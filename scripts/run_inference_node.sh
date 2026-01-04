#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
APP_DIR="$SCRIPT_DIR/../services/inference-node"

cd "$APP_DIR"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export ALLOW_INSECURE_DEV=${ALLOW_INSECURE_DEV:-true}
export UVICORN_PORT=${UVICORN_PORT:-8000}
exec uvicorn app.main:app --host 0.0.0.0 --port "$UVICORN_PORT"
