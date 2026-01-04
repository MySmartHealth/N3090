# Knowledge Base & Self-Learning System

## Overview

Complete knowledge management and self-learning system that enables the medical AI to:

1. **Ingest Knowledge** - Load PDFs, web pages, clinical guidelines, research papers
2. **Attribute Sources** - Cite evidence and track document origins
3. **Self-Learn** - Improve continuously from user feedback and corrections
4. **Validate Knowledge** - Verify accuracy and update outdated information
5. **Fill Gaps** - Identify and address knowledge deficiencies

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Knowledge Base System                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Document   │    │    Source    │    │ Self-Learning│  │
│  │  Ingestion   │───▶│ Attribution  │───▶│    Engine    │  │
│  │    Engine    │    │    Engine    │    │              │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│         │                    │                    │          │
│         ▼                    ▼                    ▼          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         PostgreSQL + pgvector Database              │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │  │
│  │  │   Medical    │  │ Chat History │  │   User    │ │  │
│  │  │  Documents   │  │  + Feedback  │  │  Context  │ │  │
│  │  │  (HNSW)      │  │             │  │           │ │  │
│  │  └──────────────┘  └──────────────┘  └───────────┘ │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                               │
└─────────────────────────────────────────────────────────────┘
         │                      │                      │
         ▼                      ▼                      ▼
  ┌──────────┐          ┌──────────┐          ┌──────────┐
  │  PDF/Web │          │ Citations│          │Knowledge │
  │ Documents│          │in AI Rsp │          │   Gaps   │
  └──────────┘          └──────────┘          └──────────┘
```

## Components

### 1. Document Ingestion Engine

**Purpose:** Load documents from multiple sources into knowledge base

**Supported Formats:**
- PDF files (clinical guidelines, research papers)
- Web pages (medical resources, hospital protocols)
- Plain text files (notes, references)
- Batch directory ingestion

**Features:**
- Automatic text extraction and chunking
- GPU-accelerated embedding generation (BGE-large-en-v1.5)
- Metadata extraction (specialty, document type, source)
- Quality scoring and validation tracking

**Example Usage:**

```python
from app.knowledge_base import get_ingestion_engine

engine = get_ingestion_engine()

# Ingest PDF
doc_ids = await engine.ingest_pdf(
    pdf_path="./guidelines/hypertension_2024.pdf",
    title="ACC/AHA Hypertension Guidelines 2024",
    specialty="cardiology",
    document_type="clinical_guideline",
    source_url="https://www.acc.org/..."
)

# Ingest web page
doc_id = await engine.ingest_web_page(
    url="https://pubmed.ncbi.nlm.nih.gov/12345678/",
    title="Novel Treatment for Heart Failure",
    specialty="cardiology",
    document_type="research_paper",
    quality_score=0.9  # High quality for peer-reviewed
)
```

### 2. Source Attribution Engine

**Purpose:** Generate citations and attribute sources for AI responses

**Features:**
- Evidence-based response generation
- Automatic citation formatting (Markdown, JSON)
- Relevance scoring for sources
- Page number and excerpt extraction

**Example Usage:**

```python
from app.knowledge_base import get_attribution_engine

engine = get_attribution_engine()

# Generate citations
citations = await engine.generate_citations(
    query="What are the latest guidelines for treating hypertension?",
    specialty="cardiology",
    top_k=5,
    min_score=0.7
)

# Format as markdown
markdown = engine.format_citations_markdown(citations)
# Output:
# **Sources:**
# 1. **ACC/AHA Hypertension Guidelines 2024** (cardiology) - [Link](https://...)
#    *Relevance: 95.3%*
#    > For adults with stage 1 hypertension, lifestyle modifications...

# Format as JSON for API
json_citations = engine.format_citations_json(citations)
```

### 3. Self-Learning Engine

**Purpose:** Continuous improvement from user interactions

**Learning Signals:**
- `positive` - User confirms answer is correct
- `negative` - User indicates answer is wrong
- `correction` - User provides corrected information
- `validation` - User validates cited source

**Learning Loop:**

```
User Interaction → Feedback Collection → Knowledge Update
                                              │
                                              ▼
                                        Fine-tune Models
                                              │
                                              ▼
                                        A/B Test → Deploy
