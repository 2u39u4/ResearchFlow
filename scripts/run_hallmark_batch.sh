#!/usr/bin/env bash
# Resumable HALLMARK dev_public eval: 50 entries/batch, delay=0.2, per-entry checkpoint.
# Safe to stop (Ctrl+C / kill) and re-run — progress resumes from predictions.jsonl.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PY="${ROOT}/.venv-eval/bin/python"
LOG="${ROOT}/results/hallmark_batch_run.log"
PIDFILE="${ROOT}/results/hallmark_batch.pid"
CHECKPOINT="${ROOT}/results/hallmark_checkpoints/dev_public"

mkdir -p results
echo "=== $(date -Iseconds) batch run start ===" | tee -a "$LOG"

nohup "$PY" scripts/run_hallmark_batch.py \
  --split dev_public \
  --batch-size 50 \
  --delay 0.2 \
  --checkpoint-dir "$CHECKPOINT" \
  --output results/athena_dev_public_full.json \
  --comparison-md results/athena_vs_baselines_full.md \
  --analyze \
  >> "$LOG" 2>&1 &
echo $! > "$PIDFILE"
echo "Started PID=$(cat "$PIDFILE"). Log: $LOG"
echo "Checkpoint: $CHECKPOINT"
echo "Tail: tail -f $LOG"
