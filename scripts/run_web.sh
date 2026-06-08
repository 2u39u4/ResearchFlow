#!/usr/bin/env bash
# Start Next.js user frontend (port 3000)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/web"
if [[ ! -d node_modules ]]; then
  npm install
fi
exec npm run dev
