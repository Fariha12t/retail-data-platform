# Cost monitoring

`retail_pipeline cost` (daily DAG task) writes `audit.cost_metrics` per component:
`lake_raw`, `lake_quarantine` (object storage bytes), `wh_raw`, `wh_snapshots`, `wh_marts`, `wh_audit` (Postgres relation sizes), `pipeline_compute` (sum of batch durations).

Monthly estimates use the prices in `.env` (S3 $0.023/GB, database $0.115/GB, compute $0.10/hour). **These are estimates, not a bill**; replace the prices with your provider's.
If the total exceeds `MONTHLY_BUDGET_USD`, a warning alert is sent. Cost controls in code: S3 lifecycle (raw -> infrequent access after 30 days, quarantine expires after 90 days) in `infra/terraform/main.tf`.
For BigQuery add bytes-scanned from `INFORMATION_SCHEMA.JOBS` as another component.
