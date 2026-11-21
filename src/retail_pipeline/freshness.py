"""Data freshness checks: has every table been loaded successfully recently?"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.engine import Engine

from .audit import utcnow
from .contracts import CONTRACTS


def evaluate_freshness(last_success: dict[str, datetime | None], now: datetime, max_age_hours: float) -> list[dict]:
    """Pure function (easy to unit test): returns the list of stale or never-loaded tables."""
    problems = []
    limit = timedelta(hours=max_age_hours)
    for table in CONTRACTS:
        ts = last_success.get(table)
        if ts is None:
            problems.append({"table": table, "problem": "never loaded successfully"})
        elif now - ts > limit:
            age = (now - ts).total_seconds() / 3600
            problems.append({"table": table, "problem": f"last success {age:.1f}h ago (limit {max_age_hours}h)"})
    return problems


def check_freshness(engine: Engine, max_age_hours: float, now: datetime | None = None) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "select table_name, max(finished_at) from audit.ingestion_batches "
                "where status = 'success' group by table_name"
            )
        ).all()
    return evaluate_freshness(dict(rows), now or utcnow(), max_age_hours)
