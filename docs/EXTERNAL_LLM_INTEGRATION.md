# External LLM Integration Guide (Mediqzy.com)

Connect your N3090 inference node to external LLM services like Mediqzy.com, OpenAI, or any OpenAI-compatible API.

## Quick Start

### 1. Environment Variables

Add these to your `.env` file or deployment configuration:

```bash
# Enable external LLM routing
EXTERNAL_LLM_ENABLED=true

# Mediqzy.com Configuration Example
EXTERNAL_LLM_PROVIDER=mediqzy
EXTERNAL_LLM_BASE_URL=https://api.mediqzy.com  # Remove trailing slash
EXTERNAL_LLM_API_KEY=your-api-key-here
EXTERNAL_LLM_MODEL=mediqzy-clinical  # or whatever model name Mediqzy exposes

# Optional settings
EXTERNAL_LLM_TEMPERATURE=0.7        # Default: 0.7 (0.0 = deterministic, 1.0 = creative)
EXTERNAL_LLM_MAX_TOKENS=2048        # Default: None (no limit)
EXTERNAL_LLM_TIMEOUT=30             # Default: 30 seconds
```

### 2. Start the Application

```bash
cd /home/dgs/N3090/services/inference-node

# If using .env file
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Or if setting env vars directly:
export EXTERNAL_LLM_ENABLED=true
export EXTERNAL_LLM_BASE_URL=https://api.mediqzy.com
export EXTERNAL_LLM_API_KEY=your-key
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 3. Test the Integration

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "system", "content": "You are a medical expert."},
      {"role": "user", "content": "What are the symptoms of diabetes?"}
    ],
    "agent_type": "MedicalQA",
    "temperature": 0.7
  }'
```

Expected response:
```json
{
  "id": "cmpl-...",
  "created": 1704000000,
  "model": "mediqzy:mediqzy-clinical",
  "choices": [{
    "message": {
      "role": "assistant",
      "content": "Diabetes symptoms include..."
    }
  }],
  "usage": {
    "prompt_tokens": 50,
    "completion_tokens": 100,
    "total_tokens": 150
  }
}
```

## Supported External LLM Providers

### OpenAI-Compatible (Most Common)
- **Mediqzy.com** - Healthcare-focused LLM platform
- **OpenAI** - Use `EXTERNAL_LLM_BASE_URL=https://api.openai.com`
- **Ollama** - Local LLM server: `https://localhost:11434`
- **LM Studio** - Local inference: `http://localhost:1234`
- **vLLM** - Inference framework
- **HuggingFace Text Generation Inference** - `https://hf-inference.example.com`
- **Any OpenAI-compatible API**

### Configuration Patterns

#### Mediqzy.com
```bash
EXTERNAL_LLM_PROVIDER=mediqzy
EXTERNAL_LLM_BASE_URL=https://api.mediqzy.com
EXTERNAL_LLM_API_KEY=sk-mediqzy-xxxxx
EXTERNAL_LLM_MODEL=mediqzy-clinical
```

#### OpenAI
```bash
EXTERNAL_LLM_PROVIDER=openai
EXTERNAL_LLM_BASE_URL=https://api.openai.com
EXTERNAL_LLM_API_KEY=sk-...
EXTERNAL_LLM_MODEL=gpt-4  # or gpt-3.5-turbo
```

#### Ollama (Local)
```bash
EXTERNAL_LLM_PROVIDER=custom
EXTERNAL_LLM_BASE_URL=http://localhost:11434
EXTERNAL_LLM_API_KEY=  # Leave empty (Ollama doesn't require auth)
EXTERNAL_LLM_MODEL=mistral  # or llama2, neural-chat, etc.
```

#### LM Studio (Local)
```bash
EXTERNAL_LLM_PROVIDER=custom
EXTERNAL_LLM_BASE_URL=http://localhost:1234
EXTERNAL_LLM_API_KEY=  # Leave empty
EXTERNAL_LLM_MODEL=your-loaded-model
```

## How It Works

1. **Request Routing**: When `/v1/chat/completions` is called and `EXTERNAL_LLM_ENABLED=true`, the request is first sent to the external LLM.

2. **Fallback**: If the external LLM is unavailable or returns an error, the request automatically falls back to the local model router.

3. **Response**: External LLM responses are wrapped in the standard OpenAI `ChatResponse` format for compatibility.

4. **Logging**: All routing decisions and API calls are logged for debugging.

## Architecture

```
Client Request
    ↓
/v1/chat/completions endpoint
    ↓
┌─────────────────────────────────────┐
│ External LLM Enabled?               │
└─────────────────────────────────────┘
    ├─ YES → Try External LLM Service
    │         ├─ Success → Return response
    │         └─ Failure → Fallback to local
    │
    └─ NO → Use Local Model Router
            (vLLM, HF Transformers, etc.)
```

## Configuration File (Optional)

Instead of env vars, you can create `config/external_llm.yaml`:

