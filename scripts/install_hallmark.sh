#!/usr/bin/env bash
# Download HALLMARK (no git-lfs) and install runtime deps for eval (Python 3.10+).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENDOR="${HALLMARK_ROOT:-$ROOT/.vendor/hallmark}"
ZIP_URL="https://github.com/rpatrik96/hallmark/archive/refs/heads/main.zip"

pick_python() {
  for cmd in python3.12 python3.11 python3.10; do
    if command -v "$cmd" >/dev/null 2>&1; then
      echo "$cmd"
      return 0
    fi
  done
  echo "Need Python 3.10+ (python3.11 recommended)." >&2
  exit 1
}

PY="$(pick_python)"
echo "Using $PY ($("$PY" --version))"

mkdir -p "$(dirname "$VENDOR")"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "Downloading HALLMARK..."
curl -fsSL -o "$TMP/hallmark.zip" "$ZIP_URL"
unzip -q "$TMP/hallmark.zip" -d "$TMP"
rm -rf "$VENDOR"
mv "$TMP/hallmark-main" "$VENDOR"

EVAL_VENV="$ROOT/.venv-eval"
echo "Creating eval venv at .venv-eval ..."
"$PY" -m venv "$EVAL_VENV"
# shellcheck source=/dev/null
source "$EVAL_VENV/bin/activate"
pip install -q -r "$ROOT/requirements-eval.txt"

echo ""
echo "Installed to: $VENDOR"
echo "Run evaluation:"
echo "  .venv-eval/bin/python scripts/run_hallmark_eval.py --stats-only"
echo "  .venv-eval/bin/python scripts/run_hallmark_eval.py --split dev_public --limit 20 --analyze"
