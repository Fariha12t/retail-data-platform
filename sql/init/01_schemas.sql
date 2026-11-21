-- Warehouse layers. Idempotent: safe to run many times.
CREATE SCHEMA IF NOT EXISTS source;          -- simulated operational database (OLTP)
CREATE SCHEMA IF NOT EXISTS raw;             -- validated, append-only landing tables
CREATE SCHEMA IF NOT EXISTS staging;         -- dbt: cleaned, de-duplicated views
CREATE SCHEMA IF NOT EXISTS snapshots;       -- dbt: SCD Type 2 history
CREATE SCHEMA IF NOT EXISTS marts;           -- dbt: star schema + reporting tables
CREATE SCHEMA IF NOT EXISTS marts_history;   -- weekly historical snapshots of reports
CREATE SCHEMA IF NOT EXISTS audit;           -- pipeline observability
