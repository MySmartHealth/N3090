# N3090 Medical LLM API Reference - Quick Start

For API-only integration with your telemedicine app. All endpoints are HTTP REST calls.

---

## Server Configuration

```
Development:  http://localhost:8000
Production:   http://your-domain.com:8000

Start server:
ALLOW_INSECURE_DEV=true uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## Main Endpoint: Chat Completions

**OpenAI-compatible chat endpoint**

### Request

```
POST /v1/chat/completions
Content-Type: application/json
```

### Payload

```json
{
  "messages": [
    {
      "role": "system",
      "content": "You are a helpful medical AI assistant."
    },
    {
      "role": "user",
      "content": "What is diabetes?"
    }
  ],
  "model": "BioMistral",
  "temperature": 0.7,
  "max_tokens": 500,
  "stream": false
}
```

### Response

```json
{
  "id": "cmpl-abc123",
  "object": "text_completion",
  "created": 1704384000,
  "model": "BioMistral",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Diabetes is a chronic disease characterized by high blood glucose levels..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 25,
    "completion_tokens": 150,
    "total_tokens": 175
  }
}
```

---

## API Examples

### cURL

```bash
# Basic chat
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "What is hypertension?"}
    ],
    "model": "BioMistral",
    "max_tokens": 300
  }'

# Multi-turn conversation
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "I have chest pain"},
      {"role": "assistant", "content": "I understand you are experiencing chest pain..."},
      {"role": "user", "content": "What should I do?"}
    ],
    "model": "BioMistral"
  }'

# Streaming response
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Explain heart disease"}],
    "model": "BioMistral",
    "stream": true
  }'
```

### Python (requests)

```python
import requests

# Simple call
response = requests.post(
    "http://localhost:8000/v1/chat/completions",
    json={
        "messages": [
            {"role": "user", "content": "What is diabetes?"}
        ],
        "model": "BioMistral",
        "max_tokens": 500
    },
    timeout=30
)

answer = response.json()['choices'][0]['message']['content']
print(answer)
```

### JavaScript/Node.js

```javascript
const axios = require('axios');

const response = await axios.post(
    'http://localhost:8000/v1/chat/completions',
    {
        messages: [
            { role: 'user', content: 'What is diabetes?' }
        ],
        model: 'BioMistral',
        max_tokens: 500
    }
);

const answer = response.data.choices[0].message.content;
console.log(answer);
```

### Go

```go
package main

import (
    "bytes"
    "encoding/json"
    "fmt"
    "io"
    "net/http"
)

func main() {
    payload := map[string]interface{}{
        "messages": []map[string]string{
            {"role": "user", "content": "What is diabetes?"},
        },
        "model": "BioMistral",
        "max_tokens": 500,
    }

    jsonData, _ := json.Marshal(payload)
    resp, _ := http.Post(
        "http://localhost:8000/v1/chat/completions",
        "application/json",
        bytes.NewBuffer(jsonData),
    )
    defer resp.Body.Close()

    body, _ := io.ReadAll(resp.Body)
    var result map[string]interface{}
    json.Unmarshal(body, &result)
    
    fmt.Println(result)
}
```

### PHP

```php
<?php
$data = json_encode([
    'messages' => [
        ['role' => 'user', 'content' => 'What is diabetes?']
    ],
    'model' => 'BioMistral',
    'max_tokens' => 500
]);

$ch = curl_init('http://localhost:8000/v1/chat/completions');
curl_setopt($ch, CURLOPT_CUSTOMREQUEST, 'POST');
curl_setopt($ch, CURLOPT_POSTFIELDS, $data);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_HTTPHEADER, [
    'Content-Type: application/json'
]);

$response = curl_exec($ch);
$result = json_decode($response, true);
echo $result['choices'][0]['message']['content'];
?>
```

### Java

```java
import okhttp3.*;

OkHttpClient client = new OkHttpClient();

String json = "{" +
    "\"messages\": [{\"role\": \"user\", \"content\": \"What is diabetes?\"}]," +
    "\"model\": \"BioMistral\"," +
    "\"max_tokens\": 500" +
"}";

RequestBody body = RequestBody.create(json, MediaType.parse("application/json"));
Request request = new Request.Builder()
    .url("http://localhost:8000/v1/chat/completions")
    .post(body)
    .build();

try (Response response = client.newCall(request).execute()) {
    String responseBody = response.body().string();
    System.out.println(responseBody);
}
```

---

## Query Parameters

### Basic Parameters

| Parameter | Type | Default | Example | Notes |
|-----------|------|---------|---------|-------|
| `messages` | array | required | `[{"role": "user", "content": "..."}]` | Conversation history |
| `model` | string | `MedicalQA` | `BioMistral` | See models list below |
| `temperature` | float | 0.7 | 0.5 | 0.0=deterministic, 1.0=creative |
| `max_tokens` | int | 500 | 1000 | Max response length |
| `stream` | boolean | false | true | Stream response |
| `agent_type` | string | optional | `Claims` | Route to specialist |

### Available Models

```
Fast responses (real-time chat):
  - Qwen                (0.6B)  ~100-300ms
  - Tiny-LLaMA          (1.1B)  ~200-500ms

Balanced (general medical):
  - BiMediX2            (8B)    ~1-2s
  - BioMistral          (7B)    ~1-2s

Specialized:
  - OpenInsurance       (8B)    ~1-2s    (insurance/claims)
  - MedicalQA           (router) Auto-select best model
