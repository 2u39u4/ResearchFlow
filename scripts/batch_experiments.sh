#!/usr/bin/env bash
# Full RQ evaluation batch: build-pools (20 topics) → rq1 → rq2 → rq3 → analysis
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
LOG=results/experiments
mkdir -p "$LOG"

echo "=== eval batch started $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee "$LOG/batch.log"

echo "--- build-pools (20 topics) ---" | tee -a "$LOG/batch.log"
$PY scripts/run_experiments.py build-pools --topic-sleep 90 --sleep-after-429 120 2>&1 | tee "$LOG/batch_build_pools.log"
BUILD_RC=${PIPESTATUS[0]}
echo "build-pools exit=$BUILD_RC" | tee -a "$LOG/batch.log"

echo "--- rq1 (20 topics x 3 repeats, Gemini judge) ---" | tee -a "$LOG/batch.log"
$PY scripts/run_experiments.py rq1 --repeats 3 2>&1 | tee "$LOG/batch_rq1.log"
echo "rq1 exit=$?" | tee -a "$LOG/batch.log"

echo "--- rq2 (20 topics x 3 repeats) ---" | tee -a "$LOG/batch.log"
$PY scripts/run_experiments.py rq2 --repeats 3 2>&1 | tee "$LOG/batch_rq2.log"
echo "rq2 exit=$?" | tee -a "$LOG/batch.log"

echo "--- rq3 + analysis ---" | tee -a "$LOG/batch.log"
$PY scripts/run_experiments.py rq3 2>&1 | tee -a "$LOG/batch_rq3.log"
$PY scripts/run_experiments.py analysis 2>&1 | tee "$LOG/batch_analysis.log"

echo "=== eval batch finished $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee -a "$LOG/batch.log"
