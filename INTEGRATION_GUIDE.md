# Integration Guide: Using N3090 LLM App with Your Teleconsultation App

This guide shows you how to integrate this Medical AI inference system with your teleconsultation/teledoctor chat app as a replacement for OpenAI.

## Quick Start

### 1. System Architecture

```
Your Teleconsultation App
         ↓ (HTTP/REST)
┌─────────────────────────────┐
│  N3090 Medical AI Inference │
│  - 6 Medical LLM Models     │
│  - RAG/Knowledge Base       │
│  - Advanced AI Features     │
└─────────────────────────────┘
         ↓
    RTX 3090 GPU
    (24GB VRAM)
```

### 2. API Endpoint (Drop-in OpenAI Replacement)

**OpenAI-Compatible Chat Completions:**
```
POST http://localhost:8000/v1/chat/completions
```

This endpoint is **100% compatible** with OpenAI's chat completions API, so minimal code changes needed.

---

## Integration Methods

### Method 1: Direct HTTP Calls (Recommended for Web Apps)

#### Python Example
```python
import requests
import json

# Your chat message
message = {
    "messages": [
        {"role": "system", "content": "You are a helpful medical AI assistant."},
        {"role": "user", "content": "What are symptoms of diabetes?"}
    ],
    "model": "MedicalQA",  # or "Claims", "Billing", "Documentation"
    "temperature": 0.7,
    "max_tokens": 500
}

# Call the endpoint
response = requests.post(
    "http://localhost:8000/v1/chat/completions",
    json=message,
    timeout=30
)

result = response.json()
print(result['choices'][0]['message']['content'])
```

#### JavaScript/Node.js Example
```javascript
const axios = require('axios');

const message = {
    messages: [
        { role: "system", content: "You are a helpful medical AI assistant." },
        { role: "user", content: "What are symptoms of diabetes?" }
    ],
    model: "MedicalQA",
    temperature: 0.7,
    max_tokens: 500
};

axios.post('http://localhost:8000/v1/chat/completions', message)
    .then(res => {
        console.log(res.data.choices[0].message.content);
    })
    .catch(err => console.error(err));
```

#### cURL Example
```bash
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "system", "content": "You are a helpful medical AI assistant."},
      {"role": "user", "content": "What are symptoms of diabetes?"}
    ],
    "model": "MedicalQA",
    "temperature": 0.7,
    "max_tokens": 500
  }'
```

---

### Method 2: Using OpenAI Python Library (Minimal Code Change)

**This is the easiest migration from OpenAI!**

```python
from openai import OpenAI

# Point to your local N3090 server instead of OpenAI
client = OpenAI(
    api_key="local-dev",  # Not needed for local server
    base_url="http://localhost:8000/v1"  # Change this line only!
)

# Rest of code works exactly like OpenAI
response = client.chat.completions.create(
    model="MedicalQA",
    messages=[
        {"role": "system", "content": "You are a helpful medical AI assistant."},
        {"role": "user", "content": "What are symptoms of diabetes?"}
    ],
    temperature=0.7,
    max_tokens=500
)

print(response.choices[0].message.content)
```

**Migration Steps:**
```python
# BEFORE (OpenAI):
client = OpenAI(api_key="sk-...")

# AFTER (N3090):
client = OpenAI(
    api_key="local-dev",
    base_url="http://localhost:8000/v1"
)

# Everything else stays the same!
```

---

### Method 3: Streaming Responses (for Real-time Chat)

#### Python with Streaming
```python
import requests
import json

message = {
    "messages": [
        {"role": "system", "content": "You are a helpful medical AI assistant."},
        {"role": "user", "content": "Explain heart disease"}
    ],
    "model": "MedicalQA",
    "stream": True,
    "temperature": 0.7
}

response = requests.post(
    "http://localhost:8000/v1/chat/completions",
    json=message,
    stream=True
)

# Process streaming response
for line in response.iter_lines():
    if line:
        data = json.loads(line.decode('utf-8').replace('data: ', ''))
        if 'choices' in data:
            chunk = data['choices'][0]['delta'].get('content', '')
            print(chunk, end='', flush=True)
```

#### JavaScript with Streaming
```javascript
async function streamChat(messages) {
    const response = await fetch('http://localhost:8000/v1/chat/completions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            messages,
            model: 'MedicalQA',
            stream: true,
            temperature: 0.7
        })
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        const text = decoder.decode(value);
        const lines = text.split('\n').filter(l => l.trim());
        
        lines.forEach(line => {
            if (line.startsWith('data: ')) {
                const data = JSON.parse(line.slice(6));
                if (data.choices[0].delta.content) {
                    process.stdout.write(data.choices[0].delta.content);
                }
            }
        });
    }
}

// Usage
streamChat([
    { role: "system", content: "You are a helpful medical AI assistant." },
    { role: "user", content: "Explain heart disease" }
]);
```