```

### Agent Types (Routing)

```
MedicalQA       General medical questions
Claims          Insurance claims
Billing         Medical billing
Documentation   Medical documentation
PatientChat     Patient-facing conversations
```

---

## Health Check

```
GET /health
GET /v1/health

Response: {"status": "ok"}
```

### Example

```bash
curl http://localhost:8000/health
```

---

## System Information

```
GET /v1/models
GET /v1/gpu/memory
GET /v1/status
GET /docs              (Interactive API docs)
```

---

## Integration Patterns

### Pattern 1: Single Message

```bash
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "patient_question"}],
    "model": "BioMistral"
  }'
```

### Pattern 2: Multi-turn Conversation

```bash
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "I have fever"},
      {"role": "assistant", "content": "Fever causes..."},
      {"role": "user", "content": "What should I take?"}
    ],
    "model": "BioMistral"
  }'
```

### Pattern 3: System Context

```bash
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "system", "content": "You are a telemedicine specialist helping patients."},
      {"role": "user", "content": "What is normal blood pressure?"}
    ],
    "model": "BioMistral"
  }'
```

### Pattern 4: Specialized Routing

```bash
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Will insurance cover this?"}],
    "model": "OpenInsurance",
    "agent_type": "Claims"
  }'
```

### Pattern 5: Fast Real-time Chat

```bash
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Hi"}],
    "model": "Qwen",
    "max_tokens": 200,
    "temperature": 0.5
  }'
```

### Pattern 6: Streaming Response

```bash
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Explain diabetes"}],
    "model": "BioMistral",
    "stream": true
  }' | while read line; do
    echo "$line" | sed 's/^data: //'
  done
```

---

## Advanced Features

### Vision-Language Processing (Medical Images)

```
POST /v1/advanced/vlp/analyze-image

{
  "image": "base64_encoded_image",
  "image_type": "xray",
  "specialty": "radiology"
}
```

### Generate Report

```
POST /v1/advanced/gen-ai/generate-report

{
  "patient_data": {
    "age": 45,
    "chief_complaint": "chest pain",
    "vitals": {"bp": "140/90", "hr": 88}
  },
  "report_type": "clinical"
}
```

### Explainable AI

```
POST /v1/advanced/xai/explain-prediction

{
  "prediction": "Patient may have hypertension",
  "patient_data": {"age": 55, "bp": 145}
}
```

---

## Response Codes

```
200  Success
400  Bad Request (invalid parameters)
401  Unauthorized (auth required in production)
403  Forbidden (auth failed)
500  Server Error
503  Service Unavailable
```

---

## Error Handling

### Example Error Response

```json
{
  "detail": "messages must be non-empty"
}
```

### Common Errors

```
"Invalid or unsupported agent type"
  → Check agent_type is valid

"messages must be non-empty"
  → Add at least one message

"Connection refused"
  → N3090 server not running

"Timeout"
  → Server taking too long (try faster model or smaller max_tokens)
```

---

## Timeout Settings

```
Development:  30 seconds
Production:   30 seconds
Streaming:    60 seconds

Recommended for your app:
  - Chat requests:      30s timeout
  - Streaming:          60s timeout
  - Health checks:      5s timeout
```

---

## Model Performance

```
Qwen (0.6B):
  Speed: 100-300ms
  Quality: Good for real-time
  Best for: Live chat, quick responses

BiMediX2 (8B):
  Speed: 1-2s
  Quality: Excellent medical
  Best for: Detailed medical advice

BioMistral (7B):
  Speed: 1-2s
  Quality: Excellent clinical
  Best for: Doctor-patient consultation

OpenInsurance (8B):
  Speed: 1-2s
  Quality: Specialized for insurance
  Best for: Claims, billing questions
```

---

## Usage Limits

```
Development: Unlimited
Production:
  - Rate limit: 100 requests/minute
  - Max tokens: 2000 per request
  - Max concurrent: 10 requests
  - Timeout: 30 seconds
```

---

## Quick Reference

```bash
# Health check
curl http://localhost:8000/health

# Simple question
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "What is fever?"}], "model": "BioMistral"}'

# With streaming
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Explain diabetes"}], "model": "BioMistral", "stream": true}'

# Fast response
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hi"}], "model": "Qwen", "max_tokens": 200}'

# Insurance routing
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Does insurance cover?"}], "model": "OpenInsurance", "agent_type": "Claims"}'
```

---

## Integration Checklist

- [ ] Server running: `ALLOW_INSECURE_DEV=true uvicorn app.main:app --port 8000`
- [ ] Health check passes: `curl http://localhost:8000/health`
- [ ] First API call works
- [ ] Implement error handling
- [ ] Add timeouts (30s)
- [ ] Choose appropriate models
- [ ] Test streaming if needed
- [ ] Deploy to production
- [ ] Monitor response times

---

## Troubleshooting

### "Connection refused"
Server not running. Start it:
```bash
ALLOW_INSECURE_DEV=true uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### "Request timeout"
Server too slow. Try:
- Faster model: `model: "Qwen"`
- Smaller response: `max_tokens: 200`
- Increase timeout to 60s

### "503 Service Unavailable"
GPU memory full. Restart server:
```bash
killall llama-server && sleep 2
# Then restart
```

### "Invalid model"
Use valid model name. Available:
- Qwen, BiMediX2, BioMistral, OpenInsurance, Tiny-LLaMA, MedicalQA

---

## Documentation

- Full API docs: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- GitHub: `https://github.com/MySmartHealth/N3090`

