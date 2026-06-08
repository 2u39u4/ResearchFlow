#!/usr/bin/env bash
# Start Athena FastAPI gateway (port 8000)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}:${PYTHONPATH:-}"
exec .venv/bin/uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
