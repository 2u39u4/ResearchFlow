#!/usr/bin/env bash
# Launch Athena Streamlit demo UI
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
exec streamlit run app/streamlit_app.py "$@"
