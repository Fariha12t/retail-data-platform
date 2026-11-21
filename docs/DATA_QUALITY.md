# Data quality

Quality is enforced in three places so that problems are caught at the cheapest point.

## 1. Contracts at ingestion (`contracts.py`, `validation.py`)
Per column: type, nullability, min/max, allowed values, regex. Outcomes:
* schema drift (missing column) -> batch fails
* bad row -> quarantined with reasons such as `email:bad_format`, `amount:below_min`, `stock_on_hand:invalid_type`
* duplicate key -> latest version kept (`duplicates_removed` is recorded)

Intentional dirt in the synthetic data (so you can see it work): duplicated orders, zero item quantities, negative payment amounts, malformed emails,
`N/A` / negative / blank values in inventory files, duplicated and non-numeric rows from the API, random HTTP 503s.

## 2. dbt tests (`dbt build` gates the pipeline)
* generic: `unique`, `not_null`, `accepted_values`, `relationships`, custom `non_negative`, `unique_combination_of_columns`
* singular: SCD2 windows never overlap, report revenue equals fact revenue to the cent, point-in-time joins never duplicate lines
* warn-level: captured payments vs order totals, share of "unknown" dimension members

A **warn** on `assert_payments_match_orders` is expected: a quarantined order line or payment makes an order total differ from its payment. That is the pipeline telling you the truth rather than hiding it.

## 3. Operational checks
* `retail_pipeline freshness`: every table must have a successful batch in the last 26h
* `dbt source freshness`: warn at 36h, error at 72h
* `retail_pipeline reconcile` (weekly): distinct keys in source vs warehouse; warns above 0.5% missing and fails above 2%. A small gap equals quarantined rows (see `rows_quarantined`).

## Looking at quality
```sql
select table_name, sum(rows_extracted) extracted, sum(rows_quarantined) quarantined,
       sum(duplicates_removed) dupes, round(100.0*sum(rows_quarantined)/nullif(sum(rows_extracted),0),2) quarantine_pct
from audit.ingestion_batches where status='success' group by 1;
```
Quarantined rows: `data/lake/quarantine/...` (or the S3 `quarantine/` prefix), each with a `_reasons` column.
