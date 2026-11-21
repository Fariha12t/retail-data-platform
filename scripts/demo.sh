#!/usr/bin/env bash
# One-command demo: seed history, initial load, then 3 simulated days of incremental loads
# (new orders, status changes, customer moves and price changes -> visible as SCD2 versions).
# Requires: Postgres reachable via .env, the mock API running (make api), dbt installed.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
cd "$ROOT"
DAYS="${DEMO_DAYS:-60}"

python -m retail_pipeline.cli reset-db --yes
rm -rf data/lake
SEED_OUT="$(python -m retail_pipeline.cli seed --days "$DAYS")"
echo "$SEED_OUT"
export SOURCE_HISTORY_START="$(echo "$SEED_OUT" | sed -n 's/^SOURCE_HISTORY_START=//p')"

END="$(python -m retail_pipeline.cli latest-date)"
echo ">>> initial load for $END"
scripts/run_pipeline.sh "$END"

for i in 1 2 3; do
  python -m retail_pipeline.cli simulate-day
  D="$(python -m retail_pipeline.cli latest-date)"
  echo ">>> incremental load for $D"
  scripts/run_pipeline.sh "$D"
done
python -m retail_pipeline.cli snapshot-history
python -m retail_pipeline.cli reconcile
echo "Done. Open reports/ or run: make dashboard"
