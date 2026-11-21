# Runbook

| Symptom | Likely cause | What to do |
|---|---|---|
| `ingest_<table>` failed, "missing required columns" | Source schema changed | Check `audit.ingestion_batches.error`; update `contracts.py` (and the staging model); re-run the task |
| `ingest_marketing_spend` failed after retries | API down / rate limited | Re-run later; the look-back window refetches the gap automatically |
| `dbt_build` failed on a test | Bad data reached the warehouse | `cd dbt && dbt test --store-failures`, inspect `compiled` SQL in `dbt/target`, fix at source or tighten the contract; re-run |
| Freshness check failed | A table was not loaded in 26h | See `audit.ingestion_batches` for the latest status per table |
| Reconcile failed (>2% missing) | Many rows quarantined or a window gap | Inspect quarantine files and `issues` JSON in `audit.ingestion_batches` |
| Cost alert | Storage or compute above budget | Check `audit.cost_metrics`; review lifecycle rules, old raw files |

## Common commands
```bash
python -m retail_pipeline.cli ingest --date 2026-01-31              # all tables
python -m retail_pipeline.cli ingest --date 2026-01-31 --table orders
scripts/run_pipeline.sh 2026-01-31                                  # whole daily flow
python -m retail_pipeline.cli sql "select * from audit.pipeline_runs order by started_at desc limit 5"
python -m retail_pipeline.cli alert-test                            # verify Slack/email config
```

## Re-running safely
Re-running a date is safe: the same window is reused and the batch is replaced.
**Never** run `dbt snapshot --full-refresh` or `dbt build --full-refresh` including snapshots: that deletes SCD2 history.
The weekly DAG excludes snapshots for this reason.

## Alerts
Set `SLACK_WEBHOOK_URL` (and optionally SMTP_* / ALERT_EMAIL_TO). Airflow failure callbacks and the Python checks both use it.