---

## Available Models

Choose the best model for your use case:

| Model | Port | Size | Use Case | Performance |
|-------|------|------|----------|-------------|
| **Tiny-LLaMA** | 8080 | 1.1B | General chat, quick responses | Fast (~100ms) |
| **BiMediX2** | 8081 | 8B | Medical knowledge, detailed answers | Balanced |
| **Qwen** | 8082 | 0.6B | Ultra-fast responses | Very Fast |
| **Tiny-LLaMA-2** | 8083 | 1.1B | Alternative general model | Fast |
| **OpenInsurance** | 8084 | 8B | Insurance/claims questions | Specialized |
| **BioMistral** | 8085 | 7B | Medical/clinical expertise | High-quality |

**Model Selection for Chat:**
```python
# For quick responses (telemedicine real-time chat)
model = "Qwen"  # 0.6B - fastest

# For detailed medical advice (documented consultation)
model = "BioMistral"  # 7B - high quality

# For insurance/billing questions
model = "OpenInsurance"  # 8B - specialized

# For general medical questions
model = "BiMediX2"  # 8B - medical-focused

# Automatic selection (router chooses best model)
model = "MedicalQA"  # Let system choose
```

---

## Agent Types (Specialty Routing)

The system automatically routes to specialized agents:

```python
message = {
    "messages": [...],
    "agent_type": "MedicalQA",  # Change this for routing
    "temperature": 0.7
}
```

Available agent types:
- **MedicalQA**: General medical questions
- **Documentation**: Medical documentation assistance
- **Claims**: Insurance claims queries
- **Billing**: Medical billing questions
- **PatientChat**: Patient-facing conversations

---

## Advanced Features

### 1. Retrieval-Augmented Generation (RAG)

The system automatically pulls medical knowledge for relevant queries:

```python
message = {
    "messages": [
        {"role": "system", "content": "You are a medical expert."},
        {"role": "user", "content": "What are the latest guidelines for treating hypertension?"}
    ],
    "model": "MedicalQA"
    # RAG automatically engages for MedicalQA, Claims, Billing, Documentation
}
```

### 2. Vision-Language Processing (Medical Image Analysis)

```python
import requests
import base64

# Read image file
with open("xray.jpg", "rb") as img:
    image_data = base64.b64encode(img.read()).decode()

response = requests.post(
    "http://localhost:8000/v1/advanced/vlp/analyze-image",
    json={
        "image": image_data,
        "image_type": "xray",  # or mri, ct, ultrasound
        "specialty": "radiology"
    }
)

findings = response.json()
print(findings['findings'])
```

### 3. Report Generation

```python
response = requests.post(
    "http://localhost:8000/v1/advanced/gen-ai/generate-report",
    json={
        "patient_data": {
            "age": 45,
            "chief_complaint": "chest pain",
            "vitals": {"bp": "140/90", "hr": 88}
        },
        "report_type": "clinical"
    }
)

report = response.json()
print(report['report'])
```

### 4. Explainable AI (Decision Transparency)

```python
response = requests.post(
    "http://localhost:8000/v1/advanced/xai/explain-prediction",
    json={
        "prediction": "Patient may have hypertension",
        "patient_data": {"age": 55, "bp": 145}
    }
)

explanation = response.json()
print(f"Confidence: {explanation['confidence_score']}")
print(f"Key Factors: {explanation['feature_importance']}")
```

---

## Deployment Considerations

### Local Development
```bash
# Start the inference server
cd /home/dgs/N3090/services/inference-node
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Production Deployment

**Using Docker:**
```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app/ ./app/
COPY models/ ./models/

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

**Using PM2 (Node.js-style Process Manager):**
```bash
# Install PM2
npm install -g pm2

# Start with PM2
pm2 start "uvicorn app.main:app --host 0.0.0.0 --port 8000" \
    --name "medical-llm" \
    --interpreter=python3 \
    --instances 4

# Monitor
pm2 monit
```

