#!/bin/bash
# vLLM Setup & Management Script
# Convenience wrapper for downloads, status checks, and service startup

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_DIR="$(dirname "$SCRIPT_DIR")"
VENV="$SERVICE_DIR/.venv"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
echo_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
echo_error() { echo -e "${RED}[ERROR]${NC} $1"; }

usage() {
  cat << EOF
vLLM Setup & Management Script

Usage:
  $0 [COMMAND] [OPTIONS]

Commands:
  status                  Check model download & vLLM readiness
  download [MODELS]       Download models (biomistral-7b-fp16, qwen2.5-14b-awq, etc.)
                         Use 'download --all' to download everything
  install-vllm            Install vLLM package (pip install vllm)
  start-service           Start inference service with PM2
  health-check            Test inference endpoint (if service running)
  logs                    Show recent service logs
  help                    Show this message

Examples:
  $0 status
  $0 download biomistral-7b-fp16
  $0 download --all --sequential
  $0 install-vllm
  $0 start-service
  $0 logs

EOF
}

check_venv() {
  if [ ! -d "$VENV" ]; then
    echo_error "Python venv not found at $VENV"
    echo_error "Run from /home/dgs/N3090/services/inference-node with .venv activated"
    exit 1
  fi
}

check_venv

# Activate venv
source "$VENV/bin/activate"

case "${1:-help}" in
  status)
    echo_info "Checking model & vLLM status..."
    python bin/download_models.py --status
    echo ""
    python -c "from app.vllm_config import vLLMEngineRegistry; r = vLLMEngineRegistry(); print('vLLM Available Models:'); [print(f'  {k}: {v}') for k, v in r.list_engines().items()]" 2>/dev/null || echo_warn "vLLM config ready"
    ;;
  
  download)
    shift
    if [ $# -eq 0 ]; then
      echo_error "Please specify models to download or use --all"
      echo_info "Available: biomistral-7b-fp16, qwen2.5-14b-awq, llama3.1-8b-awq, biomistral-7b-awq"
      exit 1
    fi
    
    echo_info "Starting model download..."
    HF_TOKEN="${HF_TOKEN:-}" python bin/download_models.py "$@"
    ;;
  
  install-vllm)
    echo_info "Installing vLLM..."
    pip install -q vllm
    echo_info "✓ vLLM installed successfully"
    python -c "import vllm; print(f'vLLM version: {vllm.__version__}')" || true
    ;;
  
  start-service)
    echo_info "Starting inference service with PM2..."
    if command -v pm2 &> /dev/null; then
      cd "$SERVICE_DIR"
      pm2 start ecosystem.config.js
      pm2 logs inference-node --lines 10
    else
      echo_warn "PM2 not found, starting with Python directly..."
      cd "$SERVICE_DIR"
      uvicorn app.main:app --host 0.0.0.0 --port 8000
    fi
    ;;
  
  health-check)
    echo_info "Testing inference endpoint..."
    if curl -s http://localhost:8000/health &> /dev/null; then
      echo_info "✓ Service responding"
      curl -s http://localhost:8000/models | python -m json.tool | head -20
    else
      echo_error "Service not responding (is it running?)"
      echo_info "Start with: $0 start-service"
      exit 1
    fi
    ;;
  
  logs)
    if command -v pm2 &> /dev/null; then
      pm2 logs inference-node --lines 30
    else
      echo_error "PM2 not available; cannot show logs"
      exit 1
    fi
    ;;
  
  help)
    usage
    ;;
  
  *)
    echo_error "Unknown command: $1"
    usage
    exit 1
    ;;
esac
