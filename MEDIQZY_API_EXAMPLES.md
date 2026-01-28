# Mediqzy Integration - API Examples

## Testing with cURL

### Basic Test (Mediqzy)

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "What is hypertension?"}
    ],
    "agent_type": "MedicalQA"
  }'
```

**Response (with external LLM routing):**
```json
{
  "id": "cmpl-a1b2c3d4e5f6g7h8",
  "created": 1704729600,
  "model": "mediqzy:mediqzy-clinical",
  "choices": [
    {
      "index": 0,
      "finish_reason": "stop",
      "message": {
        "role": "assistant",
        "content": "Hypertension, commonly known as high blood pressure, is a chronic condition where the force of blood against artery walls is consistently too high (≥140/90 mmHg). Key points:\n\n1. **Definition**: Sustained elevation of systolic blood pressure ≥140 mmHg or diastolic ≥90 mmHg\n\n2. **Types**:\n   - Primary (Essential): 90-95% of cases, cause unknown\n   - Secondary: Result of underlying condition\n\n3. **Risk Factors**:\n   - Family history\n   - Age (>60 years)\n   - Obesity\n   - High sodium diet\n   - Sedentary lifestyle\n   - Chronic kidney disease\n\n4. **Complications**:\n   - Coronary artery disease\n   - Stroke\n   - Heart failure\n   - Kidney disease\n\n5. **Management**:\n   - Lifestyle modifications\n   - Antihypertensive medications\n   - Regular monitoring"
      }
    }
  ],
  "usage": {
    "prompt_tokens": 12,
    "completion_tokens": 187,
    "total_tokens": 199
  },
  "policy": {
    "agent_type": "MedicalQA",
    "constraints_mode": "draft-only",
    "draft_only": true,
    "side_effects": false
  },
  "translation": null
}
```

---

## Examples by Agent Type

### Medical QA (Doctor Diagnosis)

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "system", "content": "You are a diagnostic assistant. Provide clinical assessment."},
      {"role": "user", "content": "Patient: 62-year-old male. Symptoms: chest pain for 2 hours, shortness of breath, nausea. BP: 160/95."}
    ],
    "agent_type": "MedicalQA",
    "temperature": 0.3,
    "max_tokens": 1024
  }'
```

### Claims Processing (Insurance)

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Validate this insurance claim: 72-hour hospitalization for appendectomy, total cost $15,000, policy limit $100,000"}
    ],
    "agent_type": "Claims",
    "temperature": 0.1,
    "max_tokens": 512
  }'
```

### Documentation (Policy/Procedure)

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "What are the step-by-step procedures for inpatient hospital admission?"}
    ],
    "agent_type": "Documentation",
    "temperature": 0.5,
    "max_tokens": 2048
  }'
```

---

## Python Client Example

```python
import requests
import json
import os

class MediqzyClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
    
    def ask_mediqzy(self, question: str, agent_type: str = "MedicalQA", temperature: float = 0.7):
        """Send question to Mediqzy-powered endpoint"""
        
        payload = {
            "messages": [
                {"role": "user", "content": question}
            ],
            "agent_type": agent_type,
            "temperature": temperature
        }
        
        response = requests.post(
            f"{self.base_url}/v1/chat/completions",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        result = response.json()
        
        # Extract response
        if response.status_code == 200:
            content = result["choices"][0]["message"]["content"]
            model_used = result["model"]
            tokens = result["usage"]["total_tokens"]
            
            return {
                "success": True,
                "response": content,
                "model": model_used,
                "tokens": tokens
            }
        else:
            return {
                "success": False,
                "error": result.get("detail", "Unknown error")
            }

# Usage
if __name__ == "__main__":
    client = MediqzyClient()
    
    # Example 1: Medical question
    result = client.ask_mediqzy(
        "What are the warning signs of diabetes?",
        agent_type="MedicalQA",
        temperature=0.7
    )
    
    if result["success"]:
        print(f"Response: {result['response']}")
        print(f"Model: {result['model']}")
        print(f"Tokens used: {result['tokens']}")
    else:
        print(f"Error: {result['error']}")
    
    # Example 2: Insurance claim
    result = client.ask_mediqzy(
        "Check claim validity: 3-day hospitalization, appendectomy, cost $12,000",
        agent_type="Claims",
        temperature=0.3
    )
    
    print(f"\nClaim Assessment:\n{result['response']}")
```

---

## JavaScript/Node.js Example

