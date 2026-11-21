"""Run/batch audit trail and incremental-load watermarks."""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import text
from sqlalchemy.engine import Engine


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def new_run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6]


def compute_window(
    logical_date: date,
    watermark: datetime | None,
    previous_success: tuple[datetime, datetime] | None,
    lookback: timedelta,
    history_start: datetime,
) -> tuple[datetime, datetime]:
    """Decide which slice of source data a batch covers: [start, end).

    * Re-running a logical date that already succeeded reuses the *same* window, which
      makes the pipeline idempotent (the batch is replaced, never duplicated).
    * Otherwise the window starts at the stored high watermark minus a look-back period
      (to catch late-arriving rows; duplicates are removed downstream).
    """
    end = datetime.combine(logical_date + timedelta(days=1), time.min)
    if previous_success is not None:
        return previous_success
    start = history_start if watermark is None else watermark - lookback
    return start, end


def get_window(engine: Engine, table: str, logical_date: date, lookback: timedelta, history_start: datetime):
    with engine.connect() as conn:
        wm = conn.execute(
            text("select high_watermark from audit.watermarks where table_name = :t"), {"t": table}
        ).scalar()
        prev = conn.execute(
            text(
                """select window_start, window_end from audit.ingestion_batches
                   where table_name = :t and logical_date = :d and status = 'success'"""
            ),
            {"t": table, "d": logical_date},
        ).first()
    return compute_window(logical_date, wm, tuple(prev) if prev else None, lookback, history_start)


def start_run(engine: Engine, run_id: str, command: str, logical_date: date | None) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """insert into audit.pipeline_runs (run_id, command, logical_date, status, started_at)
                   values (:r, :c, :d, 'running', :s)
                   on conflict (run_id) do nothing"""
            ),
            {"r": run_id, "c": command, "d": logical_date, "s": utcnow()},
        )


def finish_run(engine: Engine, run_id: str, status: str, error: str | None = None) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("update audit.pipeline_runs set status=:s, finished_at=:f, error=:e where run_id=:r"),
            {"s": status, "f": utcnow(), "e": error, "r": run_id},
        )


def record_batch(engine: Engine, row: dict) -> None:
    cols = [
        "batch_id", "run_id", "table_name", "source_type", "logical_date", "window_start", "window_end",
        "rows_extracted", "rows_valid", "rows_quarantined", "duplicates_removed", "raw_uri",
        "quarantine_uri", "issues", "status", "error", "started_at", "finished_at",
    ]
    payload = {c: row.get(c) for c in cols}
    updates = ", ".join(f"{c}=excluded.{c}" for c in cols if c != "batch_id")
    sql = (
        f"insert into audit.ingestion_batches ({', '.join(cols)}) "
        f"values ({', '.join(':' + c for c in cols)}) "
        f"on conflict (batch_id) do update set {updates}"
    )
    with engine.begin() as conn:
        conn.execute(text(sql), payload)


def advance_watermark(engine: Engine, table: str, new_value: datetime) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """insert into audit.watermarks (table_name, high_watermark, updated_at)
                   values (:t, :v, now())
                   on conflict (table_name) do update
                   set high_watermark = greatest(audit.watermarks.high_watermark, excluded.high_watermark),
                       updated_at = now()"""
            ),
            {"t": table, "v": new_value},
        )
