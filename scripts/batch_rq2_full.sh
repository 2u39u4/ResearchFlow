#!/usr/bin/env bash
# Full RQ2 (20 topics x 3 repeats) with per-topic checkpoint. Run analysis separately.
set -uo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
LOG=results/experiments
mkdir -p "$LOG"

export PYTHONUNBUFFERED=1
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy

echo "=== RQ2 full started $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee "$LOG/batch_rq2_rerun.log"

$PY scripts/run_experiments.py rq2 --repeats 3 "$@" 2>&1 | tee "$LOG/batch_rq2_rerun_full.log"
rc=${PIPESTATUS[0]}
echo "rq2 exit=$rc" | tee -a "$LOG/batch_rq2_rerun.log"

echo "=== RQ2 full finished $(date -u +%Y-%m-%dT%H:%M:%SZ) exit=$rc ===" | tee -a "$LOG/batch_rq2_rerun.log"
exit "$rc"
