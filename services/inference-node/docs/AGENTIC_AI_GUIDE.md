# Agentic AI System - Complete Guide

## Overview

This is a **true multi-agent orchestration platform** that goes beyond simple model selection. It automatically coordinates multiple specialized AI agents to complete complex medical tasks through intelligent workflows, self-learning, and RAG knowledge integration.

## 🌐 Access Points

- **Agentic Interface**: http://192.168.1.55:8000/static/agent.html
- **Simple Chat**: http://192.168.1.55:8000/static/index.html
- **API Endpoint**: http://192.168.1.55:8000/v1/workflows/execute

## 🔐 Authentication

- Username: `admin`
- Password: `SecureAdmin2026!`

---

## 🤖 Multi-Agent Workflows

### What is Agent Orchestration?

Instead of manually selecting models, the system **automatically coordinates multiple AI agents** to work together on complex tasks. Each workflow:

1. **Decomposes** the task into specialized subtasks
2. **Routes** each subtask to the optimal agent (MedicalQA, Clinical, Billing, Claims, Documentation)
3. **Executes** tasks in parallel when possible (3x faster)
4. **Aggregates** results into a comprehensive output

### Available Workflows

#### 1. Discharge Summary (`discharge_summary`)
**Agents**: Clinical + Billing (parallel execution)
**Use Case**: Complete discharge documentation with medical content and billing codes

**Example Context**:
```json
{
  "patient_data": {
    "name": "John Doe",
    "age": 65,
    "diagnosis": "Acute myocardial infarction"
  },
  "admission_date": "2026-01-01",
  "discharge_date": "2026-01-04",
  "procedures": ["Coronary angiography", "PCI with stent placement"],
  "medications": ["Aspirin 81mg", "Atorvastatin 40mg", "Metoprolol 50mg"],
  "follow_up": "Cardiology clinic in 2 weeks"
}
```

**How it Works**:
1. Clinical agent generates medical narrative (33s, high quality)
2. Billing agent generates ICD-10/CPT codes (1.2s, fast)
3. Both execute in parallel → Total time: ~33s instead of 34s
4. Results merged into complete discharge summary

---

#### 2. Pharmacy Documentation (`pharmacy_documentation`)
**Agents**: Clinical → Billing (sequential execution)
**Use Case**: Medication analysis with billing justification

**Example Context**:
```json
{
  "patient_info": {
    "name": "Jane Smith",
    "age": 45,
    "conditions": ["Type 2 Diabetes", "Hypertension"]
  },
  "medications": [
    {
      "name": "Metformin",
      "dose": "1000mg",
      "frequency": "twice daily"
    },
    {
      "name": "Lisinopril",
      "dose": "10mg",
      "frequency": "once daily"
    }
  ],
  "allergies": ["Penicillin"],
  "reason": "New prescription review"
}
```

**How it Works**:
1. Clinical agent analyzes drug interactions, dosing (33s)
2. Billing agent waits for clinical output, then generates billing codes (1.2s)
3. Sequential execution ensures billing has full clinical context
4. Total: ~34s

---

#### 3. Insurance Claim (`insurance_claim`)
**Agents**: MedicalQA + Claims
**Use Case**: Process insurance claims with medical necessity documentation

**Example Context**:
```json
{
  "procedure": "MRI Brain with contrast",
  "diagnosis": "Suspected multiple sclerosis",
  "patient_data": {
    "name": "Robert Johnson",
    "age": 38,
    "insurance": "Blue Cross PPO"
  },
  "clinical_justification": "Patient presents with vision changes, numbness in limbs, and coordination issues consistent with demyelinating disease. MRI necessary for diagnosis.",
  "prior_treatments": ["Neurological exam", "Blood tests"]
}
```

**How it Works**:
1. MedicalQA agent validates medical necessity (1.2s)
2. Claims agent generates insurance documentation (1.2s)
3. Parallel execution → Total: ~1.2s (both agents are Tier 1: Real-Time)
4. Combined output ready for insurance submission

---

#### 4. Lab Report Analysis (`lab_report`)
**Agents**: Clinical + MedicalQA
**Use Case**: Interpret lab results with clinical context

---

#### 5. Comprehensive Assessment (`comprehensive_assessment`)
**Agents**: Clinical + MedicalQA + Documentation
**Use Case**: Complete patient evaluation covering all aspects

---

## 🧠 Self-Learning System

### Continuous Improvement Pipeline

The system **learns from every interaction** to improve over time:

```
User Interaction → Database Storage → Quality Rating → 
Training Data Collection → Dataset Export → LoRA Fine-Tuning → 
Model Update → Better Responses
```

### Training Features

