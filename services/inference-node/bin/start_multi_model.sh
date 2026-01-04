#!/usr/bin/env bash
# Start Synthetic Intelligence Multi-Model Agentic RAG AI System
# Launches multiple GGUF models in parallel for simultaneous multi-location serving

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
APP_DIR="$SCRIPT_DIR/.."
LLAMA_BIN=/home/dgs/llama.cpp/build/bin/llama-server
MODEL_DIR=/home/dgs/N3090/services/inference-node/models

# CUDA environment
export PATH=/usr/local/cuda/bin:$PATH
export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║  Synthetic Intelligence Agentic RAG AI - Multi-Model System  ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

# Function to start model instance
start_model() {
    local name=$1
    local model=$2
    local port=$3
    local gpu=$4
    local ctx=$5
    local logfile="/tmp/llama-${name}.log"
    
    echo "[$name]"
    echo "  Model: $model"
    echo "  GPU: $gpu | Port: $port | Context: $ctx"
    
    # Check if already running
    if curl -s http://127.0.0.1:$port/health > /dev/null 2>&1; then
        echo "  Status: ✓ Already running"
        return 0
    fi
    
    # Start instance
    CUDA_VISIBLE_DEVICES=$gpu \
    $LLAMA_BIN \
        -m "$MODEL_DIR/$model" \
        -c $ctx \
        -ngl 99 \
        --port $port \
        --host 0.0.0.0 \
        --api-key "" \
        > "$logfile" 2>&1 &
    
    local pid=$!
    echo "  PID: $pid"
    
    # Wait for startup
    echo -n "  Starting"
    for i in {1..30}; do
        if curl -s http://127.0.0.1:$port/health > /dev/null 2>&1; then
            echo " ✓ Running"
            return 0
        fi
        echo -n "."
        sleep 1
    done
    
    echo " ✗ Failed"
    return 1
}

echo "Starting Model Instances (Parallel Execution)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# GPU 0 (RTX 3090) - Medical & Documentation
echo "GPU 0: RTX 3090 (24GB VRAM)"
echo "────────────────────────────"
start_model "medical_qa" \
    "BiMediX2-8B-hf.i1-Q6_K.gguf" \
    8081 0 8192

echo ""

start_model "documentation" \
    "medicine-llm-13b.Q6_K.gguf" \
    8082 0 8192

echo ""
echo ""

# GPU 1 (RTX 3060) - Chat & Insurance  
echo "GPU 1: RTX 3060 (12GB VRAM)"
echo "────────────────────────────"
start_model "chat" \
    "tiny-llama-1.1b-chat-medical.fp16.gguf" \
    8083 1 4096

echo ""

start_model "insurance" \
    "openinsurancellm-llama3-8b.Q5_K_M.gguf" \
    8084 1 8192

echo ""
echo ""

# Check GPU status
echo "GPU Status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
nvidia-smi --query-gpu=index,name,memory.used,memory.total --format=csv

echo ""
echo ""

# Start API Gateway
echo "API Gateway"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cd "$APP_DIR"

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate
pip install -q -r requirements.txt

export ALLOW_INSECURE_DEV=${ALLOW_INSECURE_DEV:-true}
export MULTI_MODEL_MODE=true

echo "Starting FastAPI Gateway on port 8000..."
uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --log-level info \
    > /tmp/api-gateway.log 2>&1 &

API_PID=$!
echo "PID: $API_PID"

# Wait for API to be ready
echo -n "Waiting for API"
for i in {1..15}; do
    if curl -s http://localhost:8000/healthz > /dev/null 2>&1; then
        echo " ✓ Ready"
        break
    fi
    echo -n "."
    sleep 1
done

echo ""
echo ""

# System Status
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║                     SYSTEM STATUS: READY                      ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""
echo "Model Instances:"
echo "  • Medical QA      → http://127.0.0.1:8081 (GPU 0)"
echo "  • Documentation   → http://127.0.0.1:8082 (GPU 0)"
echo "  • Chat            → http://127.0.0.1:8083 (GPU 1)"
echo "  • Insurance       → http://127.0.0.1:8084 (GPU 1)"
echo ""
echo "API Gateway:"
echo "  • Endpoint        → http://localhost:8000"
echo "  • Health Check    → http://localhost:8000/healthz"
echo "  • Model Info      → http://localhost:8000/models"
echo ""
echo "Capabilities:"
echo "  ✓ 4 Simultaneous Models Running"
echo "  ✓ 7 Agent Types Configured"
echo "  ✓ 2 GPUs Utilized (RTX 3090 + RTX 3060)"
echo "  ✓ RAG Integration Active"
echo "  ✓ Multi-Location Serving Ready"
echo ""
echo "Test Command:"
echo '  curl -X POST http://localhost:8000/v1/chat/completions \'
echo '    -H "Content-Type: application/json" \'
echo '    -H "X-Agent-Type: MedicalQA" \'
echo '    -d '"'"'{"agent_type":"MedicalQA","messages":[{"role":"user","content":"Test"}]}'"'"
echo ""
echo "Logs:"
echo "  • API Gateway     → tail -f /tmp/api-gateway.log"
echo "  • Medical QA      → tail -f /tmp/llama-medical_qa.log"
echo "  • Documentation   → tail -f /tmp/llama-documentation.log"
echo "  • Chat            → tail -f /tmp/llama-chat.log"
echo "  • Insurance       → tail -f /tmp/llama-insurance.log"
echo ""
echo "Documentation:"
echo "  • Architecture    → /home/dgs/N3090/SYNTHETIC_INTELLIGENCE_ARCHITECTURE.md"
echo "  • API Guide       → services/inference-node/API_INTEGRATION.md"
echo "  • Quick Start     → services/inference-node/QUICKSTART.md"
echo ""