```

**Example Usage:**

```python
from app.knowledge_base import get_learning_engine

engine = get_learning_engine()

# Record user feedback
await engine.record_feedback(
    session_id="session_123",
    message_id=456,
    signal_type="correction",
    rating=2.0,
    user_feedback="The dosage is incorrect",
    correction_text="The recommended starting dose is 10mg, not 20mg"
)

# Identify knowledge gaps
gaps = await engine.identify_knowledge_gaps(
    days_back=7,
    min_occurrences=3
)
# Returns frequently asked questions with poor ratings
```

## Database Schema Updates

### MedicalDocument (Enhanced)

```python
class MedicalDocument:
    # Existing fields
    document_id: str
    title: str
    content: str
    embedding: Vector(1024)
    
    # NEW: Quality tracking
    quality_score: float  # 0.0 - 1.0
    verification_status: str  # verified, unverified, pending_review, outdated
    last_verified: datetime
    verified_by: str
```

### ChatMessage (Enhanced)

```python
class ChatMessage:
    # Existing fields
    session_id: str
    content: str
    
    # NEW: Feedback tracking
    user_rating: float  # 1-5 rating
    user_feedback: str
```

## API Endpoints

### Ingest Documents

```bash
# Ingest from URL
curl -X POST http://localhost:8000/v1/knowledge/ingest/url \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/guideline.html",
    "title": "Clinical Practice Guideline",
    "specialty": "cardiology",
    "document_type": "clinical_guideline",
    "quality_score": 0.85
  }'

# Ingest text content
curl -X POST http://localhost:8000/v1/knowledge/ingest/text \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Hypertension is defined as...",
    "title": "Hypertension Definition",
    "specialty": "cardiology",
    "document_type": "reference"
  }'

# Upload PDF
curl -X POST http://localhost:8000/v1/knowledge/ingest/pdf \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@guideline.pdf" \
  -F "title=ACC/AHA Guidelines" \
  -F "specialty=cardiology"
```

### Search Knowledge Base

```bash
curl -X POST http://localhost:8000/v1/knowledge/search \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the signs of heart failure?",
    "specialty": "cardiology",
    "limit": 10,
    "min_score": 0.7
  }'
```

### Get Citations

```bash
curl -X POST http://localhost:8000/v1/knowledge/citations \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Treatment options for diabetes",
    "specialty": "endocrinology",
    "top_k": 5
  }'
```

### Submit Feedback

```bash
curl -X POST http://localhost:8000/v1/knowledge/feedback \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session_123",
    "message_id": 456,
    "signal_type": "correction",
    "rating": 2.0,
    "correction_text": "The correct dose is 10mg daily"
  }'
```

### Knowledge Gaps Analysis

```bash
curl -X POST http://localhost:8000/v1/knowledge/gaps \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "days_back": 7,
    "min_occurrences": 3
  }'
```

### Knowledge Base Statistics

```bash
curl -X GET http://localhost:8000/v1/knowledge/stats \
  -H "Authorization: Bearer $TOKEN"
```

## CLI Tools

### Batch Ingest Directory

```bash
# Ingest all PDFs and text files from directory
python scripts/manage_knowledge_base.py batch-ingest \
  ./medical-guidelines/ \
  --specialty cardiology \
  --type clinical_guideline
```

### Search from CLI

```bash
python scripts/manage_knowledge_base.py search \
  "What are the symptoms of COVID-19?" \
  --specialty infectious_disease \
  --limit 5
```

### Validate Documents

```bash
# List documents needing validation
python scripts/manage_knowledge_base.py validate \
  --specialty cardiology \
  --max-age 180 \
  --list \
  --limit 20
```

### Find Knowledge Gaps

```bash
python scripts/manage_knowledge_base.py gaps \
  --days 30 \
  --min-occurrences 5
