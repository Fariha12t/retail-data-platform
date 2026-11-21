-- Observability tables written by the pipeline.
CREATE TABLE IF NOT EXISTS audit.pipeline_runs (
    run_id        text PRIMARY KEY,
    command       text NOT NULL,
    logical_date  date,
    status        text NOT NULL,            -- running | success | failed
    started_at    timestamp NOT NULL DEFAULT now(),
    finished_at   timestamp,
    error         text
);

CREATE TABLE IF NOT EXISTS audit.ingestion_batches (
    batch_id            text PRIMARY KEY,   -- <table>__<logical_date>
    run_id              text,
    table_name          text NOT NULL,
    source_type         text NOT NULL,
    logical_date        date NOT NULL,
    window_start        timestamp NOT NULL,
    window_end          timestamp NOT NULL,
    rows_extracted      integer DEFAULT 0,
    rows_valid          integer DEFAULT 0,
    rows_quarantined    integer DEFAULT 0,
    duplicates_removed  integer DEFAULT 0,
    raw_uri             text,
    quarantine_uri      text,
    issues              text,
    status              text NOT NULL,      -- success | failed
    error               text,
    started_at          timestamp NOT NULL,
    finished_at         timestamp
);
CREATE INDEX IF NOT EXISTS ix_batches_table_date ON audit.ingestion_batches (table_name, logical_date);

CREATE TABLE IF NOT EXISTS audit.watermarks (
    table_name      text PRIMARY KEY,
    high_watermark  timestamp NOT NULL,
    updated_at      timestamp NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit.cost_metrics (
    metric_date        date NOT NULL,
    component          text NOT NULL,
    bytes_stored       bigint,
    rows_processed     bigint,
    compute_seconds    numeric(12,2),
    est_monthly_usd    numeric(12,4),
    PRIMARY KEY (metric_date, component)
);
