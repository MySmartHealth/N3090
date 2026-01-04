# Backend & Middleware Implementation Summary

## ✅ Completed Components

### 1. Model Router Backend
**File**: [services/inference-node/app/model_router.py](../services/inference-node/app/model_router.py)

**Features**:
- Agent-to-model mapping with GPU-aware scheduling
- Multi-backend support (vLLM, llama.cpp, transformers)
- VRAM tracking and capacity management
- Horizontal scaling ready

**Model Registry**:
| Model | Agent(s) | GPU | VRAM | Backend |
|-------|----------|-----|------|---------|
| BiMediX2 | MedicalQA | 0 (3090) | 20GB | vLLM |
| Mixtral 8x7B | Claims, Billing | 0 (3090) | 14GB | vLLM |
| Qwen 2.5 14B | Documentation | 0 (3090) | 12GB | vLLM |
| LLaMA 3.1 8B | Chat, Appointment, Monitoring | 1 (3060) | 6GB | vLLM |
| ChatDoctor | - | 1 (3060) | 5GB | llama.cpp |

**Current State**: Stub mode with template responses
**Next**: Integrate actual vLLM/llama.cpp inference engines

---

### 2. RAG Engine Backend
**File**: [services/inference-node/app/rag_engine.py](../services/inference-node/app/rag_engine.py)

**Features**:
- Embedding generation (BGE-Large stub)
- In-memory vector store with cosine similarity search
- Multiple document stores:
  - `medical_literature`: Clinical guidelines, research
  - `insurance_policies`: Coverage rules, pre-auth requirements
  - `clinical_guidelines`: Standard of care documents
- Automatic context injection for agent prompts

**Current State**: Deterministic stub embeddings, 3 sample documents loaded
**Next**: Integrate BGE-Large/BioMedLM models, add persistent vector DB (Qdrant/Weaviate)

---

### 3. Middleware Stack
**File**: [services/inference-node/app/middleware.py](../services/inference-node/app/middleware.py)

**Layers** (applied in order):

#### SecurityHeadersMiddleware
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: no-referrer`
- `Strict-Transport-Security: max-age=31536000`

#### ErrorHandlingMiddleware
- Catches all exceptions
- Sanitizes error responses (no internal stack traces)
- Logs full errors with request IDs

#### AuditEnrichmentMiddleware
- Generates request IDs (`X-Request-ID`)
- Adds timestamps (`X-Timestamp`)
- Tracks client IPs (non-PHI)
- Logs all requests with audit context

#### PolicyEnforcementMiddleware
- Validates agent types against allowlist
- Enforces agent-specific token limits:
  - Chat: 1024 tokens
  - Documentation: 4096 tokens
  - Claims/Billing: 2048 tokens
- Attaches policy context to request state

#### RateLimitMiddleware
- Per-IP + per-agent rate limiting
- Default: 100 requests per 60 seconds
- Sliding window implementation
- Returns `HTTP 429` when exceeded

---

## API Enhancements

### New Endpoints

#### `GET /models`
Returns model registry and agent mappings.

**Response**:
```json
{
  "models": {
    "bimedix2": {
      "name": "BiMediX2",
      "backend": "vllm",
      "gpu_ids": [0],
      "vram_gb": 20.0,
      "max_context": 8192
    },
    ...
  },
  "agent_mapping": {
    "Chat": "llama-8b",
    "Documentation": "qwen-14b",
    "Claims": "mixtral-8x7b",
    ...
  }
}
```

#### `POST /evidence/retrieve`
RAG-based evidence retrieval.

**Request**:
```json
{
  "query": "acute cough",
  "store": "medical_literature",
  "top_k": 5
}
```

**Response**:
```json
{
  "query": "acute cough",
  "store": "medical_literature",
  "results": [
    {
      "rank": 1,
      "score": 0.87,
      "content": "Acute cough is typically caused by...",
      "metadata": {"source": "clinical_guidelines", "year": 2023}
    }
  ]
}
```

### Enhanced `POST /v1/chat/completions`

**New Features**:
- Automatic RAG context injection for Documentation, MedicalQA, Claims, Billing agents
- Model router integration (GPU-aware scheduling)
- Enhanced audit logging with model used, inference time, RAG usage
- Policy flags in response

**Request**:
```json
{
  "agent_type": "MedicalQA",
  "messages": [
    {"role": "user", "content": "What causes acute cough?"}
  ]
}
```

**Response**:
```json
{
  "id": "cmpl-...",
  "model": "BiMediX2",
  "choices": [{
    "message": {
      "role": "assistant",
      "content": "[BiMediX2 on GPU 0]\n..."
    }
  }],
  "policy": {
    "agent_type": "MedicalQA",
    "draft_only": true,
    "side_effects": false
  }
}
```

**Audit Log**:
```
AUDIT req_id=req-123 resp_id=cmpl-456 agent=MedicalQA 
prompt_hash=abc123... model=BiMediX2 created=1766677657 
inference_time=0.234s rag_used=True
```

---

## Architecture Flow

```
User Request
    ↓