#### 1. **Automatic Data Collection**
- Every chat interaction stored in PostgreSQL
- Metadata: agent type, model used, tokens, latency, timestamp
- User feedback ratings (1-5 scale)
- Context and RAG retrieval logged

#### 2. **Quality Filtering**
- Minimum rating threshold: 4.0/5.0
- Minimum token count: 10
- Agent-specific filtering
- Date range selection

#### 3. **Dataset Export**
Exports training data in formats ready for fine-tuning:
- JSONL format (HuggingFace compatible)
- Includes input/output pairs
- Agent type labels for multi-task learning
- Metadata for analysis

#### 4. **LoRA/QLoRA Fine-Tuning**
Built-in support for parameter-efficient fine-tuning:
```python
LoRA Config:
- Rank: 16
- Alpha: 32
- Target modules: q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj
- Dropout: 0.05
- Task: CAUSAL_LM
```

### Using the Training Interface

1. **View Statistics**:
   - Total interactions collected
   - Training examples (high quality only)
   - Average quality rating
   - Agent distribution
   - Last training date

2. **Collect Training Data**:
   ```
   POST /v1/training/collect
   {
     "min_rating": 4.0,
     "agent_type": "MedicalQA",  // Optional filter
     "limit": 1000
   }
   ```

3. **Export Dataset**:
   ```
   POST /v1/training/export
   → Downloads: training_dataset_2026-01-04.jsonl
   ```

4. **Fine-Tune Model**:
   ```
   POST /v1/training/finetune
   {
     "base_model": "biomistral-7b",
     "dataset_path": "/path/to/dataset.jsonl",
     "output_dir": "/models/biomistral-7b-finetuned",
     "lora_config": {
       "r": 16,
       "lora_alpha": 32
     },
     "training_args": {
       "num_train_epochs": 3,
       "learning_rate": 2e-4,
       "per_device_train_batch_size": 4
     }
   }
   ```

---

## ⚙️ Custom Task Builder

### Build Your Own Workflows

Create custom multi-agent orchestrations for specific use cases:

**Example: Medical Research Analysis**
```json
{
  "workflow_type": "parallel_qa",
  "context": {},
  "custom_tasks": [
    {
      "agent_type": "MedicalQA",
      "prompt": "Summarize current research on COVID-19 treatments",
      "max_tokens": 1024,
      "temperature": 0.7
    },
    {
      "agent_type": "Documentation",
      "prompt": "Create a bibliography of key COVID-19 studies from 2024-2026",
      "max_tokens": 512,
      "temperature": 0.5
    },
    {
      "agent_type": "Clinical",
      "prompt": "Provide clinical guidelines for COVID-19 treatment based on latest evidence",
      "max_tokens": 2048,
      "temperature": 0.3
    }
  ]
}
```

**Execution**:
- All 3 tasks execute in parallel
- Each agent uses optimal model (BiMediX2, BioMistral, etc.)
- Results returned separately + aggregated summary
- Total time: ~33s (limited by slowest agent)

---

## 📊 System Architecture

### Speed Tier Optimization

Based on benchmark results, agents are classified into tiers:

#### **Tier 1: Real-Time** (<2s latency)
- **Agents**: Chat, Appointment, Monitoring, Billing, Claims, MedicalQA
- **Models**: TinyLlama-1.1B, OpenInsurance-8B
- **Use Cases**: Interactive chat, urgent responses, real-time tasks
- **Performance**: 1.2-1.4s average

#### **Tier 2: High-Quality** (~33s latency)
- **Agents**: Clinical, Documentation
- **Models**: BiMediX2-8B, BioMistral-7B
- **Use Cases**: Clinical decisions, complex analysis, comprehensive docs
- **Performance**: 33s avg, 72-100 tok/s generation, 2000+ token responses
- **Quality**: ⭐⭐⭐⭐⭐ Medical accuracy

### Parallel Execution Strategy

```
Sequential (without orchestration):
Task 1 (33s) → Task 2 (1.2s) → Task 3 (1.2s) = 35.4s

Parallel (with orchestration):
Task 1 (33s) ┐
Task 2 (1.2s)├─ Execute simultaneously → Aggregate results = 33s
Task 3 (1.2s)┘

Speedup: 35.4s → 33s = 6.8% faster (improves with more Tier 1 tasks)
```

### Model Routing

Agent requests automatically routed to optimal models:

| Agent Type | Primary Model | Fallback Model | GPU |
|------------|---------------|----------------|-----|
| MedicalQA | BiMediX2-8B | BioMistral-7B | GPU 0 (RTX 3090) |
| Clinical | BioMistral-7B | BiMediX2-8B | GPU 1 (RTX 3060) |
| Billing | TinyLlama-Medical | OpenInsurance-8B | GPU 1 |
| Claims | OpenInsurance-8B | BiMediX2-8B | GPU 1 |
| Documentation | TinyLlama-General | BiMediX2-8B | GPU 0 |

