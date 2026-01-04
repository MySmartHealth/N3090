# Agent API Keys & Web Scraping Guide

Complete guide for agent-wise authentication and knowledge base web scraping.

## Table of Contents
- [Agent API Key Management](#agent-api-key-management)
- [Web Scraping for Knowledge Base](#web-scraping-for-knowledge-base)
- [Training LLMs with Scraped Data](#training-llms-with-scraped-data)
- [API Reference](#api-reference)
- [Examples](#examples)

---

## Agent API Key Management

### Overview
Secure your agents with individual API keys for granular access control. Each agent type (Claims, Billing, MedicalQA, etc.) can have its own API key.

### Features
- **Agent-specific authentication**: Separate keys for each agent type
- **Secure key generation**: Cryptographically secure tokens
- **Key lifecycle management**: Create, list, verify, and delete keys
- **Admin-only operations**: Requires master admin key

### Setup

1. **Set Admin API Key** (environment variable):
```bash
export ADMIN_API_KEY="your-super-secret-admin-key-here"
```

2. **Add to ecosystem.config.js**:
```javascript
env: {
  ADMIN_API_KEY: process.env.ADMIN_API_KEY || 'dev-admin-key'
}
```

3. **Restart API Gateway**:
```bash
pm2 restart api-gateway --update-env
```

### Usage

#### Create Agent API Key

Create a new API key for an agent:

```bash
curl -X POST http://localhost:8000/v1/admin/agent-keys \
  -H "X-Admin-Key: your-super-secret-admin-key-here" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "Claims",
    "description": "Insurance claims processing agent"
  }'
```

Response:
```json
{
  "agent_type": "Claims",
  "api_key": "agent-claims-8f7e6d5c4b3a2918e7f6d5c4b3a29180",
  "created_at": "2026-01-04T10:30:00",
  "description": "Insurance claims processing agent"
}
```

**Save the API key securely - it won't be shown again in full!**

#### List All Agent Keys

View all configured agent keys (keys are masked):

```bash
curl http://localhost:8000/v1/admin/agent-keys \
  -H "X-Admin-Key: your-super-secret-admin-key-here"
```

Response:
```json
{
  "agent_keys": [
    {
      "agent_type": "Claims",
      "api_key_preview": "agent-claims-8f7e6d...",
      "created_at": "2026-01-04T10:30:00",
      "description": "Insurance claims processing agent"
    },
    {
      "agent_type": "MedicalQA",
      "api_key_preview": "agent-medicalqa-9a8b...",
      "created_at": "2026-01-04T11:15:00",
      "description": "Medical Q&A agent"
    }
  ],
  "total": 2
}
```

#### Delete Agent Key

Remove an agent's API key:

```bash
curl -X DELETE http://localhost:8000/v1/admin/agent-keys/Claims \
  -H "X-Admin-Key: your-super-secret-admin-key-here"
```

#### Verify Agent Key

Test if an agent key is valid:

```bash
curl -X POST "http://localhost:8000/v1/admin/agent-keys/verify?agent_type=Claims" \
  -H "X-Agent-Key: agent-claims-8f7e6d5c4b3a2918e7f6d5c4b3a29180"
```

Response:
```json
{
  "valid": true,
  "agent_type": "Claims",
  "message": "API key is valid"
}
```

### Using Agent Keys in Requests

Once an agent has a configured API key, all requests to that agent require the key:

```bash
# Get JWT token first
TOKEN=$(curl -s -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"SecureAdmin2026!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Use Claims agent with API key
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Agent-Key: agent-claims-8f7e6d5c4b3a2918e7f6d5c4b3a29180" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Is diabetes treatment covered?"}],
    "agent_type": "Claims",
    "max_tokens": 512
  }'
```

### Security Best Practices

1. **Store admin key securely**: Use environment variables, never commit to git
2. **Rotate keys regularly**: Delete old keys and create new ones periodically
3. **Use different keys per agent**: Don't reuse keys across agent types
4. **Monitor key usage**: Check logs for unauthorized access attempts
5. **Revoke compromised keys immediately**: Delete and regenerate if leaked

---

## Web Scraping for Knowledge Base

### Overview
Automatically scrape websites to populate your RAG knowledge base. Supports HTML pages, PDFs, and medical content filtering.

### Features
- **Multi-format support**: HTML, PDF, plain text
- **Recursive crawling**: Follow links with depth control
- **Parallel scraping**: Scrape multiple URLs simultaneously
- **Medical content filtering**: Specialized scraper for medical sources
- **Auto-ingestion**: Directly add scraped content to knowledge base
- **Trusted sources**: Built-in list of verified medical websites

### Installation

Install required dependencies:

```bash
cd /home/dgs/N3090/services/inference-node
pip install beautifulsoup4==4.12.3 PyPDF2==3.0.1 aiohttp==3.11.11
```

### Usage

#### Scrape Single Website

Scrape a single URL and ingest to knowledge base:

```bash
# Get authentication token
TOKEN=$(curl -s -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"SecureAdmin2026!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Scrape CDC diabetes information
curl -X POST http://localhost:8000/v1/knowledge/scrape \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.cdc.gov/diabetes/basics/index.html",
    "specialty": "endocrinology",
    "doc_type": "guideline",
    "follow_links": true,
    "max_depth": 2,
    "ingest_to_kb": true
  }'
```

Response:
```json
{
  "documents_scraped": 15,
  "documents_ingested": 15,
  "documents": [
    {
      "content": "Diabetes is a chronic condition...",
      "title": "Diabetes Basics - CDC",
      "source_url": "https://www.cdc.gov/diabetes/basics/index.html",
      "specialty": "endocrinology",
      "doc_type": "guideline",
      "scraped_at": "2026-01-04T12:00:00",
      "metadata": {
        "scraper": "WebScraper",
        "content_length": 5420,
        "url": "https://www.cdc.gov/diabetes/basics/index.html"
      }
    }
  ],
  "errors": []
}
```

#### Scrape Multiple URLs

Scrape multiple websites in parallel:

```bash
curl -X POST http://localhost:8000/v1/knowledge/scrape-multi \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "urls": [
      "https://www.cdc.gov/diabetes/",
      "https://www.niddk.nih.gov/health-information/diabetes",
      "https://www.mayoclinic.org/diseases-conditions/diabetes/symptoms-causes/"
    ],
    "specialty": "endocrinology",
    "doc_type": "reference",
    "follow_links": false,
    "ingest_to_kb": true
  }'
```

#### Scrape Medical Guidelines

Specialized endpoint for medical guidelines (coming soon):

```bash
curl -X POST http://localhost:8000/v1/knowledge/scrape-medical-guidelines \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "disease": "diabetes",
    "max_results": 10,
    "ingest_to_kb": true
  }'
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | string | required | Website URL to scrape |
| `specialty` | string | "general" | Medical specialty (endocrinology, cardiology, etc.) |
| `doc_type` | string | "reference" | Document type (reference, guideline, research) |
| `follow_links` | boolean | false | Whether to follow links on page |
| `max_depth` | integer | 2 | Maximum link depth to follow |
| `ingest_to_kb` | boolean | true | Auto-ingest to knowledge base |

### Trusted Medical Sources

The medical scraper includes built-in trust list:

- **Government**: NIH, CDC, FDA
- **Journals**: NEJM, BMJ, The Lancet
- **Clinical**: Mayo Clinic, Cleveland Clinic, UpToDate
- **Databases**: PubMed, MedlinePlus
- **Organizations**: WHO, AMA

### Content Filtering

The scraper automatically:
- Removes navigation, headers, footers
- Extracts main content only
- Filters out scripts and styles
- Cleans up whitespace
- Skips very short pages (<100 chars)
- Deduplicates content

---

## Training LLMs with Scraped Data

### Overview
Use scraped content to fine-tune your medical LLMs with domain-specific knowledge.

### Workflow

1. **Scrape Medical Content**
   ```bash
   # Scrape multiple medical sources
   curl -X POST http://localhost:8000/v1/knowledge/scrape-multi \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "urls": [
         "https://www.cdc.gov/diabetes/",
         "https://www.nhlbi.nih.gov/health/heart-disease",
         "https://www.cancer.gov/about-cancer"
       ],
       "specialty": "general_medicine",
       "ingest_to_kb": true
     }'
   ```

2. **Collect Training Data**
   
   User interactions with the scraped knowledge are automatically saved to the database for training.

3. **Export Dataset**
   ```bash
   curl -X POST http://localhost:8000/v1/training/export-dataset \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "agent_types": ["MedicalQA", "Clinical"],
       "min_rating": 3,
       "format": "jsonl",
       "output_file": "medical_qa_dataset.jsonl"
     }'
   ```

4. **Fine-Tune Model**
   ```bash
   curl -X POST http://localhost:8000/v1/training/lora-finetune \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "base_model": "BioMistral-7B",
       "dataset_path": "medical_qa_dataset.jsonl",
       "output_dir": "./models/biomistral-finetuned",
       "lora_config": {
         "r": 16,
         "lora_alpha": 32,
         "lora_dropout": 0.1,
         "target_modules": ["q_proj", "v_proj"]
       },
       "training_args": {
         "num_train_epochs": 3,
         "learning_rate": 2e-4,
         "per_device_train_batch_size": 4
       }
     }'
   ```

### Training Pipeline

```
Web Scraping → Knowledge Base → User Interactions → Training Data → Fine-Tuning → Updated Model
     ↓              ↓                   ↓                  ↓              ↓
  Medical        RAG           Conversations        Dataset        LoRA Adapter
  Websites     Retrieval       + Ratings           Export         Training
```

### Self-Learning Loop

The system creates a continuous improvement cycle:

1. **Scrape** new medical content
2. **Ingest** to RAG knowledge base
3. **Serve** via agents with RAG retrieval
4. **Collect** user feedback and ratings
5. **Export** high-quality interactions
6. **Train** model with LoRA/QLoRA
7. **Deploy** improved model
8. **Repeat** → Continuous improvement

---

## API Reference

### Agent API Keys

#### `POST /v1/admin/agent-keys`
Create agent API key

**Headers:**
- `X-Admin-Key`: Admin API key (required)
- `Content-Type`: application/json

**Body:**
```json
{
  "agent_type": "Claims",
  "description": "Optional description"
}
```

**Response:** `AgentAPIKeyResponse`

---

#### `GET /v1/admin/agent-keys`
List all agent keys

**Headers:**
- `X-Admin-Key`: Admin API key (required)

**Response:**
```json
{
  "agent_keys": [...],
  "total": 2
}
```

---

#### `DELETE /v1/admin/agent-keys/{agent_type}`
Delete agent key

**Headers:**
- `X-Admin-Key`: Admin API key (required)

**Response:**
```json
{
  "message": "API key deleted for Claims"
}
```

---

#### `POST /v1/admin/agent-keys/verify`
Verify agent key

**Query Params:**
- `agent_type`: Agent type (required)

**Headers:**
- `X-Agent-Key`: Agent API key to verify

**Response:**
```json
{
  "valid": true,
  "agent_type": "Claims",
  "message": "API key is valid"
}
```

---

### Web Scraping

#### `POST /v1/knowledge/scrape`
Scrape single website

**Headers:**
- `Authorization`: Bearer JWT token (required)
- `Content-Type`: application/json

**Body:**
```json
{
  "url": "https://www.cdc.gov/diabetes/",
  "specialty": "endocrinology",
  "doc_type": "guideline",
  "follow_links": true,
  "max_depth": 2,
  "ingest_to_kb": true
}
```

**Response:** `WebScrapeResponse`

---

#### `POST /v1/knowledge/scrape-multi`
Scrape multiple websites

**Headers:**
- `Authorization`: Bearer JWT token (required)
- `Content-Type`: application/json

**Body:**
```json
{
  "urls": ["https://url1.com", "https://url2.com"],
  "specialty": "general",
  "doc_type": "reference",
  "follow_links": false,
  "ingest_to_kb": true
}
```

**Response:** `WebScrapeResponse`

---

## Examples

### Example 1: Populate Insurance Knowledge Base

```bash
#!/bin/bash

# Authenticate
TOKEN=$(curl -s -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"SecureAdmin2026!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Scrape insurance websites
curl -X POST http://localhost:8000/v1/knowledge/scrape-multi \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "urls": [
      "https://www.healthcare.gov/glossary/",
      "https://www.cms.gov/medicare/coverage/",
      "https://www.naic.org/health_insurance.htm"
    ],
    "specialty": "insurance",
    "doc_type": "reference",
    "follow_links": true,
    "max_depth": 1,
    "ingest_to_kb": true
  }'
