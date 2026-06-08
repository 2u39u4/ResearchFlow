#!/usr/bin/env bash
# Auto-run HALLMARK batches until dev_public is complete.
# - One batch (50 entries) per iteration, per-entry checkpoint preserved
# - Safe to stop (kill this script); re-run to resume from predictions.jsonl
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PY="${ROOT}/.venv-eval/bin/python"
CHECKPOINT="${ROOT}/results/hallmark_checkpoints/dev_public"
LOG="${ROOT}/results/hallmark_auto.log"
PIDFILE="${ROOT}/results/hallmark_auto.pid"
STATE="${CHECKPOINT}/state.json"
BATCH_SIZE="${BATCH_SIZE:-50}"
DELAY="${DELAY:-0.2}"
SLEEP_BETWEEN="${SLEEP_BETWEEN:-3}"
FAIL_SLEEP="${FAIL_SLEEP:-60}"

read_state() {
  if [[ ! -f "$STATE" ]]; then
    echo "0 1119"
    return
  fi
  "$PY" - <<'PY' "$STATE"
import json, sys
d = json.load(open(sys.argv[1]))
print(d.get("completed_count", 0), d.get("total_entries", 1119))
PY
}

mkdir -p results "$CHECKPOINT"

if [[ -f "$PIDFILE" ]]; then
  old_pid="$(cat "$PIDFILE")"
  if ps -p "$old_pid" >/dev/null 2>&1; then
    echo "Auto runner already running (PID $old_pid). Log: $LOG"
    exit 0
  fi
fi

echo $$ > "$PIDFILE"
trap 'rm -f "$PIDFILE"' EXIT

log() {
  echo "[$(date -Iseconds)] $*" | tee -a "$LOG"
}

log "=== HALLMARK auto runner start (batch_size=$BATCH_SIZE delay=$DELAY) ==="

batch_num=0
while true; do
  read -r completed total <<< "$(read_state)"
  if (( completed >= total )); then
    log "All done: $completed/$total entries."
    if [[ ! -f results/athena_dev_public_full.json ]]; then
      log "Writing final merged outputs..."
      "$PY" scripts/run_hallmark_batch.py \
        --split dev_public \
        --batch-size "$BATCH_SIZE" \
        --delay "$DELAY" \
        --checkpoint-dir "$CHECKPOINT" \
        --output results/athena_dev_public_full.json \
        --comparison-md results/athena_vs_baselines_full.md \
        --analyze >> "$LOG" 2>&1
    fi
    log "=== Auto runner finished ==="
    exit 0
  fi

  batch_num=$((batch_num + 1))
  next=$((completed + 1))
  end=$((completed + BATCH_SIZE))
  if (( end > total )); then end=$total; fi
  log "Batch run #$batch_num: entries $next-$end ($completed/$total done)"

  if ! "$PY" scripts/run_hallmark_batch.py \
    --split dev_public \
    --batch-size "$BATCH_SIZE" \
    --delay "$DELAY" \
    --max-batches 1 \
    --checkpoint-dir "$CHECKPOINT" \
    --analyze >> "$LOG" 2>&1; then
    log "Batch failed — retry in ${FAIL_SLEEP}s"
    sleep "$FAIL_SLEEP"
    continue
  fi

  read -r completed total <<< "$(read_state)"
  log "Batch #$batch_num complete → $completed/$total"
  sleep "$SLEEP_BETWEEN"
done
