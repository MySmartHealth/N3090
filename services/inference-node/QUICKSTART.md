# Agentic AI Inference Node - Quick Start

## 🚀 Current Status

✅ **GPU-Accelerated** - llama.cpp with CUDA support  
✅ **Multi-Agent Ready** - 7 specialized agent types  
✅ **OpenAI-Compatible** - Standard API format  
✅ **Production-Ready** - Retry logic, health checks, error handling  

## Services Running

| Service | Port | Status | GPU Memory |
|---------|------|--------|------------|
| llama.cpp Server | 8080 | ✓ Running | 2.4 GB |
| FastAPI Inference Node | 8000 | ✓ Running | - |

**GPU:** NVIDIA GeForce RTX 3090 (24GB)

---

## Quick Commands

### Start Services
```bash
cd /home/dgs/N3090/services/inference-node
bash bin/start_agentic_ai.sh
```

### Health Check
```bash
curl http://localhost:8000/healthz | jq .
```

### Test Inference
```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-Agent-Type: MedicalQA" \
  -d '{
    "agent_type": "MedicalQA",
    "messages": [{"role": "user", "content": "What is diabetes?"}]
  }' | jq .
```

### Check GPU Usage
```bash
nvidia-smi
```

### View Logs
```bash
# llama.cpp server
tail -f /tmp/llama-server.log

# FastAPI application
tail -f /tmp/fastapi.log
```

---

## Agent Types & Use Cases

| Agent | Model | Use For |
|-------|-------|---------|
| `Chat` | Tiny-LLaMA-1B | Quick patient conversations |
| `Appointment` | Tiny-LLaMA-1B | Scheduling assistance |
| `Documentation` | Medicine-LLM-13B | Clinical documentation |
| `Billing` | OpenInsurance-LLaMA3-8B | Insurance & billing |
| `Claims` | OpenInsurance-LLaMA3-8B | Claims processing |
| `Monitoring` | Tiny-LLaMA-1B | System monitoring |
| `MedicalQA` | BiMediX2-8B | Medical questions |

---

## Integration Example

```python
import httpx

# Initialize client
client = httpx.Client(base_url="http://localhost:8000", timeout=120)

# Send request to agent
response = client.post(
    "/v1/chat/completions",
    headers={"X-Agent-Type": "MedicalQA"},
    json={
        "agent_type": "MedicalQA",
        "messages": [
            {"role": "user", "content": "Explain hypertension treatment"}
        ]
    }
)

# Get response
data = response.json()
answer = data["choices"][0]["message"]["content"]
print(f"Model: {data['model']}")
print(f"Answer: {answer}")
```

---

## Configuration

### Environment Variables

```bash
# In /home/dgs/N3090/services/inference-node/.env
LLAMA_CPP_SERVER=http://127.0.0.1:8080
UVICORN_PORT=8000
ALLOW_INSECURE_DEV=true  # Set to false in production
LLAMA_CPP_TIMEOUT=120
MODEL_MAX_RETRIES=3
```

### Switching Models

Edit `/home/dgs/N3090/services/inference-node/app/model_router.py`:

```python
AGENT_MODEL_MAP = {
    "MedicalQA": "bi-medix2",  # Change to different model
    # ... other agents
}
```

---

## Performance

- **Latency**: ~200-500ms per request
- **GPU Memory**: ~2.4GB (tiny-llama-1b)
- **Max Context**: 8192 tokens (model-dependent)
- **Concurrent**: 10 requests supported

---

## Troubleshooting

### llama.cpp not responding
```bash
# Restart llama.cpp server
pkill -f llama-server
cd /home/dgs/llama.cpp
export PATH=/usr/local/cuda/bin:$PATH
export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH
./build/bin/llama-server \
  -m /home/dgs/N3090/services/inference-node/models/tiny-llama-1.1b-chat-medical.fp16.gguf \
  -c 8192 -ngl 99 --port 8080 --host 0.0.0.0 &
```

### FastAPI not responding
```bash
# Restart FastAPI
pkill -f "uvicorn app.main"
cd /home/dgs/N3090/services/inference-node
source .venv/bin/activate
export LLAMA_CPP_SERVER=http://127.0.0.1:8080
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
```

### GPU not being used
```bash
# Check CUDA libraries
ldd /home/dgs/llama.cpp/build/bin/llama-server | grep cuda

# Should show CUDA libraries linked
```

---

## Next Steps

1. **See API_INTEGRATION.md** for detailed API documentation
2. **Configure JWT authentication** for production
3. **Set up PM2** for process management
4. **Add monitoring** with Prometheus/Grafana
5. **Implement load balancing** for multiple GPUs

---

## Support

- Documentation: `services/inference-node/API_INTEGRATION.md`
- Health endpoint: http://localhost:8000/healthz
- Models info: http://localhost:8000/models