```

### Example 2: Create Agent Keys for All Agents

```bash
#!/bin/bash

ADMIN_KEY="your-super-secret-admin-key-here"
AGENTS=("Claims" "Billing" "MedicalQA" "Clinical" "Documentation")

for AGENT in "${AGENTS[@]}"; do
  echo "Creating key for $AGENT..."
  curl -s -X POST http://localhost:8000/v1/admin/agent-keys \
    -H "X-Admin-Key: $ADMIN_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"agent_type\":\"$AGENT\",\"description\":\"API key for $AGENT agent\"}" \
    | python3 -m json.tool
  echo ""
done
```

### Example 3: Scrape and Train Pipeline

```bash
#!/bin/bash

TOKEN=$(curl -s -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"SecureAdmin2026!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Step 1: Scrape medical guidelines
echo "Scraping medical guidelines..."
curl -X POST http://localhost:8000/v1/knowledge/scrape \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.cdc.gov/diabetes/managing/",
    "specialty": "endocrinology",
    "doc_type": "guideline",
    "follow_links": true,
    "max_depth": 2,
    "ingest_to_kb": true
  }'

# Step 2: Check knowledge base stats
echo "Checking knowledge base..."
curl -s http://localhost:8000/v1/knowledge/stats \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -m json.tool

# Step 3: Export training dataset (after users interact with system)
echo "Exporting training dataset..."
curl -X POST http://localhost:8000/v1/training/export-dataset \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_types": ["MedicalQA"],
    "min_rating": 4,
    "format": "jsonl"
  }'

