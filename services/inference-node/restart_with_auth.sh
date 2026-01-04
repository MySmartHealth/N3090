#!/bin/bash
# Restart all llama-server instances with API key authentication

echo "🔄 Restarting llama-server instances with API keys..."
echo ""

# Source API keys
source .api_keys.env

# Stop all existing llama-server instances
echo "🛑 Stopping existing instances..."
pkill -f "llama-server" || true
sleep 2

# Check if any are still running
if pgrep -f "llama-server" > /dev/null; then
    echo "⚠️  Some instances still running, force killing..."
    pkill -9 -f "llama-server"
    sleep 2
fi

echo "✅ All instances stopped"
echo ""

# Model paths
MODEL_DIR="/home/dgs/N3090/services/inference-node/models"
LLAMA_SERVER="/home/dgs/llama.cpp/build/bin/llama-server"

# Create logs directory if it doesn't exist
mkdir -p logs

# Start model instances with API keys
echo "🚀 Starting llama-server instances with authentication..."
echo ""

# Port 8080: Tiny-LLaMA-1B (GPU 0) - Legacy/Chat
nohup $LLAMA_SERVER \
  -m "$MODEL_DIR/tiny-llama-1.1b-chat-medical.fp16.gguf" \
  -c 2048 -ngl 99 \
  --port 8080 --host 0.0.0.0 \
  --api-key "$API_KEY_TINY_LLAMA_1B_8080" \
  > logs/llama-8080.log 2>&1 &
echo "✅ Started Tiny-LLaMA-1B on port 8080 (GPU 0)"

# Port 8081: BiMediX2-8B (GPU 0) - MedicalQA
nohup env CUDA_VISIBLE_DEVICES=0 $LLAMA_SERVER \
  -m "$MODEL_DIR/BiMediX2-8B-hf.i1-Q6_K.gguf" \
  -c 8192 -ngl 99 \
  --port 8081 --host 0.0.0.0 \
  --api-key "$API_KEY_BIMEDIX2_8081" \
  > logs/llama-8081.log 2>&1 &
echo "✅ Started BiMediX2-8B on port 8081 (GPU 0)"

# Port 8082: Medicine-LLM-13B (GPU 0) - Documentation [NEW]
nohup env CUDA_VISIBLE_DEVICES=0 $LLAMA_SERVER \
  -m "$MODEL_DIR/medicine-llm-13b.Q6_K.gguf" \
  -c 8192 -ngl 99 \
  --port 8082 --host 0.0.0.0 \
  --api-key "$API_KEY_MEDICINE_LLM_8082" \
  > logs/llama-8082.log 2>&1 &
echo "✅ Started Medicine-LLM-13B on port 8082 (GPU 0) [NEW]"

# Port 8083: Tiny-LLaMA-1B (GPU 1) - Monitoring/Appointment
nohup env CUDA_VISIBLE_DEVICES=1 $LLAMA_SERVER \
  -m "$MODEL_DIR/tiny-llama-1.1b-chat-medical.fp16.gguf" \
  -c 4096 -ngl 99 \
  --port 8083 --host 0.0.0.0 \
  --api-key "$API_KEY_TINY_LLAMA_1B_8083" \
  > logs/llama-8083.log 2>&1 &
echo "✅ Started Tiny-LLaMA-1B on port 8083 (GPU 1)"

# Port 8084: OpenInsurance-8B (GPU 1) - Billing/Claims
nohup env CUDA_VISIBLE_DEVICES=1 $LLAMA_SERVER \
  -m "$MODEL_DIR/openinsurancellm-llama3-8b.Q5_K_M.gguf" \
  -c 8192 -ngl 99 \
  --port 8084 --host 0.0.0.0 \
  --api-key "$API_KEY_OPENINSURANCE_8084" \
  > logs/llama-8084.log 2>&1 &
echo "✅ Started OpenInsurance-8B on port 8084 (GPU 1)"

# Port 8085: BioMistral-7B (GPU 0) - Clinical
nohup env CUDA_VISIBLE_DEVICES=0 $LLAMA_SERVER \
  -m "$MODEL_DIR/BioMistral-Clinical-7B.Q8_0.gguf" \
  -c 8192 -ngl 99 \
  --port 8085 --host 0.0.0.0 \
  --api-key "$API_KEY_BIOMISTRAL_8085" \
  > logs/llama-8085.log 2>&1 &
echo "✅ Started BioMistral-7B on port 8085 (GPU 0)"

echo ""
echo "⏳ Waiting for servers to initialize (10 seconds)..."
sleep 10

echo ""
echo "📊 Server Status:"
ps aux | grep llama-server | grep -v grep | awk '{printf "  PID %-6s Port %s\n", $2, $(NF-3)}'

echo ""
echo "🔍 Health Check:"
for port in 8080 8081 8082 8083 8084 8085; do
    status=$(curl -s http://localhost:$port/health 2>/dev/null | grep -o '"status":"ok"' || echo "not ready")
    if [[ "$status" == *"ok"* ]]; then
        echo "  ✅ Port $port: Ready"
    else
        echo "  ⏳ Port $port: Starting..."
    fi
done

echo ""
echo "✅ All servers restarted with API key authentication!"
echo "🔐 API keys stored in .api_keys.env"