```yaml
enabled: true
provider: mediqzy
api:
  base_url: https://api.mediqzy.com
  api_key: ${MEDIQZY_API_KEY}  # References env var
  model: mediqzy-clinical
  timeout: 30
defaults:
  temperature: 0.7
  max_tokens: 2048
```

Then in your startup:
```python
from app.services.external_llm import LLMConfig
config = LLMConfig.from_yaml("config/external_llm.yaml")
```

## Advanced Usage

### Using Streaming (Optional Feature)

If your external LLM supports streaming, you can use:

```python
from app.services.external_llm import get_external_llm_client

client = await get_external_llm_client()

async for chunk in client.stream_completion(
    messages=[{"role": "user", "content": "Tell me a story"}],
    temperature=0.8,
):
    print(chunk, end="", flush=True)
```

### Custom Headers/Auth

If your Mediqzy API requires custom headers beyond Bearer token:

```python
# Update app/services/external_llm.py line ~88 to customize headers:
headers = {
    "Content-Type": "application/json",
    "X-Custom-Header": "custom-value",
}
if self.config.api_key:
    headers["Authorization"] = f"Bearer {self.config.api_key}"
```

### Temperature & Token Control

Each request can override defaults:

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [...],
    "agent_type": "Claims",
    "temperature": 0.2,  # Lower = more precise (0.0 = deterministic)
    "max_tokens": 1024   # Limit output length
  }'
```

## Troubleshooting

### 1. "External LLM failed, falling back to local"

**Check:**
```bash
curl -X POST https://api.mediqzy.com/v1/chat/completions \
  -H "Authorization: Bearer YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"mediqzy-clinical","messages":[{"role":"user","content":"test"}]}'
```

**Common issues:**
- ❌ Wrong `EXTERNAL_LLM_BASE_URL` (check trailing slash)
- ❌ Invalid or expired `EXTERNAL_LLM_API_KEY`
- ❌ Wrong `EXTERNAL_LLM_MODEL` name
- ❌ API service is down

### 2. Network Timeout

Increase timeout:
```bash
EXTERNAL_LLM_TIMEOUT=60  # Default is 30 seconds
```

### 3. Check Logs

```bash
# View detailed logs
tail -f logs/inference.log | grep -i "external_llm"
```

## Monitoring

### Metrics to Track

1. **External LLM Success Rate**: Monitor `/v1/chat/completions` responses with `model` field containing provider name.
2. **Fallback Rate**: Count logs containing "falling back to local".
3. **Response Time**: Compare latency with/without external LLM.
4. **Cost**: If using paid services (OpenAI, Mediqzy), track token usage via `usage` field in response.

### Example Prometheus Query
```promql
# Request rate by external LLM
rate(http_requests_total{endpoint="/v1/chat/completions"}[5m])

# Fallback rate
rate(external_llm_fallbacks_total[5m])
```

## Production Checklist

- [ ] ✅ Tested connectivity to Mediqzy API
- [ ] ✅ Verified API key and model name
- [ ] ✅ Confirmed response format matches expectations
- [ ] ✅ Set appropriate timeout for SLA
- [ ] ✅ Configured fallback to local models
- [ ] ✅ Enabled logging for audit trail
- [ ] ✅ Set rate limits if applicable
- [ ] ✅ Tested with realistic payloads
- [ ] ✅ Verified cost/token tracking
- [ ] ✅ Set up monitoring and alerts

## Example Docker Compose

```yaml
version: '3.8'

services:
  inference-node:
    image: n3090-inference:latest
    ports:
      - "8000:8000"
    environment:
      EXTERNAL_LLM_ENABLED: "true"
      EXTERNAL_LLM_PROVIDER: "mediqzy"
      EXTERNAL_LLM_BASE_URL: "https://api.mediqzy.com"
      EXTERNAL_LLM_API_KEY: "${MEDIQZY_API_KEY}"
      EXTERNAL_LLM_MODEL: "mediqzy-clinical"
      EXTERNAL_LLM_TEMPERATURE: "0.7"
      EXTERNAL_LLM_MAX_TOKENS: "2048"
      EXTERNAL_LLM_TIMEOUT: "30"
    restart: unless-stopped
```

## Next Steps

1. **Get API Details**: Contact your Mediqzy account manager for:
   - Base URL
   - API key
   - Available model names
   - Rate limits

2. **Test Locally**: Use `curl` or `PostMan` to verify the API works before deploying.

3. **Monitor Performance**: Compare inference time and accuracy with local models.

4. **Scale**: Once validated, deploy to production with appropriate monitoring.

## Support

For issues or questions:
1. Check application logs: `tail -f logs/inference.log`
2. Verify environment variables: `env | grep EXTERNAL_LLM`
3. Test API manually: `curl -v https://api.mediqzy.com/v1/models`
4. Contact Mediqzy support with error messages

---

**File**: `docs/EXTERNAL_LLM_INTEGRATION.md`  
**Created**: 2026-01-09  
**Last Updated**: 2026-01-09
