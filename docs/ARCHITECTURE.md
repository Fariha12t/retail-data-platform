# Architecture

## Layers
| Layer | Where | Purpose |
|---|---|---|
| Sources | Postgres `source` schema, `data/landing/*.csv`, mock REST API | Simulated operational systems |
| Raw files | S3/MinIO `raw/<source>/<table>/ingest_date=YYYY-MM-DD/<batch>.parquet` | Immutable copy of what the source sent (replay / audit) |
| Quarantine | `quarantine/<table>/...` | Rows rejected by validation, with a `_reasons` column |
| Warehouse raw | Postgres `raw.*` | Validated, typed, append-only, tagged with `_batch_id`, `_ingested_at`, `_source_file` |
| Staging | dbt views `staging.*` | Latest version per key, cleaned names and types, derived amounts |
| Snapshots | `snapshots.*` | SCD Type 2 history (dbt snapshot, timestamp strategy) |
| Marts | `marts.*` | Dimensions, facts, reporting tables |
| History | `marts_history.*` | Weekly dated copies of key reports |
| Audit | `audit.*` | Runs, batches, watermarks, cost metrics |

## One daily run
1. Airflow starts `retail_daily_pipeline` for logical date `{{ ds }}` (02:00 UTC).
2. Seven `ingest_<table>` tasks run in parallel. Each: pick window -> extract -> write raw file -> validate -> quarantine bad rows -> delete+insert batch -> record audit row -> advance watermark.
3. `dbt build`: staging -> snapshots -> marts -> tests, in dependency order. An error-level test failure skips everything downstream.
4. Freshness checks (`retail_pipeline freshness`, `dbt source freshness`).
5. HTML/CSV report and cost metrics. Any task failure triggers retries (3x, exponential back-off) and then a Slack alert.

## Incremental window logic (`audit.compute_window`)
* First run: change-tracked sources load everything; date-partitioned sources start at `SOURCE_HISTORY_START`.
* Later runs: `[watermark - look-back, end of logical date)`.
* Re-run of a successful date: the stored window is reused, so output is identical (idempotent).
* Limitation: a backfill of an *older* date that never ran, after newer dates succeeded, is not supported by the watermark approach. Use a dedicated backfill with explicit windows.

## Failure handling
| Failure | Behaviour |
|---|---|
| API returns 5xx / network error | Retried with exponential back-off (5 attempts), then task fails and alerts |
| Source schema loses a column | Batch fails (`SchemaError`), recorded in `audit.ingestion_batches`, alert |
| Source adds a column | Warning, column ignored |
| Bad values (bad email, negative amount, "N/A") | Row quarantined with reason; batch still succeeds |
| Duplicates | Deduplicated by key (latest version wins) |
| dbt test fails (error) | Downstream models skipped; report not generated |
| Table not loaded for >26h | Freshness check fails and alerts |
| One source fails | Other sources still load; the run fails at the end |

## Scaling notes
Postgres is a fine warehouse for this volume. For larger data, swap the warehouse to BigQuery/Redshift/Snowflake (dbt profile included for BigQuery; a few Postgres-specific functions need adapting),
load via `COPY`/external tables from the S3 files, and move Airflow to a managed service (MWAA/Cloud Composer).
