#!/usr/bin/env bash
# Start Next.js user frontend (port 3000)
# WEB_PROD=1 uses production build (faster navigation). Default: dev with Turbopack.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/web"
if [[ ! -d node_modules ]]; then
  npm install
fi
if [[ "${WEB_PROD:-}" == "1" ]]; then
  npm run build
  exec npm run start
fi
exec npm run dev -- --turbo
