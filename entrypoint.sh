#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-8080}"
export PYTHONPATH="/app/src:${PYTHONPATH:-}"

echo "==> Starting Autonomous Trading Analyst API on port ${PORT}..."
exec /usr/local/bin/uvicorn autonomous_trading_analyst.api:app --host 0.0.0.0 --port "${PORT}" --log-level info