```javascript
const axios = require('axios');

class MediqzyClient {
  constructor(baseUrl = 'http://localhost:8000') {
    this.baseUrl = baseUrl;
  }

  async askMediqzy(question, agentType = 'MedicalQA', temperature = 0.7) {
    try {
      const payload = {
        messages: [
          { role: 'user', content: question }
        ],
        agent_type: agentType,
        temperature: temperature
      };

      const response = await axios.post(
        `${this.baseUrl}/v1/chat/completions`,
        payload,
        {
          headers: { 'Content-Type': 'application/json' },
          timeout: 30000
        }
      );

      const { choices, model, usage } = response.data;
      
      return {
        success: true,
        response: choices[0].message.content,
        model: model,
        tokens: usage.total_tokens
      };
    } catch (error) {
      return {
        success: false,
        error: error.message
      };
    }
  }
}

// Usage
const client = new MediqzyClient();

client.askMediqzy(
  'What are the symptoms of heart disease?',
  'MedicalQA',
  0.7
).then(result => {
  if (result.success) {
    console.log('Response:', result.response);
    console.log('Model:', result.model);
    console.log('Tokens:', result.tokens);
  } else {
    console.error('Error:', result.error);
  }
});
```

---

## With JWT Authentication (Production)

```bash
# Generate token (from your auth system)
TOKEN="your-jwt-token-here"

curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "messages": [{"role": "user", "content": "Diagnose: fever 38.5C, cough, fatigue"}],
    "agent_type": "MedicalQA"
  }'
```

---

## Batch Processing (Multiple Requests)

```python
import requests
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

def process_claim(claim_data):
    """Process single claim through Mediqzy"""
    
    payload = {
        "messages": [
            {"role": "system", "content": "You are an insurance claim processor."},
            {"role": "user", "content": f"Review claim: {json.dumps(claim_data)}"}
        ],
        "agent_type": "Claims",
        "temperature": 0.3
    }
    
    response = requests.post(
        "http://localhost:8000/v1/chat/completions",
        json=payload,
        timeout=30
    )
    
    return response.json()

# Process multiple claims in parallel
claims = [
    {"id": "CLM001", "amount": 15000, "days": 3},
    {"id": "CLM002", "amount": 8000, "days": 2},
    {"id": "CLM003", "amount": 25000, "days": 5},
]

results = []
with ThreadPoolExecutor(max_workers=3) as executor:
    futures = [executor.submit(process_claim, claim) for claim in claims]
    
    for future in as_completed(futures):
        results.append(future.result())

# Print results
for result in results:
    model = result["model"]
    response = result["choices"][0]["message"]["content"]
    print(f"Model: {model}\nAssessment: {response}\n")
```

---

## Streaming Response (Advanced)

```python
import httpx
import json

async def stream_from_mediqzy():
    """Stream response tokens as they arrive"""
    
    payload = {
        "messages": [
            {"role": "user", "content": "Explain diabetes management in 5 steps"}
        ],
        "agent_type": "MedicalQA"
    }
    
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            "http://localhost:8000/v1/chat/completions",
            json=payload
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    if "choices" in data:
                        delta = data["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            print(content, end="", flush=True)

# Run async function
import asyncio
asyncio.run(stream_from_mediqzy())
```

---

## Error Handling & Fallback

```python
def ask_with_fallback(question, agent_type="MedicalQA"):
    """Ask question with fallback handling"""
    
    try:
        # Try external LLM (Mediqzy)
        response = requests.post(
            "http://localhost:8000/v1/chat/completions",
            json={
                "messages": [{"role": "user", "content": question}],
                "agent_type": agent_type
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            model = result["model"]
            
            # Check if it came from external or local
            if "mediqzy" in model:
                print(f"✅ Using Mediqzy: {model}")
            else:
                print(f"⚠️  Fell back to local: {model}")
            
            return result["choices"][0]["message"]["content"]
        else:
            print(f"❌ Error {response.status_code}: {response.text}")
            
    except requests.Timeout:
        print("⚠️  Request timeout - ensure Mediqzy API is accessible")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    return "Unable to process request"

# Test
response = ask_with_fallback("What is diabetes?")
print(response)
```

---

## Monitoring & Logging

```bash
# See all Mediqzy routing decisions
tail -f logs/inference.log | grep "external_llm"

# Count successful external LLM calls
grep "Routing to external LLM" logs/inference.log | wc -l

# Count fallback occurrences
grep "falling back to local" logs/inference.log | wc -l

# Get statistics
echo "External LLM Usage:"
echo "Successful: $(grep 'Routing to external LLM' logs/inference.log | grep -c 'mediqzy')"
echo "Fallbacks: $(grep 'falling back to local' logs/inference.log | wc -l)"
```

---

## API Response Codes

| Code | Meaning | Example |
|------|---------|---------|
| `200` | Success | Response from Mediqzy or local |
| `400` | Bad request | Invalid messages or agent_type |
| `401` | Unauthorized | Missing/invalid JWT token |
| `500` | Server error | Internal error (falls back to local) |

---

**Ready to integrate!** 🚀

For more examples, see:
- `MEDIQZY_QUICK_START.md` - Quick setup
- `docs/EXTERNAL_LLM_INTEGRATION.md` - Complete reference
- `app/services/external_llm.py` - Source code
