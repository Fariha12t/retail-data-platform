#!/usr/bin/env bash
# Run the full daily pipeline for one logical date, exactly like the Airflow DAG does:
#   ingest -> dbt build (snapshots, models, tests) -> freshness -> report -> cost
# Usage: scripts/run_pipeline.sh 2026-01-31
set -euo pipefail
DATE="${1:?usage: run_pipeline.sh YYYY-MM-DD}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export DBT_PROFILES_DIR="${DBT_PROFILES_DIR:-$ROOT/dbt}"
cd "$ROOT"

echo "== [1/5] ingest $DATE"
python -m retail_pipeline.cli ingest --date "$DATE"
echo "== [2/5] dbt build (staging -> snapshots -> marts -> tests)"
(cd dbt && dbt build)
echo "== [3/5] freshness check"
python -m retail_pipeline.cli freshness
echo "== [4/5] daily report"
python -m retail_pipeline.cli report --kind daily --date "$DATE"
echo "== [5/5] cost metrics"
python -m retail_pipeline.cli cost --date "$DATE"
