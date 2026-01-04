#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
APP_DIR="$SCRIPT_DIR/.."
cd "$APP_DIR"

# Ensure Python & pip
if ! command -v python3 >/dev/null 2>&1; then
  echo "[ERROR] python3 not found. Please install Python 3." >&2
  exit 1
fi

# Try pip
if ! python3 -m pip --version >/dev/null 2>&1; then
  echo "[WARN] pip for Python 3 not found; attempting ensurepip..." >&2
  if python3 -m ensurepip --upgrade >/dev/null 2>&1; then
    echo "[INFO] ensurepip succeeded." >&2
  else
    echo "[ERROR] pip unavailable and ensurepip failed. On Debian/Ubuntu: sudo apt install -y python3-pip python3-venv" >&2
    exit 1
  fi
fi

# Create venv if missing
if [ ! -d ".venv" ]; then
  if ! python3 -m venv .venv >/dev/null 2>&1; then
    echo "[WARN] python3-venv not available; proceeding without venv." >&2
  fi
fi

# Activate venv
if [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
else
  echo "[INFO] Running without virtualenv; using system Python." >&2
fi

# Install deps
pip install --upgrade pip
pip install -r requirements.txt

# Run uvicorn with guardrails
exec uvicorn app.main:app --host 0.0.0.0 --port "${UVICORN_PORT:-8000}" --no-access-log
