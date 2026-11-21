"""Weekly jobs: historical report snapshots and source-vs-warehouse reconciliation."""
from __future__ import annotations

from datetime import date

from sqlalchemy import text
from sqlalchemy.engine import Engine

from .contracts import CONTRACTS
from .logging_setup import get_logger

log = get_logger(__name__)
HISTORY_TABLES = ["rpt_daily_revenue", "rpt_inventory_status", "rpt_product_performance"]


def snapshot_history(engine: Engine, snapshot_date: date) -> dict[str, int]:
    """Keep a dated copy (column as_of_date) of key reports so numbers can be audited as they looked back then."""
    out = {}
    with engine.begin() as conn:
        conn.execute(text("create schema if not exists marts_history"))
        for t in HISTORY_TABLES:
            conn.execute(text(f"create table if not exists marts_history.{t}_history as "
                              f"select cast(:d as date) as as_of_date, * from marts.{t} where false"), {"d": snapshot_date})
            conn.execute(text(f"delete from marts_history.{t}_history where as_of_date = :d"), {"d": snapshot_date})
            res = conn.execute(text(f"insert into marts_history.{t}_history select cast(:d as date), * from marts.{t}"), {"d": snapshot_date})
            out[t] = res.rowcount
    log.info("history snapshot %s: %s", snapshot_date, out)
    return out


def reconcile(engine: Engine, warn_pct: float = 0.5, fail_pct: float = 2.0) -> list[dict]:
    """Compare distinct primary keys in the operational DB vs the raw warehouse layer."""
    results = []
    with engine.connect() as conn:
        for c in (c for c in CONTRACTS.values() if c.source == "postgres"):
            pk = c.primary_key[0]
            src = conn.execute(text(f"select count(distinct {pk}) from source.{c.name}")).scalar() or 0
            raw = conn.execute(text(f'select count(distinct {pk}) from raw."{c.name}"')).scalar() or 0
            missing_pct = (src - raw) / src * 100 if src else 0.0
            status = "fail" if missing_pct > fail_pct else "warn" if missing_pct > warn_pct else "ok"
            results.append({"table": c.name, "source_keys": src, "warehouse_keys": raw, "missing_pct": round(missing_pct, 3), "status": status})
    failed = [r for r in results if r["status"] == "fail"]
    if failed:
        raise RuntimeError(f"reconciliation failed: {failed}")
    return results