```

### Show Statistics

```bash
python scripts/manage_knowledge_base.py stats
```

## Quality Scoring Guidelines

### Document Types & Default Scores

| Document Type | Default Score | Notes |
|--------------|--------------|-------|
| Peer-reviewed journal | 0.95 | Highest quality |
| Clinical guideline | 0.90 | Official medical societies |
| Hospital protocol | 0.85 | Institution-specific |
| Medical textbook | 0.80 | Established references |
| Government health agency | 0.85 | CDC, WHO, FDA |
| Medical website | 0.60 | Requires validation |
| User submission | 0.50 | Needs expert review |
| User correction | 0.50 | Pending validation |

### Verification Status

- `verified` - Reviewed by medical professional, current
- `unverified` - Not yet validated
- `pending_review` - Flagged for expert review
- `outdated` - Superseded by newer information
- `incorrect` - Contains errors, should be removed

## Self-Learning Workflow

### 1. Collect Feedback

```python
# User rates response
await record_feedback(
    signal_type="positive",
    rating=5.0
)

# User provides correction
await record_feedback(
    signal_type="correction",
    rating=2.0,
    correction_text="The correct dosage is..."
)
```

### 2. Update Knowledge Base

```python
# System automatically creates correction document
# Marks conflicting documents for review
# Notifies administrators of issues
```

### 3. Identify Gaps

```bash
# Weekly analysis of low-rated responses
python scripts/manage_knowledge_base.py gaps --days 7

# Output:
# Found 12 knowledge gaps
# 1. Query: "Long-term effects of metformin"
#    Occurrences: 15
#    Avg Rating: 2.3/5.0
```

### 4. Fill Gaps

```bash
# Ingest new documents addressing gaps
python scripts/manage_knowledge_base.py ingest-pdf \
  ./metformin_long_term_study.pdf \
  --title "Metformin Long-term Effects Study 2024" \
  --specialty endocrinology
```

### 5. Retrain Models

```bash
# Fine-tune with corrected data
python scripts/finetune_model.py \
  --base-model ./models/biomistral-7b-fp16 \
  --agent-type MedicalQA \
  --days-back 30 \
  --use-qlora
```

## Integration with RAG

The knowledge base seamlessly integrates with the RAG engine:

```python
from app.rag_engine import RAGEngine
from app.knowledge_base import get_attribution_engine

# RAG retrieves relevant documents
rag = RAGEngine()
context = await rag.search_medical_knowledge(
    query="How to treat sepsis?",
    specialty="critical_care",
    top_k=5
)

# Attribution engine generates citations
attribution = get_attribution_engine()
citations = await attribution.generate_citations(
    query="How to treat sepsis?",
    specialty="critical_care"
)

# Combine in AI response
response = f"""
Based on current guidelines:
{ai_generated_answer}

{attribution.format_citations_markdown(citations)}
"""
```

## Continuous Learning Loop

### Weekly Maintenance

```bash
#!/bin/bash
# Weekly knowledge base maintenance

# 1. Identify gaps
python scripts/manage_knowledge_base.py gaps \
  --days 7 \
  --min-occurrences 3 > gaps_report.txt

# 2. Validate old documents
python scripts/manage_knowledge_base.py validate \
  --max-age 180 \
  --list > validation_needed.txt

# 3. Retrain models if sufficient feedback
python scripts/finetune_model.py \
  --base-model ./models/biomistral-7b-fp16 \
  --agent-type MedicalQA \
  --days-back 7 \
  --min-examples 100 \
  --use-qlora

