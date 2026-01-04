# Agentic AI API Integration Guide

Production-ready inference node for agentic AI applications with GPU-accelerated GGUF models via llama.cpp.

## Base URL

```
http://your-server:8000
```

## Authentication

### Development Mode
Set `ALLOW_INSECURE_DEV=true` to bypass JWT authentication.

### Production Mode
Include JWT bearer token in requests:
```bash
Authorization: Bearer <your-jwt-token>
```

## Endpoints

### 1. Health Check
Check service and backend connectivity status.

**Request:**
```bash
GET /healthz
```

**Response:**
```json
{
  "status": "ok",
  "ts": 1735977600,
  "backends": {
    "llama_cpp": {
      "status": "connected",
      "url": "http://127.0.0.1:8080"
    }
  }
}
```

---

### 2. Model Information
Get available models and agent mappings.

**Request:**
```bash
GET /models
```

**Response:**
```json
{
  "models": {
    "bi-medix2": {
      "name": "BiMediX2-8B (Q6_K gguf)",
      "backend": "llama_cpp",
      "gpu_ids": [0],
      "vram_gb": 10.0,
      "max_context": 8192
    },
    "tiny-llama-1b": {
      "name": "Tiny-LLaMA 1.1B Chat Medical",
      "backend": "llama_cpp",
      "gpu_ids": [1],
      "vram_gb": 2.0,
      "max_context": 4096
    }
  },
  "agent_mapping": {
    "Chat": "tiny-llama-1b",
    "MedicalQA": "bi-medix2",
    "Documentation": "medicine-llm-13b",
    "Billing": "openins-llama3-8b",
    "Claims": "openins-llama3-8b"
  }
}
```

---

### 3. Chat Completions (OpenAI-Compatible)
Generate AI responses for different agent types.

**Request:**
```bash
POST /v1/chat/completions
Content-Type: application/json
X-Agent-Type: MedicalQA

{
  "agent_type": "MedicalQA",
  "messages": [
    {
      "role": "user",
      "content": "What are the symptoms of diabetes?"
    }
  ],
  "constraints": {
    "mode": "draft-only"
  }
}
```

**Response:**
```json
{
  "id": "cmpl-a1b2c3d4e5f6",
  "object": "chat.completion",
  "created": 1735977600,
  "model": "BiMediX2-8B (Q6_K gguf)",
  "choices": [
    {
      "index": 0,
      "finish_reason": "stop",
      "message": {
        "role": "assistant",
        "content": "Common symptoms of diabetes include increased thirst, frequent urination, unexplained weight loss, fatigue, blurred vision, and slow-healing sores..."
      }
    }
  ],
  "usage": {
    "prompt_tokens": 45,
    "completion_tokens": 128,
    "total_tokens": 173
  },
  "policy": {
    "agent_type": "MedicalQA",
    "constraints_mode": "draft-only",
    "draft_only": true,
    "side_effects": false
  }
}
```

---

### 4. Evidence Retrieval (RAG)
Retrieve contextual evidence from knowledge bases.

**Request:**
```bash
POST /evidence/retrieve
Content-Type: application/json

{
  "query": "diabetes treatment guidelines",
  "store": "medical_literature",
  "top_k": 3
}
```

**Response:**
```json
{
  "query": "diabetes treatment guidelines",
  "store": "medical_literature",
  "results": [
    {
      "rank": 1,
      "score": 0.89,
      "content": "Type 2 diabetes management involves lifestyle modifications, metformin as first-line therapy...",
      "metadata": {
        "source": "ADA_Guidelines_2024",
        "doc_id": "diabetes_001"
      }
    }
  ]
}
```

---

## Available Agent Types

| Agent | Purpose | Model | Use Case |
|-------|---------|-------|----------|
| `Chat` | Patient interaction | Tiny-LLaMA-1B | Fast conversational responses |
| `Appointment` | Scheduling | Tiny-LLaMA-1B | Appointment booking/management |
| `Documentation` | Medical records | Medicine-LLM-13B | Clinical documentation |
| `Billing` | Insurance queries | OpenInsurance-LLaMA3-8B | Billing and payment |
| `Claims` | Claims processing | OpenInsurance-LLaMA3-8B | Insurance claims |
| `Monitoring` | System monitoring | Tiny-LLaMA-1B | Lightweight monitoring |
| `MedicalQA` | Medical Q&A | BiMediX2-8B | Specialized medical queries |

