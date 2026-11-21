"""Weekly maintenance: reconciliation, rebuild of reporting tables, history snapshots, weekly report, dbt docs."""
from __future__ import annotations

import pendulum
from airflow import DAG
from airflow.operators.bash import BashOperator
from common import CLI, DBT_BIN, DBT_DIR, DEFAULT_ARGS

with DAG(
    dag_id="retail_weekly_pipeline",
    description="Weekly reconciliation, report snapshots and documentation refresh",
    schedule="0 4 * * 1",  # Mondays 04:00 UTC
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    tags=["retail", "weekly"],
    doc_md=__doc__,
) as dag:
    reconcile = BashOperator(task_id="reconcile_source_vs_warehouse", bash_command=f"{CLI} reconcile")
    # Snapshots are excluded on purpose: they hold SCD2 history and must never be rebuilt from scratch.
    rebuild_marts = BashOperator(
        task_id="rebuild_marts",
        bash_command=f"cd {DBT_DIR} && {DBT_BIN} build --profiles-dir {DBT_DIR} --exclude resource_type:snapshot",
    )
    history = BashOperator(task_id="snapshot_report_history", bash_command=f"{CLI} snapshot-history --date {{{{ ds }}}}")
    weekly_report = BashOperator(task_id="generate_weekly_report", bash_command=f"{CLI} report --kind weekly --date {{{{ ds }}}}")
    docs = BashOperator(
        task_id="dbt_docs_generate",
        bash_command=f"cd {DBT_DIR} && {DBT_BIN} docs generate --profiles-dir {DBT_DIR}",
    )

    reconcile >> rebuild_marts >> [history, weekly_report, docs]
