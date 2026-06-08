#!/usr/bin/env bash
# Full RQ1 + RQ2 (20 topics x 3 repeats) + rq3 + analysis
set -uo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
LOG=results/experiments
mkdir -p "$LOG"

echo "=== RQ1+RQ2 batch started $(date -u +%Y-%m-%dT%H:%M:%SZ) pools=$(ls -1 eval/topics/pools/t*.json 2>/dev/null | wc -l | tr -d ' ')" | tee "$LOG/batch_rq12.log"

echo "--- rq1 (20 topics x 3, Gemini judge) ---" | tee -a "$LOG/batch_rq12.log"
$PY scripts/run_experiments.py rq1 --repeats 3 2>&1 | tee "$LOG/batch_rq1_full.log"
echo "rq1 exit=$?" | tee -a "$LOG/batch_rq12.log"

echo "--- rq2 (20 topics x 3) ---" | tee -a "$LOG/batch_rq12.log"
$PY scripts/run_experiments.py rq2 --repeats 3 2>&1 | tee "$LOG/batch_rq2_full.log"
echo "rq2 exit=$?" | tee -a "$LOG/batch_rq12.log"

echo "--- rq3 + analysis ---" | tee -a "$LOG/batch_rq12.log"
$PY scripts/run_experiments.py rq3 2>&1 | tee -a "$LOG/batch_rq3.log"
$PY scripts/run_experiments.py analysis 2>&1 | tee "$LOG/batch_analysis_full.log"
echo "analysis exit=$?" | tee -a "$LOG/batch_rq12.log"

echo "=== RQ1+RQ2 batch finished $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee -a "$LOG/batch_rq12.log"