# 4. Deploy updated model
./bin/manage_vllm.sh restart biomistral
```

### Monthly Tasks

1. **Quality Audit** - Review verification status distribution
2. **Gap Analysis** - Identify recurring low-rated topics
3. **Source Updates** - Check for new clinical guidelines
4. **Model Evaluation** - Compare fine-tuned vs base performance

## Performance Tips

### Embedding Generation

- **Batch Processing**: Process documents in batches of 32
- **GPU Acceleration**: Use CUDA for sentence-transformers
- **Model Selection**: BGE-large-en-v1.5 (1024-dim) for medical text

### Vector Search

- **HNSW Index**: Provides O(log N) search complexity
- **Specialty Filters**: Pre-filter by specialty before vector search
- **Quality Threshold**: Set min_score=0.7 to filter noise

### Knowledge Ingestion

- **Chunking**: 512 tokens with 50 token overlap
- **PDF Processing**: Extract text with pypdf (faster than PyMuPDF)
- **Web Scraping**: Respect robots.txt, rate limit requests

## Monitoring

### Key Metrics

```python
# Knowledge base health
- Total documents
- Documents by verification status
- Average quality score
- Documents needing validation (>180 days)

# Learning effectiveness
- Feedback signals per week
- Average rating trend
- Knowledge gaps identified
- Gaps resolved
```

### Alerts

Set up alerts for:
- Quality score drop below 0.7 average
- >20% documents unverified
- >10 knowledge gaps with 5+ occurrences
- Correction signals spike (>10/day)

## Best Practices

### 1. Document Quality

✅ **DO:**
- Verify sources from reputable medical organizations
- Include publication dates and update frequency
- Tag with specific specialties
- Set appropriate quality scores

❌ **DON'T:**
- Ingest unverified web content at high quality scores
- Mix different topics in one document
- Skip metadata (specialty, type, source)

### 2. User Feedback

✅ **DO:**
- Encourage specific corrections over vague feedback
- Validate high-impact corrections with experts
- Analyze feedback trends regularly
- Acknowledge and respond to corrections

❌ **DON'T:**
- Ignore negative feedback
- Auto-apply user corrections without review
- Delete contradictory information immediately

### 3. Knowledge Updates

✅ **DO:**
- Schedule regular validation cycles (quarterly)
- Monitor medical society websites for guideline updates
- Version control major knowledge changes
- A/B test knowledge updates before full deployment

❌ **DON'T:**
- Remove old guidelines without archiving
- Update knowledge base during peak usage
- Skip testing after major ingestions

## Troubleshooting

### Issue: PDF extraction fails

**Solution:**
```bash
# Install additional dependencies
pip install pypdf2 pdfminer.six
```

### Issue: Low citation relevance scores

**Solution:**
- Improve query specificity
- Add specialty filters
- Increase chunk overlap
- Retrain embedding model on medical corpus

### Issue: Knowledge gaps not identified

**Solution:**
- Lower min_occurrences threshold
- Expand analysis period (days_back)
- Check if users are providing ratings
- Verify feedback collection integration

### Issue: Slow document ingestion

**Solution:**
- Batch process files in parallel
- Use GPU for embedding generation
- Increase database connection pool
- Chunk large PDFs into smaller sections

## Next Steps

1. **Install Dependencies**
   ```bash
   pip install pypdf beautifulsoup4 requests python-multipart
   ```

2. **Initialize Database Schema**
   ```bash
   python scripts/init_database.py
   ```

3. **Ingest Initial Knowledge Base**
   ```bash
   python scripts/manage_knowledge_base.py batch-ingest \
     ./medical-guidelines/ \
     --specialty general
   ```

4. **Enable Knowledge Routes**
   Add to `app/main.py`:
   ```python
   from app.knowledge_routes import router as knowledge_router
   app.include_router(knowledge_router)
   ```

5. **Start Collecting Feedback**
   Integrate feedback collection in chat UI

6. **Schedule Weekly Maintenance**
   Add cron job for knowledge base validation and gap analysis

## Resources

- **PostgreSQL pgvector**: https://github.com/pgvector/pgvector
- **BGE Embeddings**: https://huggingface.co/BAAI/bge-large-en-v1.5
- **Medical Guidelines**: https://www.acc.org, https://www.aha.org
- **PubMed**: https://pubmed.ncbi.nlm.nih.gov/
- **Clinical Trials**: https://clinicaltrials.gov/