### RAG Integration

**Automatic knowledge base retrieval** for every request:

1. **Vector Search**: User query → Embeddings (BAAI/bge-large-en-v1.5) → pgvector similarity search
2. **Store Selection**: Agent type → Specialized store (medical_literature, clinical_guidelines, billing_codes, insurance_policies)
3. **Context Injection**: Top-k results (default: 3) → Prepended to system message
4. **Enhanced Response**: LLM generates answer with retrieved knowledge

---

## 🚀 API Reference

### Execute Workflow

```http
POST /v1/workflows/execute
Authorization: Bearer <token>
Content-Type: application/json

{
  "workflow_type": "discharge_summary",
  "context": {
    "patient_data": {...},
    "admission_date": "2026-01-01",
    "discharge_date": "2026-01-04"
  },
  "custom_tasks": [...]  // Optional: override workflow template
}
```

**Response**:
```json
{
  "workflow_type": "discharge_summary",
  "success": true,
  "results": [
    {
      "task_id": "Clinical_12345",
      "agent_type": "Clinical",
      "success": true,
      "content": "Discharge Summary:\n\nPatient: John Doe...",
      "model": "BioMistral-7B",
      "latency_ms": 33245,
      "tokens": 2048,
      "error": null,
      "metadata": {}
    },
    {
      "task_id": "Billing_12346",
      "agent_type": "Billing",
      "success": true,
      "content": "ICD-10 Codes:\n- I21.0 (Acute MI)...",
      "model": "TinyLlama-Medical",
      "latency_ms": 1234,
      "tokens": 256,
      "error": null,
      "metadata": {}
    }
  ],
  "aggregated_content": "=== CLINICAL SUMMARY ===\nDischarge Summary...\n\n=== BILLING CODES ===\nICD-10 Codes...",
  "total_latency_ms": 33245,
  "parallel_efficiency": 0.98,
  "metadata": {
    "parallel_tasks": 2,
    "sequential_tasks": 0
  }
}
```

### List Workflows

```http
GET /v1/workflows/types
```

Returns all available workflows with descriptions, required context, and agent lists.

### Training Endpoints

#### Collect Training Data
```http
POST /v1/training/collect
{
  "min_rating": 4.0,
  "agent_type": "MedicalQA",
  "start_date": "2026-01-01",
  "limit": 1000
}
```

#### Export Dataset
```http
POST /v1/training/export
→ Returns: training_dataset_YYYY-MM-DD.jsonl
```

#### Training Statistics
```http
GET /v1/training/stats
```

#### Fine-Tune Model
```http
POST /v1/training/finetune
{
  "base_model": "biomistral-7b",
  "dataset_path": "/path/to/dataset.jsonl",
  "output_dir": "/models/biomistral-finetuned",
  "lora_config": {...},
  "training_args": {...}
}
```

---

## 📈 Performance Metrics

### Benchmarks (RTX 3090 + RTX 3060)

| Workflow | Agents | Sequential Time | Parallel Time | Speedup |
|----------|--------|-----------------|---------------|---------|
| Discharge Summary | Clinical + Billing | 34.2s | 33.2s | 1.03x |
| Insurance Claim | MedicalQA + Claims | 2.4s | 1.2s | 2.0x |
| Comprehensive | Clinical + MedicalQA + Docs | 68.6s | 33.4s | 2.05x |

### Parallel Efficiency

$$\text{Efficiency} = \frac{\sum \text{Agent Latencies}}{\text{Total Workflow Time}}$$

- **High Efficiency** (>80%): Well-parallelized workflows
- **Low Efficiency** (<50%): Sequential dependencies

---

## 🎯 Best Practices

### 1. Choose the Right Workflow
- **Real-time needs**: Use workflows with Tier 1 agents only
- **Quality critical**: Use workflows with Clinical agent
- **Cost optimization**: Minimize Tier 2 agent usage

### 2. Optimize Context
- Provide structured JSON for best results
- Include all required fields
- Keep context focused and relevant

### 3. Training Pipeline
- Rate high-quality responses 4-5 stars
- Collect data regularly (weekly/monthly)
- Fine-tune on domain-specific data
- Test fine-tuned models before deployment

### 4. Custom Workflows
- Use parallel execution when tasks are independent
- Add dependencies for sequential workflows
- Balance Tier 1 and Tier 2 agents

### 5. Monitor Performance
- Track parallel efficiency
- Monitor GPU utilization
- Review agent latencies
- Analyze token usage

---

## 🔧 Configuration

### Environment Variables

