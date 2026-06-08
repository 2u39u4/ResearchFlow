#!/usr/bin/env bash
# Launch Athena Streamlit demo UI (legacy — prefer scripts/run_web.sh for user frontend)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
STREAMLIT="${ROOT}/.venv/bin/streamlit"
if [[ ! -x "$STREAMLIT" ]]; then
  STREAMLIT="streamlit"
fi
exec "$STREAMLIT" run app/streamlit_app.py "$@"
