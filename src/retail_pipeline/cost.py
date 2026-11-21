"""Cloud cost monitoring (estimates from storage footprint and compute time)."""
from __future__ import annotations

from datetime import date

from sqlalchemy import text
from sqlalchemy.engine import Engine

from .config import Settings
from .notify import send_alert
from .storage import ObjectStore

GB = 1024**3
WAREHOUSE_SCHEMAS = {"wh_raw": "raw", "wh_snapshots": "snapshots", "wh_marts": "marts", "wh_audit": "audit"}


def estimate_monthly_usd(component: str, bytes_stored: int, compute_seconds: float, s: Settings) -> float:
    if component.startswith("lake_"):
        return bytes_stored / GB * s.s3_price_per_gb_month
    if component.startswith("wh_"):
        return bytes_stored / GB * s.db_price_per_gb_month
    return compute_seconds / 3600 * 30 * s.compute_price_per_hour  # one run per day


def collect_cost_metrics(engine: Engine, store: ObjectStore, settings: Settings, metric_date: date) -> list[dict]:
    rows: list[dict] = []
    rows.append({"component": "lake_raw", "bytes_stored": store.size_bytes("raw/"), "rows_processed": None, "compute_seconds": 0})
    rows.append({"component": "lake_quarantine", "bytes_stored": store.size_bytes("quarantine/"), "rows_processed": None, "compute_seconds": 0})
    with engine.connect() as conn:
        sizes = dict(conn.execute(text(
            """select n.nspname, coalesce(sum(pg_total_relation_size(c.oid)), 0)::bigint
               from pg_class c join pg_namespace n on n.oid = c.relnamespace
               where c.relkind in ('r', 'm') and n.nspname = any(:schemas) group by 1"""),
            {"schemas": list(WAREHOUSE_SCHEMAS.values())}).all())
        for comp, schema in WAREHOUSE_SCHEMAS.items():
            rows.append({"component": comp, "bytes_stored": int(sizes.get(schema, 0)), "rows_processed": None, "compute_seconds": 0})
        rows_processed, seconds = conn.execute(text(
            """select coalesce(sum(rows_extracted), 0), coalesce(sum(extract(epoch from finished_at - started_at)), 0)
               from audit.ingestion_batches where logical_date = :d and status = 'success'"""), {"d": metric_date}).one()
    rows.append({"component": "pipeline_compute", "bytes_stored": 0, "rows_processed": int(rows_processed), "compute_seconds": float(seconds)})

    for r in rows:
        r["metric_date"] = metric_date
        r["est_monthly_usd"] = round(estimate_monthly_usd(r["component"], r["bytes_stored"], r["compute_seconds"], settings), 4)
    with engine.begin() as conn:
        conn.execute(text(
            """insert into audit.cost_metrics (metric_date, component, bytes_stored, rows_processed, compute_seconds, est_monthly_usd)
               values (:metric_date, :component, :bytes_stored, :rows_processed, :compute_seconds, :est_monthly_usd)
               on conflict (metric_date, component) do update set bytes_stored = excluded.bytes_stored,
               rows_processed = excluded.rows_processed, compute_seconds = excluded.compute_seconds,
               est_monthly_usd = excluded.est_monthly_usd"""), rows)
    total = sum(r["est_monthly_usd"] for r in rows)
    if total > settings.monthly_budget_usd:
        send_alert("Cost budget exceeded", f"Estimated monthly cost ${total:.2f} > budget ${settings.monthly_budget_usd:.2f}", "warning", settings)
    return rows
