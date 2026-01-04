#!/bin/bash
# AIDoctor GPU Test Launcher
set -e

echo "🚀 Starting AIDoctor GPU Performance Test..."
echo ""

# Kill any existing servers
pkill -9 -f "uvicorn" || true
sleep 2

# Start the server
echo "📡 Starting inference server with GPU support..."
cd /home/dgs/N3090/services/inference-node

# Start in background
ALLOW_INSECURE_DEV=true nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/aindoctor_server.log 2>&1 &
SERVER_PID=$!
echo "   Server PID: $SERVER_PID"

# Wait for server to start
echo "⏳ Waiting for server to initialize (30 seconds)..."
for i in {1..30}; do
    if curl -s http://localhost:8000/healthz > /dev/null 2>&1; then
        echo "✅ Server is ready!"
        sleep 2
        break
    fi
    echo -n "."
    sleep 1
done

echo ""
echo "📊 GPU Info:"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader

echo ""
echo "🧪 Starting AIDoctor tests..."
python3 test_aindoctor_gpu.py

echo ""
echo "✅ Test complete. Cleaning up..."
kill $SERVER_PID 2>/dev/null || true
