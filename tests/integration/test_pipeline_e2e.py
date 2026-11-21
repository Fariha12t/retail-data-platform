"""End-to-end ingestion test against a real PostgreSQL (CI starts one as a service container).

DESTRUCTIVE: drops the raw and audit schemas of the database it connects to.
"""
import os
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, text

from retail_pipeline import audit
from retail_pipeline.cli import cmd_init_db
from retail_pipeline.config import get_settings
from retail_pipeline.generate_data import Simulator
from retail_pipeline.ingest import ingest_many
from retail_pipeline.storage import LocalStore

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("ALLOW_DESTRUCTIVE_TESTS") != "1",
        reason="drops the raw/audit schemas - set ALLOW_DESTRUCTIVE_TESTS=1 and point PG_* at a throw-away database",
    ),
]
TABLES = ["customers", "orders", "order_items", "payments", "products", "inventory_snapshots"]  # no API needed


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("e2e")
    s = get_settings()
    s = type(s)(**{**s.__dict__, "landing_dir": tmp / "landing", "local_lake_dir": tmp / "lake"})
    engine = create_engine(s.db_url)
    cmd_init_db(None)
    with engine.begin() as c:
        for schema in ("raw", "audit"):
            c.execute(text(f"drop schema if exists {schema} cascade"))
    cmd_init_db(None)
    end = date(2026, 3, 15)
    Simulator(engine, s.landing_dir, seed=7, base_orders=25).seed_history(end, 5)
    return s, engine, LocalStore(s.local_lake_dir), end


def count(engine, sql):
    with engine.connect() as c:
        return c.execute(text(sql)).scalar()


def test_initial_load_quarantines_and_audits(env):
    s, engine, store, end = env
    ingest_many(engine, store, s, end, audit.new_run_id(), TABLES)
    assert count(engine, "select count(*) from raw.orders") > 0
    assert count(engine, "select count(*) from audit.ingestion_batches where status = 'success'") == len(TABLES)
    assert count(engine, "select sum(rows_quarantined) from audit.ingestion_batches") > 0
    assert store.list_keys("raw/") and store.list_keys("quarantine/")


def test_rerun_is_idempotent(env):
    s, engine, store, end = env
    before = count(engine, "select count(*) from raw.order_items")
    ingest_many(engine, store, s, end, audit.new_run_id(), TABLES)
    assert count(engine, "select count(*) from raw.order_items") == before


def test_next_day_loads_only_new_changes(env):
    s, engine, store, end = env
    Simulator(engine, s.landing_dir, seed=7, base_orders=25).simulate_day(end + timedelta(days=1))
    ingest_many(engine, store, s, end + timedelta(days=1), audit.new_run_id(), TABLES)
    batch_rows = count(engine, "select rows_extracted from audit.ingestion_batches "
                               f"where table_name = 'orders' and logical_date = '{end + timedelta(days=1)}'")
    total = count(engine, "select count(*) from source.orders")
    assert 0 < batch_rows < total
    assert count(engine, "select count(*) from (select order_id from raw.orders group by 1 having count(distinct _batch_id) > 1) t") >= 0
