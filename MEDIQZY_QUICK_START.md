# Mediqzy.com LLM Integration - Quick Reference

## 30-Second Setup

### 1. Add Environment Variables
```bash
export EXTERNAL_LLM_ENABLED=true
export EXTERNAL_LLM_BASE_URL=https://api.mediqzy.com
export EXTERNAL_LLM_API_KEY=your-api-key-here
export EXTERNAL_LLM_MODEL=mediqzy-clinical
```

### 2. Start Service
```bash
cd /home/dgs/N3090/services/inference-node
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 3. Test It
```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Hello, how can you help?"}],
    "agent_type": "MedicalQA"
  }'
```

Response should show `"model": "mediqzy:mediqzy-clinical"` ✅

---

## Environment Variables Reference

| Variable | Required | Example | Description |
|----------|----------|---------|-------------|
| `EXTERNAL_LLM_ENABLED` | ✅ | `true` | Enable/disable external LLM routing |
| `EXTERNAL_LLM_PROVIDER` | ✅ | `mediqzy` | Provider name (mediqzy, openai, custom, etc.) |
| `EXTERNAL_LLM_BASE_URL` | ✅ | `https://api.mediqzy.com` | API endpoint (no trailing slash) |
| `EXTERNAL_LLM_API_KEY` | ✅ | `sk-xyz...` | Authentication token |
| `EXTERNAL_LLM_MODEL` | ✅ | `mediqzy-clinical` | Model identifier |
| `EXTERNAL_LLM_TEMPERATURE` | ❌ | `0.7` | Randomness (0=fixed, 1=creative), default 0.7 |
| `EXTERNAL_LLM_MAX_TOKENS` | ❌ | `2048` | Max response length, default unlimited |
| `EXTERNAL_LLM_TIMEOUT` | ❌ | `30` | Request timeout in seconds, default 30 |

---

## API Endpoint

**POST** `/v1/chat/completions` (OpenAI-compatible format)

### Request
```json
{
  "messages": [
    {"role": "system", "content": "You are a healthcare AI."},
    {"role": "user", "content": "What are the signs of heart disease?"}
  ],
  "agent_type": "MedicalQA",
  "temperature": 0.7,
  "max_tokens": 1024
}
```

### Response
```json
{
  "id": "cmpl-xyz",
  "created": 1704000000,
  "model": "mediqzy:mediqzy-clinical",
  "choices": [{
    "message": {
      "role": "assistant",
      "content": "Heart disease signs include chest pain, shortness of breath..."
    }
  }],
  "usage": {
    "prompt_tokens": 45,
    "completion_tokens": 120,
    "total_tokens": 165
  }
}
```

---

## Fallback Logic

```
Request arrives → External LLM enabled?
  ├─ YES → Try Mediqzy API
  │         ├─ Success ✅ → Return response
  │         └─ Error ❌ → Log & fallback to local
  │
  └─ NO → Use local model (vLLM, HF, etc.)
```

---

## Supported Providers

| Provider | Base URL Example | API Key Format | Model Example |
|----------|------------------|-----------------|---|
| **Mediqzy** | `https://api.mediqzy.com` | Bearer token | `mediqzy-clinical` |
| **OpenAI** | `https://api.openai.com` | `sk-...` | `gpt-4` |
| **Ollama (Local)** | `http://localhost:11434` | None | `mistral` |
| **LM Studio** | `http://localhost:1234` | None | `model-name` |

---

## Debugging

### Check if external LLM is enabled
```bash
grep "Routing to external LLM" logs/inference.log
```

### Verify API connectivity
```bash
curl -X POST https://api.mediqzy.com/v1/chat/completions \
  -H "Authorization: Bearer YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"mediqzy-clinical","messages":[{"role":"user","content":"test"}]}'
```

### View all external LLM logs
```bash
tail -f logs/inference.log | grep -i "external"
```

---

## Docker Deployment

### `.env` File
```env
EXTERNAL_LLM_ENABLED=true
EXTERNAL_LLM_PROVIDER=mediqzy
EXTERNAL_LLM_BASE_URL=https://api.mediqzy.com
EXTERNAL_LLM_API_KEY=your-secret-key
EXTERNAL_LLM_MODEL=mediqzy-clinical
EXTERNAL_LLM_TEMPERATURE=0.7
EXTERNAL_LLM_MAX_TOKENS=2048
EXTERNAL_LLM_TIMEOUT=30
```

### Docker Compose
```yaml
services:
  inference-node:
    image: n3090-inference:latest
    ports:
      - "8000:8000"
    env_file: .env
    restart: unless-stopped
```

### Run
```bash
docker-compose up -d
```

---

## Performance Tuning

### Optimize for Speed
```bash
EXTERNAL_LLM_TEMPERATURE=0.1      # More deterministic
EXTERNAL_LLM_MAX_TOKENS=512       # Shorter responses
EXTERNAL_LLM_TIMEOUT=15            # Faster timeout
```

### Optimize for Quality
```bash
EXTERNAL_LLM_TEMPERATURE=0.9      # More creative
EXTERNAL_LLM_MAX_TOKENS=4096      # Longer responses
EXTERNAL_LLM_TIMEOUT=60            # More patience
```

---

## Cost Tracking (OpenAI/Mediqzy)

Every response includes token usage:
```json
"usage": {
  "prompt_tokens": 45,      // Input tokens
  "completion_tokens": 120, // Output tokens
  "total_tokens": 165       // Total charged
}
```

Typical pricing: $0.001 - $0.1 per 1K tokens (varies by provider)

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Falls back to local every time | API key invalid | Verify `EXTERNAL_LLM_API_KEY` |
| Connection timeout | Service slow/down | Increase `EXTERNAL_LLM_TIMEOUT` |
| 404 error | Wrong base URL | Check `EXTERNAL_LLM_BASE_URL` |
| Model not found | Wrong model name | Verify `EXTERNAL_LLM_MODEL` |
| Always uses local | Not enabled | Set `EXTERNAL_LLM_ENABLED=true` |

---

## Files Modified

- `app/services/external_llm.py` - New external LLM client
- `app/main.py` - Updated chat endpoint to support routing
- `docs/EXTERNAL_LLM_INTEGRATION.md` - Full documentation

---

**Ready to use!** 🚀