# Step 4: Start LoRA fine-tuning
echo "Starting fine-tuning..."
curl -X POST http://localhost:8000/v1/training/lora-finetune \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "base_model": "BiMediX2-8B",
    "dataset_path": "training_data.jsonl",
    "output_dir": "./models/bimedix-diabetes-tuned",
    "lora_config": {"r": 16, "lora_alpha": 32},
    "training_args": {"num_train_epochs": 2}
  }'
```

---

## Troubleshooting

### Web Scraping Issues

**Error: "Web scraper not available"**
```bash
# Install dependencies
pip install beautifulsoup4 PyPDF2 aiohttp
pm2 restart api-gateway
```

**Error: "Failed to fetch URL"**
- Check URL is accessible
- Verify firewall/proxy settings
- Try with `follow_links: false` first
- Check website doesn't block scrapers (User-Agent)

**Too many documents scraped**
- Reduce `max_depth` parameter
- Set `follow_links: false`
- Use more specific URLs

### Agent Key Issues

**Error: "ADMIN_API_KEY not configured"**
```bash
export ADMIN_API_KEY="your-key-here"
pm2 restart api-gateway --update-env
```

**Error: "Invalid API key for agent"**
- Check key is correctly copied (no spaces)
- Verify agent type matches
- Re-create key if lost

---

## Next Steps

1. **Configure admin key**: Set `ADMIN_API_KEY` in environment
2. **Create agent keys**: Generate keys for each agent type
3. **Scrape medical content**: Populate knowledge base with domain content
4. **Monitor usage**: Check logs for scraping and key verification
5. **Set up training**: Configure continuous learning pipeline

For more information, see:
- [Agentic AI Guide](AGENTIC_AI_GUIDE.md)
- [Knowledge Base Documentation](docs/)
- [Training Pipeline Guide](app/training.py)
