# Complete Integration Setup Guide

Your teleconsultation app can seamlessly replace OpenAI with N3090. Here's the complete setup process.

## Quick Start (3 minutes)

### Step 1: Start N3090 in Development Mode

```bash
# Enable dev mode (no authentication required)
cd /home/dgs/N3090/services/inference-node

# Start with development settings
ALLOW_INSECURE_DEV=true uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Step 2: Call the API from Your App

```python
import requests

# Simple chat request
response = requests.post(
    "http://localhost:8000/v1/chat/completions",
    json={
        "messages": [
            {"role": "system", "content": "You are a medical AI assistant."},
            {"role": "user", "content": "What is diabetes?"}
        ],
        "model": "BioMistral",
        "temperature": 0.7,
        "max_tokens": 500
    },
    timeout=30
)

# Get response
answer = response.json()['choices'][0]['message']['content']
print(answer)
```

### Step 3: Use in Your Telemedicine App

```python
# In your Flask/FastAPI app
@app.route('/api/medical-chat', methods=['POST'])
def medical_chat():
    user_message = request.json['message']
    
    response = requests.post(
        "http://localhost:8000/v1/chat/completions",
        json={
            "messages": [
                {"role": "system", "content": "You are a medical AI assistant."},
                {"role": "user", "content": user_message}
            ],
            "model": "BioMistral"
        }
    )
    
    return {"response": response.json()['choices'][0]['message']['content']}
```

That's it! No more OpenAI calls.

---

## Development Setup (Localhost)

### Option 1: Simple HTTP Calls (Recommended for Quick Testing)

```python
import requests

def chat_with_medical_ai(message: str) -> str:
    """Call N3090 medical AI from your app"""
    
    response = requests.post(
        "http://localhost:8000/v1/chat/completions",
        json={
            "messages": [
                {"role": "system", "content": "You are a helpful medical AI."},
                {"role": "user", "content": message}
            ],
            "model": "BioMistral",
            "temperature": 0.7,
            "max_tokens": 500
        },
        timeout=30
    )
    
    return response.json()['choices'][0]['message']['content']

# Usage
answer = chat_with_medical_ai("What are symptoms of diabetes?")
print(answer)
```

### Option 2: Wrapper Class for Reusability

```python
import requests
from typing import List, Dict, Generator

class MedicalAI:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.api_url = f"{base_url}/v1/chat/completions"
        self.default_model = "BioMistral"
    
    def chat(self, message: str, model: str = None, stream: bool = False) -> str:
        """Send message and get response"""
        model = model or self.default_model
        
        response = requests.post(
            self.api_url,
            json={
                "messages": [{"role": "user", "content": message}],
                "model": model,
                "stream": stream
            },
            timeout=30
        )
        
        if stream:
            return response.iter_lines()
        return response.json()['choices'][0]['message']['content']
    
    def multi_turn(self, messages: List[Dict]) -> str:
        """Chat with conversation history"""
        response = requests.post(
            self.api_url,
            json={
                "messages": messages,
                "model": self.default_model
            },
            timeout=30
        )
        return response.json()['choices'][0]['message']['content']

# Usage
ai = MedicalAI()
answer1 = ai.chat("I have a fever")
answer2 = ai.multi_turn([
    {"role": "user", "content": "I have a fever"},
    {"role": "assistant", "content": "..."},
    {"role": "user", "content": "What should I take?"}
])
```

### Option 3: Full Integration with Error Handling

```python
import requests
import json
from typing import AsyncIterator
import logging

logger = logging.getLogger(__name__)

