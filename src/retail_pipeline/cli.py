"""Command line entry point:  python -m retail_pipeline.cli <command>

Every Airflow task is just one of these commands, so everything can be run and debugged locally.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta

from sqlalchemy import create_engine, text

from . import audit
from .config import get_settings
from .contracts import CONTRACTS
from .logging_setup import configure_logging, get_logger, run_id_var
from .notify import send_alert

log = get_logger("retail_pipeline.cli")
SQL_DIR_CANDIDATES = ["sql/init", "/opt/pipeline/sql/init"]


def _date(s: str) -> date:
    return date.fromisoformat(s)


def _engine():
    return create_engine(get_settings().db_url, pool_pre_ping=True)


def cmd_init_db(args) -> None:
    from pathlib import Path
    sql_dir = next((Path(p) for p in SQL_DIR_CANDIDATES if Path(p).exists()), None)
    if not sql_dir:
        raise SystemExit("sql/init directory not found (run from the repo root)")
    engine = _engine()
    with engine.begin() as conn:
        for f in sorted(sql_dir.glob("*.sql")):
            conn.exec_driver_sql(f.read_text())
            log.info("applied %s", f.name)


def cmd_reset_db(args) -> None:
    """Drop every project schema (demo/dev only!) and recreate it."""
    if not args.yes:
        raise SystemExit("this deletes all warehouse data; pass --yes to confirm")
    with _engine().begin() as conn:
        for schema in ("source", "raw", "staging", "snapshots", "marts", "marts_history", "audit"):
            conn.exec_driver_sql(f"drop schema if exists {schema} cascade")
    cmd_init_db(args)


def cmd_seed(args) -> None:
    from .generate_data import Simulator
    s = get_settings()
    end = args.end or (date.today() - timedelta(days=1))
    start = Simulator(_engine(), s.landing_dir, seed=args.seed).seed_history(end, args.days)
    print(f"seeded {args.days} days: {start} .. {end}")
    print(f"SOURCE_HISTORY_START={start}")


def cmd_simulate_day(args) -> None:
    from .generate_data import Simulator
    sim = Simulator(_engine(), get_settings().landing_dir, seed=args.seed)
    day = args.date or ((sim.latest_date() or date.today() - timedelta(days=1)) + timedelta(days=1))
    sim.simulate_day(day)
    print(f"simulated {day}")


def cmd_latest_date(args) -> None:
    from .generate_data import Simulator
    print(Simulator(_engine(), get_settings().landing_dir).latest_date())


def cmd_ingest(args) -> None:
    from .ingest import ingest_many
    from .storage import get_store
    s, engine = get_settings(), _engine()
    run_id = args.run_id or audit.new_run_id()
    run_id_var.set(run_id)
    tables = [args.table] if args.table else None
    if args.table and args.table not in CONTRACTS:
        raise SystemExit(f"unknown table {args.table}; choose from {list(CONTRACTS)}")
    audit.start_run(engine, run_id, f"ingest:{args.table or 'all'}", args.date)
    try:
        ingest_many(engine, get_store(s), s, args.date, run_id, tables)
        audit.finish_run(engine, run_id, "success")
    except Exception as exc:
        audit.finish_run(engine, run_id, "failed", str(exc)[:1000])
        raise


def cmd_freshness(args) -> None:
    from .freshness import check_freshness
    s = get_settings()
    problems = check_freshness(_engine(), args.max_age_hours or s.freshness_max_age_hours)
    if problems:
        send_alert("Data freshness check failed", "\n".join(f"- {p['table']}: {p['problem']}" for p in problems), "error", s)
        raise SystemExit(1)
    log.info("all %d tables are fresh", len(CONTRACTS))


def cmd_report(args) -> None:
    from .reports import daily_report, weekly_report
    s, engine = get_settings(), _engine()
    path = (weekly_report if args.kind == "weekly" else daily_report)(engine, args.date, s.reports_dir)
    print(path)


def cmd_cost(args) -> None:
    from .cost import collect_cost_metrics
    from .storage import get_store
    s = get_settings()
    rows = collect_cost_metrics(_engine(), get_store(s), s, args.date or date.today())
    for r in rows:
        print(f"{r['component']:<18} {r['bytes_stored'] / 1e6:>10.2f} MB  ~${r['est_monthly_usd']:.4f}/month")


def cmd_snapshot_history(args) -> None:
    from .maintenance import snapshot_history
    snapshot_history(_engine(), args.date or date.today())


def cmd_reconcile(args) -> None:
    from .maintenance import reconcile
    for r in reconcile(_engine()):
        print(r)


def cmd_alert_test(args) -> None:
    send_alert("Test alert", "If you can read this, alerting works.", "warning")


def cmd_sql(args) -> None:
    with _engine().connect() as c:
        for row in c.execute(text(args.query)):
            print(row)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="retail_pipeline")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="create schemas and audit tables").set_defaults(fn=cmd_init_db)

    sp = sub.add_parser("reset-db", help="DROP all project schemas and recreate them (dev only)")
    sp.add_argument("--yes", action="store_true")
    sp.set_defaults(fn=cmd_reset_db)

    sp = sub.add_parser("seed", help="generate synthetic source data")
    sp.add_argument("--days", type=int, default=90)
    sp.add_argument("--end", type=_date)
    sp.add_argument("--seed", type=int, default=42)
    sp.set_defaults(fn=cmd_seed)

    sp = sub.add_parser("simulate-day", help="advance the simulated source systems by one day")
    sp.add_argument("--date", type=_date)
    sp.add_argument("--seed", type=int, default=42)
    sp.set_defaults(fn=cmd_simulate_day)

    sub.add_parser("latest-date", help="newest order date in the source DB").set_defaults(fn=cmd_latest_date)

    sp = sub.add_parser("ingest", help="extract, validate and load into raw")
    sp.add_argument("--date", type=_date, required=True, help="logical date (YYYY-MM-DD)")
    sp.add_argument("--table", help="one table only (default: all)")
    sp.add_argument("--run-id")
    sp.set_defaults(fn=cmd_ingest)

    sp = sub.add_parser("freshness", help="fail if any table was not loaded recently")
    sp.add_argument("--max-age-hours", type=float)
    sp.set_defaults(fn=cmd_freshness)

    sp = sub.add_parser("report", help="generate the HTML/CSV report")
    sp.add_argument("--kind", choices=["daily", "weekly"], default="daily")
    sp.add_argument("--date", type=_date, required=True)
    sp.set_defaults(fn=cmd_report)

    sp = sub.add_parser("cost", help="record cloud cost estimates")
    sp.add_argument("--date", type=_date)
    sp.set_defaults(fn=cmd_cost)

    sp = sub.add_parser("snapshot-history", help="weekly dated copy of key reports")
    sp.add_argument("--date", type=_date)
    sp.set_defaults(fn=cmd_snapshot_history)

    sub.add_parser("reconcile", help="compare source and warehouse key counts").set_defaults(fn=cmd_reconcile)
    sub.add_parser("alert-test", help="send a test notification").set_defaults(fn=cmd_alert_test)

    sp = sub.add_parser("sql", help="run an ad-hoc query")
    sp.add_argument("query")
    sp.set_defaults(fn=cmd_sql)
    return p


def main(argv: list[str] | None = None) -> None:
    configure_logging()
    args = build_parser().parse_args(argv)
    try:
        args.fn(args)
    except SystemExit:
        raise
    except Exception as exc:
        log.error("command %s failed: %s", args.command, exc, exc_info=bool(os.environ.get("DEBUG")))
        sys.exit(1)


if __name__ == "__main__":
    main()
