#!/usr/bin/env bash
# FrontDesk AI local starter (macOS / Linux).
# Run from anywhere:  ./start.sh
# Creates no files and reads no secrets; configure FrontDesk Project/.env first.
# See HowToSetup.md, section A.
set -euo pipefail
cd "$(dirname "$0")"

if [ -f .venv/bin/activate ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
elif [ -f venv/bin/activate ]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
else
  echo "No virtual environment found in this folder." >&2
  echo "Create one first (see HowToSetup.md, section A):" >&2
  echo "  python3.12 -m venv .venv && source .venv/bin/activate" >&2
  exit 1
fi

if ! python -c "import uvicorn, fastapi" 2>/dev/null; then
  echo "Dependencies are missing. With the venv activated, run:" >&2
  echo "  python -m pip install --require-hashes -r requirements.lock" >&2
  exit 1
fi

PORT="${PORT:-10000}"
echo "Starting FrontDesk AI on http://127.0.0.1:${PORT}  (Ctrl+C to stop)"
exec python -m uvicorn main:app --host 0.0.0.0 --port "${PORT}"