class TelemedicineAI:
    """Production-ready medical AI client for telemedicine apps"""
    
    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout: int = 30,
        default_model: str = "BioMistral"
    ):
        self.base_url = base_url
        self.api_url = f"{base_url}/v1/chat/completions"
        self.health_url = f"{base_url}/health"
        self.timeout = timeout
        self.default_model = default_model
    
    def health_check(self) -> bool:
        """Verify LLM server is running"""
        try:
            response = requests.get(self.health_url, timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    def chat(
        self,
        messages: list,
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> str:
        """Send chat message and get response"""
        
        if not self.health_check():
            raise RuntimeError("Medical AI server is not running")
        
        payload = {
            "messages": messages,
            "model": model or self.default_model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }
        
        try:
            response = requests.post(
                self.api_url,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            return data['choices'][0]['message']['content']
        
        except requests.exceptions.Timeout:
            logger.error(f"Request timeout after {self.timeout}s")
            raise
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error: {e}")
            raise
        except Exception as e:
            logger.error(f"Error: {e}")
            raise
    
    def chat_stream(
        self,
        messages: list,
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> Generator[str, None, None]:
        """Stream chat response for real-time UI"""
        
        payload = {
            "messages": messages,
            "model": model or self.default_model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True
        }
        
        try:
            response = requests.post(
                self.api_url,
                json=payload,
                stream=True,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    text = line.decode('utf-8')
                    if text.startswith('data: '):
                        try:
                            data = json.loads(text[6:])
                            if 'choices' in data:
                                chunk = data['choices'][0]['delta'].get('content', '')
                                if chunk:
                                    yield chunk
                        except json.JSONDecodeError:
                            pass
        
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            raise

# Usage in Flask
from flask import Flask, request, jsonify, Response

app = Flask(__name__)
medical_ai = TelemedicineAI()

@app.route('/api/consult', methods=['POST'])
def telemedicine_consult():
    """Non-streaming medical consultation"""
    data = request.json
    messages = data.get('messages', [])
    
    try:
        response = medical_ai.chat(messages)
        return jsonify({"response": response})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/consult/stream', methods=['POST'])
def telemedicine_consult_stream():
    """Real-time streaming medical consultation"""
    data = request.json
    messages = data.get('messages', [])
    
    def generate():
        try:
            for chunk in medical_ai.chat_stream(messages):
                yield chunk
        except Exception as e:
            yield f"Error: {e}"
    
    return Response(generate(), mimetype='text/plain')
```

---

## Production Setup

### Environment Setup

Create a `.env` file in your telemedicine app:

```env
# N3090 Configuration
MEDICAL_AI_URL=http://medical-ai-server:8000
MEDICAL_AI_TIMEOUT=30
MEDICAL_AI_MODEL=BioMistral

# Telemedicine API
TELEMEDICINE_PORT=5000
WORKERS=4
```

### Docker Deployment

**Dockerfile for your telemedicine app:**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/health')"

# Run app
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]
```

**Docker Compose for both services:**

```yaml
version: '3.8'

services:
  # Medical AI Inference Server
  medical-ai:
    image: medical-ai:latest
    container_name: medical-ai-server
    ports:
      - "8000:8000"
    environment:
      - ALLOW_INSECURE_DEV=false
      - JWT_SECRET=${JWT_SECRET}
      - DATABASE_URL=${DATABASE_URL}
    volumes:
      - ./models:/app/models
    restart: always
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Your Telemedicine App
  telemedicine-app:
    image: telemedicine:latest
    container_name: telemedicine-app
    ports:
      - "5000:5000"
    environment:
      - MEDICAL_AI_URL=http://medical-ai:8000
      - DATABASE_URL=${DATABASE_URL}
    depends_on:
      - medical-ai
    restart: always
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

**Start everything:**

```bash
docker-compose up -d
```

### Load Balancing & Scaling

**Nginx reverse proxy for your telemedicine app:**

```nginx
upstream telemedicine {
    server app1:5000;
    server app2:5000;
    server app3:5000;
}

server {
    listen 80;
    server_name api.telemedicine.local;

    # Route to medical AI
    location /medical-ai/ {
        proxy_pass http://medical-ai:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Longer timeout for AI responses
        proxy_connect_timeout 30s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Route telemedicine app
    location / {
        proxy_pass http://telemedicine;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

---

## Testing Your Integration

### Test 1: Direct HTTP Call

```bash
curl -X POST "http://localhost:8000/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "What is hypertension?"}
    ],
    "model": "BioMistral",
    "max_tokens": 200
  }'
```

### Test 2: Python Integration Test

```python
import requests
import time

def test_integration():
    """Test N3090 integration"""
    
    # Test 1: Health check
    print("1. Health check...", end=" ")
    response = requests.get("http://localhost:8000/health")
    assert response.status_code == 200
    print("✓")
    
    # Test 2: Chat endpoint
    print("2. Chat endpoint...", end=" ")
    response = requests.post(
        "http://localhost:8000/v1/chat/completions",
        json={
            "messages": [{"role": "user", "content": "Hi"}],
            "model": "Qwen",
            "max_tokens": 50
        },
        timeout=30
    )
    assert response.status_code == 200
    assert 'choices' in response.json()
    print("✓")
    
    # Test 3: Response time
    print("3. Response time (Qwen)...", end=" ")
    start = time.time()
    response = requests.post(
        "http://localhost:8000/v1/chat/completions",
        json={
            "messages": [{"role": "user", "content": "What is fever?"}],
            "model": "Qwen",
            "max_tokens": 100
        },
        timeout=30
    )
    elapsed = time.time() - start
    print(f"{elapsed:.1f}s ✓")
    
    # Test 4: Larger model
    print("4. Response time (BioMistral)...", end=" ")
    start = time.time()
    response = requests.post(
        "http://localhost:8000/v1/chat/completions",
        json={
            "messages": [{"role": "user", "content": "Explain diabetes"}],
            "model": "BioMistral",
            "max_tokens": 200
        },
        timeout=30
    )
    elapsed = time.time() - start
    print(f"{elapsed:.1f}s ✓")
    
    print("\n✅ All integration tests passed!")

if __name__ == "__main__":
    test_integration()
```

---

## Model Selection for Your Use Case

### Real-time Patient Chat
```python
# Use fastest model
model = "Qwen"  # 0.6B
# Typical response: 100-300ms
```

### Doctor-Doctor Communication
```python
# Use balanced model
model = "BiMediX2"  # 8B
# Typical response: 1-2 seconds
```

### Detailed Medical Analysis
```python
# Use high-quality model
model = "BioMistral"  # 7B
# Typical response: 1-3 seconds
```

### Insurance/Claims
```python
# Use specialized model
model = "OpenInsurance"  # 8B
# Typical response: 1-2 seconds
```

---

## Common Integration Patterns

### Pattern 1: Chat History with Context

```python
def save_consultation(patient_id: str, messages: list) -> str:
    """Store consultation and get AI response"""
    
    medical_ai = TelemedicineAI()
    
    # Add system context
    context_message = {
        "role": "system",
        "content": f"You are assisting in a telemedicine consultation for patient {patient_id}."
    }
    
    all_messages = [context_message] + messages
    
    # Get AI response
    response = medical_ai.chat(all_messages)
    
    # Save to database
    db.save_consultation(patient_id, messages, response)
    
    return response
```

### Pattern 2: Real-time Streaming Response

```python
@app.route('/ws/chat')
async def websocket_chat(websocket):
    """WebSocket endpoint for real-time chat"""
    await websocket.accept()
    
    medical_ai = TelemedicineAI()
    
    while True:
        # Receive message
        message = await websocket.receive_text()
        
        # Stream response
        response_text = ""
        for chunk in medical_ai.chat_stream(
            [{"role": "user", "content": message}]
        ):
            response_text += chunk
            await websocket.send_text(chunk)
        
        # Save to DB
        db.save_chat(message, response_text)
```

### Pattern 3: Fallback to Multiple Models

```python
def get_best_response(message: str) -> str:
    """Try multiple models until success"""
    
    models = ["BioMistral", "BiMediX2", "Qwen"]
    
    for model in models:
        try:
            response = medical_ai.chat(
                [{"role": "user", "content": message}],
                model=model
            )
            return response
        except Exception as e:
            logger.warning(f"Model {model} failed: {e}")
            continue
    
    raise RuntimeError("All models failed")
```

---

## Monitoring & Logging

```python
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MonitoredMedicalAI(TelemedicineAI):
    """Medical AI with monitoring"""
    
    def chat(self, messages, **kwargs):
        start = time.time()
        
        try:
            response = super().chat(messages, **kwargs)
            
            elapsed = time.time() - start
            logger.info(
                f"Chat request successful",
                extra={
                    "duration_ms": int(elapsed * 1000),
                    "model": kwargs.get('model', 'default'),
                    "message_count": len(messages),
                    "response_length": len(response)
                }
            )
            
            return response
        
        except Exception as e:
            elapsed = time.time() - start
            logger.error(
                f"Chat request failed: {e}",
                extra={
                    "duration_ms": int(elapsed * 1000),
                    "model": kwargs.get('model', 'default')
                }
            )
            raise
```

---

## Checklist for Integration

- [ ] Start N3090 server (development or production)
- [ ] Test health endpoint works
- [ ] Make first API call with test message
- [ ] Implement error handling and timeouts
- [ ] Add logging and monitoring
- [ ] Choose appropriate models for your use cases
- [ ] Implement conversation history storage
- [ ] Add streaming support for real-time chat
- [ ] Set up load balancing if needed
- [ ] Implement fallback mechanisms
- [ ] Test with production-like message volume
- [ ] Deploy to production environment
- [ ] Monitor server health and performance
- [ ] Set up alerting for failures

---

## Next Steps

1. **Start N3090**: `ALLOW_INSECURE_DEV=true uvicorn app.main:app --port 8000`
2. **Copy integration code** from this guide to your telemedicine app
3. **Replace OpenAI calls** with MedicalAI class
4. **Test thoroughly** with development data
5. **Deploy to production** using Docker/K8s
6. **Monitor performance** and adjust models as needed

You're now ready to replace OpenAI with your local Medical AI system! 🚀

