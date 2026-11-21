"""One ingestion batch per table: extract -> raw files -> validate -> load -> audit."""
from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta

from sqlalchemy.engine import Engine

from . import audit
from .config import Settings
from .contracts import CONTRACTS, TableContract
from .extract import extract
from .load import load_raw
from .logging_setup import get_logger
from .storage import ObjectStore
from .validation import SchemaError, validate

log = get_logger(__name__)


def ingest_table(
    engine: Engine,
    store: ObjectStore,
    settings: Settings,
    contract: TableContract,
    logical_date: date,
    run_id: str,
) -> dict:
    batch_id = f"{contract.name}__{logical_date.isoformat()}"
    started = audit.utcnow()
    # First load of a table: change-tracked sources (DB, product CSV) are loaded in full; date-partitioned
    # sources (inventory files, marketing API) start at SOURCE_HISTORY_START.
    history_start = (
        datetime(1970, 1, 1) if contract.incremental_column else datetime.combine(settings.history_start, time.min)
    )
    start, end = audit.get_window(engine, contract.name, logical_date, timedelta(hours=contract.lookback_hours), history_start)
    row = {
        "batch_id": batch_id, "run_id": run_id, "table_name": contract.name, "source_type": contract.source,
        "logical_date": logical_date, "window_start": start, "window_end": end, "started_at": started,
    }
    try:
        log.info("ingesting %s window [%s, %s)", contract.name, start, end)
        df = extract(engine, settings, contract, start, end)
        row["rows_extracted"] = len(df)

        # 1) Raw layer: keep exactly what the source gave us (immutable, partitioned by date).
        prefix = f"raw/{contract.source}/{contract.name}/ingest_date={logical_date.isoformat()}"
        row["raw_uri"] = store.put_dataframe(df.astype("string") if contract.source != "postgres" else df, f"{prefix}/{batch_id}.parquet")

        # 2) Validate: schema drift fails the batch, bad rows are quarantined, duplicates removed.
        result = validate(df, contract)
        if result.extra_columns:
            log.warning("%s: ignoring unexpected columns %s", contract.name, result.extra_columns)
        if not result.quarantine.empty:
            row["quarantine_uri"] = store.put_dataframe(
                result.quarantine, f"quarantine/{contract.name}/ingest_date={logical_date.isoformat()}/{batch_id}.parquet"
            )

        # 3) Load: delete-then-insert by batch id inside one transaction.
        loaded = load_raw(engine, contract, result.clean, batch_id, row["raw_uri"])
        row.update(
            rows_valid=loaded,
            rows_quarantined=result.rows_quarantined,
            duplicates_removed=result.duplicates_removed,
            issues=json.dumps(result.issues),
            status="success",
            finished_at=audit.utcnow(),
        )
        audit.record_batch(engine, row)
        audit.advance_watermark(engine, contract.name, end)
        log.info(
            "%s ok: extracted=%d loaded=%d quarantined=%d dupes=%d",
            contract.name, row["rows_extracted"], loaded, result.rows_quarantined, result.duplicates_removed,
        )
    except Exception as exc:
        row.update(status="failed", error=f"{type(exc).__name__}: {exc}"[:1000], finished_at=audit.utcnow())
        audit.record_batch(engine, row)
        log.error("%s failed: %s", contract.name, exc, exc_info=not isinstance(exc, SchemaError))
        raise
    return row


def ingest_many(
    engine: Engine, store: ObjectStore, settings: Settings, logical_date: date, run_id: str, tables: list[str] | None = None
) -> list[dict]:
    names = tables or list(CONTRACTS)
    results, failures = [], []
    for name in names:
        try:
            results.append(ingest_table(engine, store, settings, CONTRACTS[name], logical_date, run_id))
        except Exception as exc:  # keep going so one bad source does not block the others
            failures.append(f"{name}: {exc}")
    if failures:
        raise RuntimeError("ingestion failed for: " + "; ".join(failures))
    return results
