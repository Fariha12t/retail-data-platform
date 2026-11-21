"""Extractors for the three source types: PostgreSQL, CSV drops and a REST API."""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import requests
from sqlalchemy import text
from sqlalchemy.engine import Engine

from .config import Settings
from .contracts import TableContract
from .logging_setup import get_logger
from .retry import retry

log = get_logger(__name__)


@retry(attempts=3, base_delay=1.0, exceptions=(Exception,))
def extract_postgres(engine: Engine, contract: TableContract, start: datetime, end: datetime) -> pd.DataFrame:
    """Incremental extract: rows changed inside the window [start, end)."""
    col = contract.incremental_column
    sql = text(
        f"select {', '.join(contract.column_names)} from source.{contract.name} "
        f"where {col} >= :s and {col} < :e"
    )
    with engine.connect() as conn:
        return pd.read_sql(sql, conn, params={"s": start, "e": end})


def extract_products_csv(settings: Settings, contract: TableContract, start: datetime, end: datetime) -> pd.DataFrame:
    path = settings.landing_dir / "products.csv"
    if not path.exists():
        raise FileNotFoundError(f"expected product catalogue at {path}")
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    if "updated_at" not in df.columns:
        return df  # schema drift is caught by validation
    ts = pd.to_datetime(df["updated_at"], errors="coerce")
    # keep unparseable timestamps so that validation can quarantine them visibly
    return df[(ts.isna()) | ((ts >= start) & (ts < end))].reset_index(drop=True)


_INV_RE = re.compile(r"inventory_(\d{4}-\d{2}-\d{2})\.csv$")


def extract_inventory_csv(settings: Settings, contract: TableContract, start: datetime, end: datetime) -> pd.DataFrame:
    frames = []
    for path in sorted(Path(settings.landing_dir).glob("inventory_*.csv")):
        m = _INV_RE.search(path.name)
        if not m:
            continue
        file_date = date.fromisoformat(m.group(1))
        if start.date() <= file_date < end.date():
            frames.append(pd.read_csv(path, dtype=str, keep_default_na=False))
    if not frames:
        log.warning("no inventory files between %s and %s", start.date(), end.date())
        return pd.DataFrame(columns=contract.column_names).astype("string")
    return pd.concat(frames, ignore_index=True)


@retry(attempts=5, base_delay=0.5, max_delay=10, exceptions=(requests.RequestException,))
def _api_get(url: str, params: dict) -> dict:
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def extract_marketing_api(settings: Settings, contract: TableContract, start: datetime, end: datetime) -> pd.DataFrame:
    payload = _api_get(
        f"{settings.api_base_url}/v1/marketing/spend",
        {"start": start.date().isoformat(), "end": end.date().isoformat()},  # end is exclusive
    )
    df = pd.DataFrame(payload.get("data", []))
    if df.empty:
        return pd.DataFrame(columns=contract.column_names).astype("string")
    return df.astype("string")


def extract(engine: Engine, settings: Settings, contract: TableContract, start: datetime, end: datetime) -> pd.DataFrame:
    if contract.source == "postgres":
        return extract_postgres(engine, contract, start, end)
    if contract.name == "products":
        return extract_products_csv(settings, contract, start, end)
    if contract.name == "inventory_snapshots":
        return extract_inventory_csv(settings, contract, start, end)
    if contract.name == "marketing_spend":
        return extract_marketing_api(settings, contract, start, end)
    raise ValueError(f"no extractor for {contract.name}")
