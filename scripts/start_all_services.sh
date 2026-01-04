#!/bin/bash
# Start all model servers and API service

set -e

REPO_ROOT="/home/dgs/N3090"
INFERENCE_NODE="$REPO_ROOT/services/inference-node"
MODEL_PATH="$INFERENCE_NODE/models"
LLAMA_BIN="/home/dgs/llama.cpp/build/bin/llama-server"
LOG_DIR="/tmp/llm_logs"

# Create log directory
mkdir -p $LOG_DIR

echo "🚀 Starting Medical AI Inference System..."
echo "=========================================="

# Model configurations: name, model_file, port, context_size, gpu_layers
declare -a MODELS=(
    "Tiny-LLaMA|tiny-llama-1.1b-chat-medical.fp16.gguf|8080|2048|99"
    "BiMediX2|BiMediX2-8B-hf.i1-Q6_K.gguf|8081|8192|99"
    "Qwen-0.6B|qwen-0.6b-medicaldataset-f16.gguf|8082|4096|99"
    "Tiny-LLaMA-2|tiny-llama-1.1b-chat-medical.fp16.gguf|8083|4096|99"
    "OpenInsurance|openinsurancellm-llama3-8b.Q5_K_M.gguf|8084|8192|99"
    "BioMistral|BioMistral-Clinical-7B.Q8_0.gguf|8085|4096|35"
)

# Start each model server
for model_config in "${MODELS[@]}"; do
    IFS='|' read -r NAME MODEL PORT CONTEXT GPU_LAYERS <<< "$model_config"
    
    MODEL_FILE="$MODEL_PATH/$MODEL"
    LOG_FILE="$LOG_DIR/llama_$PORT.log"
    
    if [ ! -f "$MODEL_FILE" ]; then
        echo "⚠️  Model not found: $MODEL_FILE"
        continue
    fi
    
    # Check if port is already in use
    if nc -z localhost $PORT 2>/dev/null; then
        echo "✓ Port $PORT already in use ($(lsof -i :$PORT | tail -1 | awk '{print $1}'))"
        continue
    fi
    
    echo "Starting $NAME on port $PORT..."
    nohup "$LLAMA_BIN" \
        -m "$MODEL_FILE" \
        -c $CONTEXT \
        -ngl $GPU_LAYERS \
        --port $PORT \
        --host 0.0.0.0 \
        --api-key dev-key \
        > "$LOG_FILE" 2>&1 &
    
    sleep 1
done

echo ""
echo "⏳ Waiting for model servers to initialize (15 seconds)..."
sleep 15

# Check all ports
echo ""
echo "📊 Model Server Status:"
echo "======================"
for port in 8080 8081 8082 8083 8084 8085; do
    if timeout 2 curl -s http://localhost:$port/health > /dev/null 2>&1; then
        echo "✓ Port $port: OK"
    else
        echo "✗ Port $port: FAILED"
    fi
done

# Start FastAPI application
echo ""
echo "Starting FastAPI application on port 8000..."
cd "$INFERENCE_NODE"

# Load environment if available
if [ -f ".env.production" ]; then
    export $(cat .env.production | grep -v '^#' | xargs)
fi

# Start uvicorn
nohup python3 -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 4 \
    > "$LOG_DIR/api.log" 2>&1 &

sleep 2

echo "✓ FastAPI started on port 8000"
echo ""
echo "🎉 All services started successfully!"
echo ""
echo "Available endpoints:"
echo "  - API Documentation: http://localhost:8000/docs"
echo "  - Health Check: curl http://localhost:8000/health"
echo "  - Log files: $LOG_DIR/"
