#!/usr/bin/env bash
# Single-source scrape invocation, called from supercronic.
set -euo pipefail

SOURCE="${1:-ats}"
SLEEP="${SLEEP_PER_COMPANY:-0.6}"

cd /app
echo "[$(date -Is)] scrape source=${SOURCE}"
python -m job_scraper scrape --source "${SOURCE}" --sleep "${SLEEP}"
