#!/usr/bin/env bash
# Start both llama.cpp server and FastAPI inference node
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
APP_DIR="$SCRIPT_DIR/.."

# Configuration
LLAMA_SERVER=${LLAMA_CPP_SERVER:-http://127.0.0.1:8080}
LLAMA_PORT=8080
FASTAPI_PORT=${UVICORN_PORT:-8000}
MODEL=${MODEL:-$APP_DIR/models/tiny-llama-1.1b-chat-medical.fp16.gguf}
GPU_LAYERS=${LLAMA_GPU_LAYERS:-99}
CTX_SIZE=${LLAMA_CTX:-8192}

echo "==================================="
echo "Starting Agentic AI Inference Node"
echo "==================================="

# Setup CUDA environment
export PATH=/usr/local/cuda/bin:$PATH
export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH

# Check if llama.cpp server is already running
if curl -s $LLAMA_SERVER/health > /dev/null 2>&1; then
    echo "✓ llama.cpp server already running at $LLAMA_SERVER"
else
    echo "Starting llama.cpp server..."
    echo "  Model: $MODEL"
    echo "  GPU Layers: $GPU_LAYERS"
    echo "  Context Size: $CTX_SIZE"
    
    cd /home/dgs/llama.cpp
    ./build/bin/llama-server \
        -m "$MODEL" \
        -c $CTX_SIZE \
        -ngl $GPU_LAYERS \
        --port $LLAMA_PORT \
        --host 0.0.0.0 \
        --api-key "" \
        > /tmp/llama-server.log 2>&1 &
    
    LLAMA_PID=$!
    echo "  PID: $LLAMA_PID"
    
    # Wait for server to be ready
    echo -n "  Waiting for server to start"
    for i in {1..30}; do
        if curl -s http://127.0.0.1:$LLAMA_PORT/health > /dev/null 2>&1; then
            echo " ✓"
            break
        fi
        echo -n "."
        sleep 1
    done
fi

# Start FastAPI application
echo ""
echo "Starting FastAPI Inference Node..."
echo "  Port: $FASTAPI_PORT"

cd "$APP_DIR"
python3 -m venv .venv 2>/dev/null || true
source .venv/bin/activate
pip install -q -r requirements.txt

export LLAMA_CPP_SERVER="http://127.0.0.1:$LLAMA_PORT"
export ALLOW_INSECURE_DEV=${ALLOW_INSECURE_DEV:-true}

uvicorn app.main:app \
    --host 0.0.0.0 \
    --port $FASTAPI_PORT \
    --log-level info

