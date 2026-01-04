# Backend & Middleware Test Suite

## Quick Test Commands

### Health Check
```bash
curl -sS http://localhost:8000/healthz | jq .
```

### Model Registry
```bash
curl -sS http://localhost:8000/models | jq '.agent_mapping'
```

### Agent Tests

#### Chat Agent (LLaMA 8B, GPU 1)
```bash
curl -sS 'http://localhost:8000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -H 'X-Agent-Type: Chat' \
  -d '{
    "agent_type": "Chat",
    "messages": [{"role":"user","content":"Hello"}]
  }' | jq '.choices[0].message.content'
```

#### MedicalQA Agent (BiMediX2, GPU 0, with RAG)
```bash
curl -sS 'http://localhost:8000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -H 'X-Agent-Type: MedicalQA' \
  -d '{
    "agent_type": "MedicalQA",
    "messages": [{"role":"user","content":"What causes acute cough?"}]
  }' | jq '.model, .choices[0].message.content'
```

#### Claims Agent (Mixtral 8x7B, GPU 0, with RAG)
```bash
curl -sS 'http://localhost:8000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -H 'X-Agent-Type: Claims' \
  -d '{
    "agent_type": "Claims",
    "messages": [{"role":"user","content":"Review claim for procedure code 99213"}]
  }' | jq '.model, .policy'
```

#### Documentation Agent (Qwen 14B, GPU 0, with RAG)
```bash
curl -sS 'http://localhost:8000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -H 'X-Agent-Type: Documentation' \
  -d '{
    "agent_type": "Documentation",
    "messages": [{"role":"user","content":"Summarize patient with mild cough"}]
  }' | jq '.model'
```

### Evidence Retrieval
```bash
# Medical literature
curl -sS 'http://localhost:8000/evidence/retrieve' \
  -X POST \
  -H 'Content-Type: application/json' \
  -d '{"query":"acute cough","store":"medical_literature","top_k":2}' | jq '.results'

# Insurance policies
curl -sS 'http://localhost:8000/evidence/retrieve' \
  -X POST \
  -H 'Content-Type: application/json' \
  -d '{"query":"pre-authorization","store":"insurance_policies","top_k":1}' | jq '.results'
```

### Middleware Tests

#### Rate Limiting
```bash
# Send 105 requests rapidly (should hit 100/min limit)
for i in {1..105}; do
  curl -sS 'http://localhost:8000/v1/chat/completions' \
    -H 'Content-Type: application/json' \
    -H 'X-Agent-Type: Chat' \
    -d '{"agent_type":"Chat","messages":[{"role":"user","content":"test"}]}' &
done
wait
```

#### Policy Enforcement
```bash
# Invalid agent type (should fail)
curl -sS 'http://localhost:8000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -H 'X-Agent-Type: InvalidAgent' \
  -d '{"agent_type":"InvalidAgent","messages":[{"role":"user","content":"test"}]}'
```

#### Audit Headers
```bash
curl -sS 'http://localhost:8000/v1/chat/completions' \
  -H 'Content-Type: application/json' \
  -H 'X-Agent-Type: Chat' \
  -d '{"agent_type":"Chat","messages":[{"role":"user","content":"test"}]}' \
  -i | grep -E 'X-Request-ID|X-Timestamp'
```

## Backend Components

### Model Router
- **Location**: `app/model_router.py`
- **Function**: Maps agents to models, manages GPU assignments
- **Current**: Stub mode, returns template responses
- **Next**: Integrate vLLM/llama.cpp backends

### RAG Engine
- **Location**: `app/rag_engine.py`
- **Function**: Embeddings, vector search, evidence retrieval
- **Current**: In-memory vector store with deterministic stub embeddings
- **Next**: Integrate BGE-Large/BioMedLM models, persistent vector DB

### Middleware
- **Location**: `app/middleware.py`
- **Layers**:
  - `SecurityHeadersMiddleware`: HSTS, CSP headers
  - `ErrorHandlingMiddleware`: Sanitized error responses
  - `AuditEnrichmentMiddleware`: Request ID, timestamps
  - `PolicyEnforcementMiddleware`: Agent validation, token limits
  - `RateLimitMiddleware`: 100 req/min per IP+agent

## Expected Outputs

### Chat Agent Response
```json
{
  "model": "LLaMA-3.1-8B",
  "choices": [{
    "message": {
      "content": "[LLaMA-3.1-8B on GPU 1]\nAgent: Chat\n..."
    }
  }],
  "policy": {
    "agent_type": "Chat",
    "draft_only": true,
    "side_effects": false
  }
}
```

### Evidence Retrieval Response
```json
{
  "query": "acute cough",
  "store": "medical_literature",
  "results": [{
    "rank": 1,
    "score": 0.87,
    "content": "Acute cough is typically caused by...",
    "metadata": {"source": "clinical_guidelines"}
  }]
}
```
