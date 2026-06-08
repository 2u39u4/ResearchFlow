#!/usr/bin/env bash
# Deprecated wrapper — use scripts/run_hallmark_batch.sh (resumable batches).
exec "$(dirname "$0")/run_hallmark_batch.sh" "$@"
