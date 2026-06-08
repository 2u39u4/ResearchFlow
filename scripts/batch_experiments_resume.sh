#!/usr/bin/env bash
# Resume RQ evaluation: build t03–t20 (with arXiv cooldown) → full rq1/rq2 → analysis
set -uo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
LOG=results/experiments
mkdir -p "$LOG"

TOPICS="t03 t04 t05 t06 t07 t08 t09 t10 t11 t12 t13 t14 t15 t16 t17 t18 t19 t20"

echo "=== eval batch resume $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee -a "$LOG/batch.log"

echo "--- build-pools t03–t20 ---" | tee -a "$LOG/batch.log"
$PY scripts/run_experiments.py build-pools --topic-ids $TOPICS \
  --topic-sleep 90 --sleep-after-429 120 2>&1 | tee -a "$LOG/batch_build_pools.log"
BUILD_RC=${PIPESTATUS[0]}
echo "build-pools exit=$BUILD_RC" | tee -a "$LOG/batch.log"

POOLS=$(ls -1 eval/topics/pools/t*.json 2>/dev/null | wc -l | tr -d ' ')
echo "pools_ready=$POOLS" | tee -a "$LOG/batch.log"

echo "--- rq1 (all pools x 3, Gemini judge) ---" | tee -a "$LOG/batch.log"
$PY scripts/run_experiments.py rq1 --repeats 3 2>&1 | tee "$LOG/batch_rq1.log"
echo "rq1 exit=$?" | tee -a "$LOG/batch.log"

echo "--- rq2 (all pools x 3) ---" | tee -a "$LOG/batch.log"
$PY scripts/run_experiments.py rq2 --repeats 3 2>&1 | tee "$LOG/batch_rq2.log"
echo "rq2 exit=$?" | tee -a "$LOG/batch.log"

echo "--- rq3 + analysis ---" | tee -a "$LOG/batch.log"
$PY scripts/run_experiments.py rq3 2>&1 | tee -a "$LOG/batch_rq3.log"
$PY scripts/run_experiments.py analysis 2>&1 | tee "$LOG/batch_analysis.log"

echo "=== eval batch resume finished $(date -u +%Y-%m-%dT%H:%M:%SZ) pools=$POOLS ===" | tee -a "$LOG/batch.log"