**Load Balancing:**
```nginx
# Nginx config for load balancing across 4 workers
upstream medical_llm {
    server localhost:8000;
    server localhost:8001;
    server localhost:8002;
    server localhost:8003;
}

server {
    listen 80;
    server_name api.medical-ai.local;

    location / {
        proxy_pass http://medical_llm;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## Cost Comparison

| Service | Cost | Notes |
|---------|------|-------|
| **OpenAI GPT-4** | $0.03/1K tokens | Per-request billing |
| **OpenAI GPT-3.5** | $0.0005/1K tokens | Cheapest cloud option |
| **N3090 (This App)** | $0 (after GPU cost) | One-time hardware investment |
| **N3090 Equivalent** | ~$1,500-2,000 | RTX 3090 cost |

**ROI Calculation:**
- OpenAI: 10,000 requests/month × $0.002 = $20/month = $240/year
- N3090: $1,500 one-time (or amortized ~$30/month over 5 years)
- **Break-even: ~8-10 months**, then free indefinitely

---

## Troubleshooting Integration Issues

### Issue 1: Connection Refused
```
Error: Connection refused at localhost:8000
```

**Solution:**
```bash
# Check if server is running
curl http://localhost:8000/health

# If not running, start it:
cd /home/dgs/N3090/services/inference-node
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Issue 2: Slow Responses (>5 seconds)
```python
# Check GPU memory
curl http://localhost:8000/v1/gpu/memory

# Switch to faster model
model = "Qwen"  # 0.6B instead of 7B

# Or reduce max_tokens
max_tokens = 256  # instead of 1024
```

### Issue 3: CUDA Out of Memory
```bash
# Solution 1: Restart and free memory
killall llama-server
sleep 2

# Solution 2: Use quantized models (smaller)
# Already using Q5_K_M, Q6_K quantization (no change needed)

# Solution 3: Reduce batch size
# Automatic - system limits concurrent requests
```

### Issue 4: Model Not Responding
```bash
# Check which ports are running
netstat -tulpn | grep -E '808[0-5]'

# Expected output:
# 8080 - Tiny-LLaMA (LISTEN)
# 8081 - BiMediX2 (LISTEN)
# 8082 - Qwen (LISTEN)
# 8083 - Tiny-LLaMA-2 (LISTEN)
# 8084 - OpenInsurance (LISTEN)
# 8085 - BioMistral (LISTEN)
```

---

## Performance Optimization Tips

### 1. Use Caching for Frequently Asked Questions
```python
cache = {}

def get_response(question):
    if question in cache:
        return cache[question]
    
    response = requests.post(
        "http://localhost:8000/v1/chat/completions",
        json={...}
    ).json()
    
    cache[question] = response
    return response
```

### 2. Batch Similar Requests
```python
# Instead of: 10 separate API calls
# Do this: Group similar requests together

patients = [...]  # 10 patients
batch_questions = [p['question'] for p in patients]

responses = []
for q in batch_questions:
    r = requests.post("http://localhost:8000/v1/chat/completions", ...)
    responses.append(r.json())
```

### 3. Use Appropriate Model Sizes
```python
# Response time benchmarks:
# Qwen (0.6B): 100-300ms
# Tiny-LLaMA (1.1B): 200-500ms
# BiMediX2 (8B): 1-3 seconds
# BioMistral (7B): 1-2 seconds

# For real-time chat: use Qwen
# For quality answers: use BioMistral
# For balance: use BiMediX2
```

### 4. Connection Pooling
```python
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import requests

session = requests.Session()
retry = Retry(connect=3, backoff_factor=0.5)
adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
session.mount('http://', adapter)

# Use session for all requests
response = session.post('http://localhost:8000/v1/chat/completions', ...)
```

---

## Integration Checklist

- [ ] Start N3090 inference server
- [ ] Test health endpoint: `curl http://localhost:8000/health`
- [ ] Make first API call with test message
- [ ] Implement streaming responses (for real-time chat)
- [ ] Add error handling for timeouts
- [ ] Set up model selection logic for different use cases
- [ ] Implement request/response logging
- [ ] Add monitoring/alerting for server health
- [ ] Test with production-like message volumes
- [ ] Implement fallback to secondary LLM if needed
- [ ] Deploy to production environment
- [ ] Monitor GPU memory and performance

---

## Support & Resources

**API Documentation:**
```
http://localhost:8000/docs          # Interactive Swagger UI
http://localhost:8000/redoc         # ReDoc documentation
```

**Health Check:**
```bash
curl http://localhost:8000/health
```

**System Status:**
```bash
curl http://localhost:8000/v1/health
```

**Questions?**
Check the docs in `/home/dgs/N3090/docs/` for detailed information.

