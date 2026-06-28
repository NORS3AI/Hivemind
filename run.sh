#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

# Load .env if present (so ANTHROPIC_API_KEY is available).
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo "Warning: ANTHROPIC_API_KEY is not set. The UI will load but the council"
  echo "will return an error until you set it (see .env.example)."
fi

exec uvicorn backend.main:app --reload --host "${HOST:-127.0.0.1}" --port "${PORT:-8000}"