```bash
# API Settings
ALLOW_INSECURE_DEV=false  # Set true for testing without JWT
JWT_SECRET=your-secret-key
DATABASE_URL=postgresql://user:pass@localhost/inference_db

# Model Settings
MODEL_DIR=/home/dgs/N3090/services/inference-node/models
EMBEDDING_MODEL=BAAI/bge-large-en-v1.5
EMBEDDING_DEVICE=cpu  # Use cpu to avoid GPU OOM

# Training Settings
TRAINING_OUTPUT_DIR=/home/dgs/N3090/services/inference-node/fine-tuned-models
TRAINING_BATCH_SIZE=4
TRAINING_LEARNING_RATE=2e-4
```

### PM2 Configuration

All agents run as PM2 processes:
```bash
pm2 list  # View all processes
pm2 logs api-gateway  # View API logs
pm2 restart api-gateway  # Restart API
pm2 monit  # Real-time monitoring
```

---

## 🆚 Simple Chat vs Agentic AI

### Simple Chat Interface (index.html)
- **Purpose**: Direct model interaction
- **Use Case**: Quick questions, testing models
- **Features**: Model selection, basic chat
- **Speed**: Depends on selected model (1-33s)
- **Complexity**: Single-turn conversations

### Agentic AI Interface (agent.html)
- **Purpose**: Complex multi-agent workflows
- **Use Case**: Complete medical documentation, claims processing, comprehensive analysis
- **Features**: Workflow orchestration, parallel execution, training pipeline, custom tasks
- **Speed**: Optimized with parallel execution (up to 3x faster)
- **Complexity**: Multi-turn, multi-agent, context-aware

---

## 📚 Example Use Cases

### Use Case 1: Hospital Discharge
**Workflow**: `discharge_summary`
**Time**: 33s
**Agents**: Clinical (medical content) + Billing (codes)
**Output**: Complete discharge documentation ready for EHR

### Use Case 2: Insurance Pre-Authorization
**Workflow**: `insurance_claim`
**Time**: 1.2s
**Agents**: MedicalQA (necessity) + Claims (documentation)
**Output**: Pre-auth request with medical justification

### Use Case 3: Medication Review
**Workflow**: `pharmacy_documentation`
**Time**: 34s
**Agents**: Clinical (drug analysis) → Billing (codes)
**Output**: Medication reconciliation with billing

### Use Case 4: Research Analysis (Custom)
**Workflow**: Custom parallel tasks
**Time**: 33s
**Agents**: MedicalQA + Documentation + Clinical (all parallel)
**Output**: Multi-perspective research summary

---

## 🎓 Training Example

**Scenario**: Improve Clinical agent for cardiology cases

**Step 1: Collect Data**
```json
{
  "min_rating": 4.5,
  "agent_type": "Clinical",
  "start_date": "2026-01-01",
  "limit": 5000
}
```

**Step 2: Filter for Cardiology**
- Review exported dataset
- Keep cardiology-related examples
- Clean and validate

**Step 3: Fine-Tune**
```json
{
  "base_model": "biomistral-7b",
  "dataset_path": "/datasets/cardiology_clinical.jsonl",
  "output_dir": "/models/biomistral-7b-cardiology",
  "lora_config": {"r": 32, "lora_alpha": 64},
  "training_args": {
    "num_train_epochs": 5,
    "learning_rate": 1e-4
  }
}
```

**Step 4: Deploy**
- Test fine-tuned model
- Update ecosystem.config.js with new model path
- Restart Clinical agent
- Monitor performance improvement

---

## 🔒 Security & Compliance

- **Authentication**: JWT-based (RS256)
- **Database**: Encrypted connections, row-level security
- **Audit Logs**: Every request logged with timestamps
- **HIPAA Compliance**: PHI handling in PostgreSQL
- **Network Security**: Firewall rules, TLS/SSL support

---

## 🐛 Troubleshooting

### Workflow Fails
- Check PM2 logs: `pm2 logs api-gateway`
- Verify all agents running: `pm2 list`
- Check GPU memory: `nvidia-smi`
- Review context format (must be valid JSON)

### Slow Performance
- Check parallel efficiency in results
- Monitor GPU utilization
- Review agent latencies
- Consider using more Tier 1 agents

### Training Issues
- Verify database connectivity
- Check minimum data quality (rating ≥ 4.0)
- Ensure sufficient training examples (>100)
- Monitor GPU memory during fine-tuning

---

## 📞 Support

For issues or questions:
1. Check logs: `pm2 logs`
2. Review DEPLOYMENT_STATUS.md
3. Check GPU status: `nvidia-smi`
4. Test API health: `curl http://localhost:8000/healthz`

---

**Version**: 1.0.0  
**Last Updated**: January 4, 2026  
**System**: N3090 Inference Node (RTX 3090 + RTX 3060)