SecurityHeadersMiddleware (add headers)
    ↓
ErrorHandlingMiddleware (catch exceptions)
    ↓
AuditEnrichmentMiddleware (request ID, timestamp)
    ↓
PolicyEnforcementMiddleware (validate agent, set limits)
    ↓
RateLimitMiddleware (check rate limit)
    ↓
FastAPI Route Handler
    ↓
JWT Verification (if configured)
    ↓
RAG Engine (retrieve context if applicable)
    ↓
Model Router (route to appropriate model/GPU)
    ↓
Inference (stub or real backend)
    ↓
Audit Logging (hash, metadata, no PHI)
    ↓
Response + Headers
```

---

## Compliance & Security

### PHI Protection
- ✅ No raw PHI in logs (SHA256 hashes only)
- ✅ No PHI persistence on local disk
- ✅ Request-scoped memory only
- ✅ Middleware sanitizes error messages

### Audit Trail
- ✅ Every request has unique ID
- ✅ Model used, inference time tracked
- ✅ RAG usage flagged
- ✅ Policy constraints logged
- ✅ Immutable audit log format

### Rate Limiting & DoS Protection
- ✅ Per-IP + per-agent limits
- ✅ Configurable thresholds
- ✅ Graceful HTTP 429 responses

### Security Headers
- ✅ HSTS for HTTPS enforcement
- ✅ XSS protection
- ✅ Clickjacking prevention (X-Frame-Options)
- ✅ MIME sniffing prevention

---

## Testing

**Full test suite**: [BACKEND_TESTS.md](BACKEND_TESTS.md)

**Quick smoke test**:
```bash
# Health
curl -sS http://localhost:8000/healthz

# Models
curl -sS http://localhost:8000/models | jq '.agent_mapping'

# Chat agent
curl -sS http://localhost:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -H 'X-Agent-Type: Chat' \
  -d '{"agent_type":"Chat","messages":[{"role":"user","content":"Hello"}]}' | jq '.model'

# Evidence retrieval
curl -sS http://localhost:8000/evidence/retrieve \
  -X POST \
  -H 'Content-Type: application/json' \
  -d '{"query":"cough","top_k":2}' | jq '.results[].content'
```

---

## Next Steps

### Immediate (Integration Ready)
1. **vLLM Backend**: Replace stub in `ModelRouter._stub_generate()` with vLLM engine calls
2. **BGE-Large Embeddings**: Replace stub in `EmbeddingEngine.encode()` with actual model
3. **Persistent Vector Store**: Integrate Qdrant/Weaviate for RAG engine
4. **AWS Control Plane**: Connect to Step Functions for workflow orchestration

### Short-term (Scaling)
1. **Multi-node Registry**: Implement heartbeat service for GPU node discovery
2. **Load Balancing**: Add AWS-side scheduler for routing requests across nodes
3. **Model Warm-up**: Pre-load models on node startup to reduce cold-start latency
4. **Metrics**: Prometheus endpoints for GPU utilization, request rates, inference times

### Long-term (Production)
1. **Distributed Tracing**: OpenTelemetry integration
2. **A/B Testing**: Model version routing and performance comparison
3. **Auto-scaling**: Dynamic node provisioning based on queue depth
4. **Multi-region**: Replicate nodes across AWS regions for DR

---

## File Structure

```
services/inference-node/
├── app/
│   ├── __init__.py           # Package init
│   ├── main.py               # FastAPI app + routes
│   ├── model_router.py       # Model routing & GPU scheduling
│   ├── rag_engine.py         # RAG + embeddings + vector store
│   └── middleware.py         # Rate limit, policy, audit, security
├── bin/
│   └── serve.sh              # Start script
├── ecosystem.config.js       # PM2 config
├── requirements.txt          # Python deps
└── README.md                 # Quick start
```

---

**Status**: ✅ Backend & middleware complete and tested. Ready for model integration and AWS orchestration.