---

## Integration Examples

### Python (httpx)
```python
import httpx

API_BASE = "http://localhost:8000"

def chat_completion(agent_type: str, message: str):
    response = httpx.post(
        f"{API_BASE}/v1/chat/completions",
        headers={"X-Agent-Type": agent_type},
        json={
            "agent_type": agent_type,
            "messages": [{"role": "user", "content": message}]
        },
        timeout=120.0
    )
    return response.json()

# Example usage
result = chat_completion("MedicalQA", "What is hypertension?")
print(result["choices"][0]["message"]["content"])
```

### JavaScript/Node.js
```javascript
const API_BASE = "http://localhost:8000";

async function chatCompletion(agentType, message) {
  const response = await fetch(`${API_BASE}/v1/chat/completions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Agent-Type": agentType
    },
    body: JSON.stringify({
      agent_type: agentType,
      messages: [{ role: "user", content: message }]
    })
  });
  return response.json();
}

// Example usage
chatCompletion("MedicalQA", "What is hypertension?")
  .then(data => console.log(data.choices[0].message.content));
```

### cURL
```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-Agent-Type: MedicalQA" \
  -d '{
    "agent_type": "MedicalQA",
    "messages": [
      {"role": "user", "content": "What is hypertension?"}
    ]
  }'
```

---

## Configuration

### Environment Variables

```bash
# API Server
UVICORN_PORT=8000                    # API server port
ALLOW_INSECURE_DEV=false             # Enable dev mode (no JWT)

# Backend
LLAMA_CPP_SERVER=http://127.0.0.1:8080   # llama.cpp server URL
LLAMA_CPP_TIMEOUT=120                     # Request timeout (seconds)
MODEL_MAX_RETRIES=3                       # Retry attempts

# Security
JWT_SECRET=your-secret-key            # JWT signing secret
JWT_ISSUER=inference-node            # JWT issuer
JWT_AUDIENCE=agentic-ai-platform     # JWT audience

# Performance
RATE_LIMIT_REQUESTS=100              # Max requests per window
RATE_LIMIT_WINDOW=60                 # Window duration (seconds)
```

---

## Error Handling

### Common Error Codes

| Status Code | Meaning | Resolution |
|-------------|---------|------------|
| 400 | Bad Request | Check agent_type and message format |
| 401 | Unauthorized | Provide valid JWT token |
| 429 | Rate Limited | Reduce request frequency |
| 500 | Server Error | Check backend connectivity |
| 503 | Service Unavailable | Backend model server offline |

### Error Response Format
```json
{
  "detail": "Invalid or unsupported agent type",
  "status_code": 400
}
```

---

## Performance Characteristics

- **Latency**: 100-500ms per request (GPU-accelerated)
- **Throughput**: ~10-50 requests/second (model-dependent)
- **Context Window**: 4096-8192 tokens (model-dependent)
- **Max Concurrent**: 10 requests (configurable)

---

## Best Practices

1. **Use appropriate agent types** for each task
2. **Keep messages concise** for faster responses
3. **Implement retry logic** with exponential backoff
4. **Monitor health endpoint** for backend status
5. **Set reasonable timeouts** (60-120 seconds)
6. **Cache frequent queries** when possible
7. **Use RAG endpoints** for knowledge-intensive tasks

---

## Support & Monitoring

### Health Monitoring
```bash
# Check overall health
curl http://localhost:8000/healthz

# Check GPU utilization
nvidia-smi

# View llama.cpp logs
tail -f /tmp/llama-server.log
```

### Logs Location
- **FastAPI**: stdout/stderr
- **llama.cpp**: `/tmp/llama-server.log`
- **Audit logs**: Application logs (PHI-safe hashes only)
