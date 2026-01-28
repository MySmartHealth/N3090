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
# ═══════════════════════════════════════════════════════════════════════════════
# TANDEM MODEL ARCHITECTURE:
#   Port 8080: BiMediX2-8B      (PRIMARY - All medical tasks)
#   Port 8081: MedPalm2-8B      (BACKUP - Fallback only)
#   Port 8082: Qwen-0.6B        (TANDEM - Quick responses)
#   Port 8084: OpenInsurance-8B (TANDEM - Insurance domain)
# ═══════════════════════════════════════════════════════════════════════════════
declare -a MODELS=(
    "BiMediX2|BiMediX2-8B-hf.i1-Q6_K.gguf|8080|4096|99"
    "MedPalm2|Llama-3.1-MedPalm2-imitate-8B-Instruct.Q6_K.gguf|8081|4096|99"
    "Qwen-0.6B|qwen-0.6b-medicaldataset-f16.gguf|8082|4096|99"
    "OpenInsurance|openinsurancellm-llama3-8b.Q5_K_M.gguf|8084|4096|99"
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
for port in 8080 8081 8082 8084; do
    if timeout 2 curl -s http://localhost:$port/health > /dev/null 2>&1; then
        case $port in
            8080) echo "✓ Port $port: BiMediX2 (PRIMARY) - OK" ;;
            8081) echo "✓ Port $port: MedPalm2 (BACKUP) - OK" ;;
            8082) echo "✓ Port $port: Qwen-0.6B (TANDEM) - OK" ;;
            8084) echo "✓ Port $port: OpenInsurance (TANDEM) - OK" ;;
        esac
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
