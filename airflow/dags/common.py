"""Shared settings for the DAGs.

Airflow only *orchestrates*. The actual work runs in an isolated virtualenv (see Dockerfile.airflow)
via the project's CLI and dbt, so Airflow's own dependency pins never clash with pandas/dbt.
"""
from __future__ import annotations

import json
import os
import urllib.request
from datetime import timedelta

PIPELINE_PY = os.environ.get("PIPELINE_PYTHON", "/home/airflow/venv/bin/python")
DBT_BIN = os.environ.get("DBT_BIN", "/home/airflow/venv/bin/dbt")
DBT_DIR = os.environ.get("DBT_DIR", "/opt/pipeline/dbt")
CLI = f"{PIPELINE_PY} -m retail_pipeline.cli"

# Keep in sync with src/retail_pipeline/contracts.py (one extract+load task per table).
TABLES = ["customers", "orders", "order_items", "payments", "products", "inventory_snapshots", "marketing_spend"]


def alert_on_failure(context) -> None:
    """Airflow failure callback -> Slack (if SLACK_WEBHOOK_URL is set) and the task log."""
    ti = context["task_instance"]
    msg = f"Airflow task failed: {ti.dag_id}.{ti.task_id} (logical date {context['ds']}, try {ti.try_number})"
    print(f"ALERT {msg}")
    url = os.environ.get("SLACK_WEBHOOK_URL")
    if url:
        try:
            req = urllib.request.Request(
                url, data=json.dumps({"text": f":rotating_light: {msg}"}).encode(), headers={"Content-Type": "application/json"}
            )
            urllib.request.urlopen(req, timeout=10)  # noqa: S310
        except Exception as exc:  # alerting must never mask the original failure
            print(f"slack alert failed: {exc}")


DEFAULT_ARGS = {
    "owner": "data-engineering",
    "retries": 3,
    "retry_delay": timedelta(minutes=2),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=20),
    "execution_timeout": timedelta(minutes=45),
    "on_failure_callback": alert_on_failure,
}
