"""Daily ELT: ingest 7 sources in parallel -> dbt build (snapshots, models, tests) -> checks -> reports.

{{ ds }} is the logical date = the day whose data is being processed. Re-running a date is safe
(idempotent): the batch is replaced, never duplicated.
"""
from __future__ import annotations

import pendulum
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.utils.task_group import TaskGroup
from common import CLI, DBT_BIN, DBT_DIR, DEFAULT_ARGS, TABLES

with DAG(
    dag_id="retail_daily_pipeline",
    description="Incremental ingestion -> dbt star schema -> data-quality gates -> daily report",
    schedule="0 2 * * *",
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    tags=["retail", "elt", "daily"],
    doc_md=__doc__,
) as dag:
    with TaskGroup("extract_validate_load") as ingest:
        for table in TABLES:
            BashOperator(task_id=f"ingest_{table}", bash_command=f"{CLI} ingest --table {table} --date {{{{ ds }}}}")

    # `dbt build` runs snapshots, models and tests in dependency order. A failing test stops downstream models,
    # so bad data never reaches the reporting layer.
    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command=f"cd {DBT_DIR} && {DBT_BIN} build --profiles-dir {DBT_DIR}",
    )
    dbt_source_freshness = BashOperator(
        task_id="dbt_source_freshness",
        bash_command=f"cd {DBT_DIR} && {DBT_BIN} source freshness --profiles-dir {DBT_DIR}",
    )
    freshness_check = BashOperator(task_id="freshness_check", bash_command=f"{CLI} freshness")
    daily_report = BashOperator(task_id="generate_daily_report", bash_command=f"{CLI} report --kind daily --date {{{{ ds }}}}")
    cost_metrics = BashOperator(task_id="collect_cost_metrics", bash_command=f"{CLI} cost --date {{{{ ds }}}}")

    ingest >> dbt_build >> [dbt_source_freshness, freshness_check] >> daily_report
    dbt_build >> cost_metrics
