# Knowledge Base Quick Start Guide

## Installation

```bash
# 1. Install dependencies
cd /home/dgs/N3090/services/inference-node
pip install pypdf beautifulsoup4 requests python-multipart

# 2. Update database schema (adds quality_score, verification_status, etc.)
python scripts/init_database.py

# 3. Verify knowledge routes are enabled
# Check logs for "Knowledge base routes enabled"
```

## Usage Examples

### 1. Ingest Your First Document

**From PDF:**
```bash
python scripts/manage_knowledge_base.py ingest-pdf \
  ./docs/sample_guideline.pdf \
  --title "Hypertension Management Guidelines" \
  --specialty cardiology \
  --type clinical_guideline \
  --url "https://www.acc.org/guidelines/hypertension"
```

**From Web Page:**
```bash
python scripts/manage_knowledge_base.py ingest-web \
  https://www.mayoclinic.org/diseases-conditions/diabetes/symptoms-causes/syc-20371444 \
  --title "Diabetes Overview - Mayo Clinic" \
  --specialty endocrinology \
  --type web_resource \
  --quality 0.75
```

**From Text File:**
```bash
python scripts/manage_knowledge_base.py ingest-text \
  ./protocols/sepsis_protocol.txt \
  --title "Emergency Department Sepsis Protocol" \
  --specialty emergency_medicine \
  --type hospital_protocol
```

**Batch Ingest Directory:**
```bash
# Ingest all PDFs and text files from a directory
python scripts/manage_knowledge_base.py batch-ingest \
  ./medical-guidelines/ \
  --specialty cardiology \
  --type clinical_guideline
```

### 2. Search Knowledge Base

```bash
# Search for specific medical topic
python scripts/manage_knowledge_base.py search \
  "What are the first-line treatments for hypertension?" \
  --specialty cardiology \
  --limit 5

# Output:
# 🔍 Found 5 results for: What are the first-line treatments...
#
# 1. Hypertension Management Guidelines (cardiology)
#    Similarity: 94.2%
#    Type: clinical_guideline
#    Source: https://www.acc.org/guidelines/hypertension
#    Content: First-line therapy for hypertension includes...
```

### 3. View Statistics

```bash
python scripts/manage_knowledge_base.py stats

# Output:
# 📊 Knowledge Base Statistics
#
# Total Documents: 142
#
# By Specialty:
#   - cardiology: 45
#   - endocrinology: 32
#   - emergency_medicine: 28
#   - general: 37
#
# By Document Type:
#   - clinical_guideline: 68
#   - research_paper: 35
#   - web_resource: 24
#   - hospital_protocol: 15
#
# Verification Status:
#   - verified: 95
#   - unverified: 35
#   - pending_review: 12
#
# Quality Scores:
#   - Average: 0.78
#   - Min: 0.50
#   - Max: 0.95
```

### 4. API Usage (with Authentication)

**Search via API:**
```bash
# Get JWT token first
TOKEN=$(curl -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' \
  | jq -r '.access_token')

# Search knowledge base
curl -X POST http://localhost:8000/v1/knowledge/search \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How to diagnose heart failure?",
    "specialty": "cardiology",
    "limit": 10,
    "min_score": 0.7
  }' | jq
```

**Get Citations for Query:**
```bash
curl -X POST http://localhost:8000/v1/knowledge/citations \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Latest treatment guidelines for Type 2 diabetes",
    "specialty": "endocrinology",
    "top_k": 5,
    "min_score": 0.75
  }' | jq

# Response includes:
# - citations: Array of source documents
# - markdown: Formatted citations for display
# - count: Number of citations found
```

**Submit User Feedback:**
```bash
curl -X POST http://localhost:8000/v1/knowledge/feedback \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session_abc123",
    "message_id": 456,
    "signal_type": "correction",
    "rating": 2.5,
    "user_feedback": "The recommended dose seems incorrect",
    "correction_text": "The starting dose should be 10mg, not 20mg as stated"
  }'
```

**Upload PDF via API:**
```bash
curl -X POST http://localhost:8000/v1/knowledge/ingest/pdf \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@guideline.pdf" \
  -F "title=ACC/AHA Heart Failure Guidelines 2024" \
  -F "specialty=cardiology" \
  -F "document_type=clinical_guideline"
```

### 5. Self-Learning Workflow

**Identify Knowledge Gaps:**
```bash
python scripts/manage_knowledge_base.py gaps \
  --days 30 \
  --min-occurrences 5

# Output:
# 🔍 Found 8 knowledge gaps
#
# 1. Query: What are the side effects of GLP-1 agonists?
#    Occurrences: 12
#    Avg Rating: 2.1/5.0
#    Gap Type: poor_response
#
# 2. Query: How to manage medication interactions with warfarin?
#    Occurrences: 8
#    Avg Rating: 2.5/5.0
#    Gap Type: poor_response
```

**Fill Identified Gaps:**
```bash
# Download or create documents addressing the gaps
# Then ingest them into knowledge base
python scripts/manage_knowledge_base.py ingest-web \
  https://www.drugs.com/glp-1-agonists.html \
  --title "GLP-1 Agonist Side Effects and Management" \
  --specialty endocrinology \
  --quality 0.7
```

**Validate Documents:**
```bash
# List documents needing validation (older than 180 days)
python scripts/manage_knowledge_base.py validate \
  --max-age 180 \
  --specialty cardiology \
  --list \
  --limit 20

# Mark document as verified via API
curl -X POST http://localhost:8000/v1/knowledge/validate/abc123def456 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "verification_status": "verified",
    "quality_score": 0.9,
    "notes": "Reviewed by cardiologist, current as of Jan 2026"
  }'
```

### 6. Integration with Chat

The knowledge base automatically enhances AI responses with citations:

**Example Chat Request:**
```python
# User query
"What are the warning signs of a heart attack?"

# System retrieves knowledge
citations = await get_attribution_engine().generate_citations(
    query="warning signs heart attack",
    specialty="cardiology",
    top_k=3
)

# AI response includes citations
"""
The warning signs of a heart attack include:
1. Chest pain or discomfort
2. Shortness of breath
3. Pain in arms, back, neck, jaw, or stomach
4. Cold sweats
5. Nausea or lightheadedness

**Sources:**
1. **AHA Heart Attack Warning Signs** (cardiology) - [Link](https://www.heart.org/...)
   *Relevance: 96.5%*
   > The most common symptom is chest pain or discomfort...

2. **Mayo Clinic Heart Attack Symptoms** (cardiology) - [Link](https://www.mayoclinic.org/...)
   *Relevance: 93.2%*
   > Women may experience different symptoms...
"""
```

## Common Workflows

### Weekly Maintenance Script

```bash
#!/bin/bash
# weekly_knowledge_maintenance.sh

cd /home/dgs/N3090/services/inference-node

# 1. Generate knowledge gaps report
python scripts/manage_knowledge_base.py gaps \
  --days 7 \
  --min-occurrences 3 > reports/gaps_$(date +%Y%m%d).txt

# 2. List documents needing validation
python scripts/manage_knowledge_base.py validate \
  --max-age 180 \
  --list > reports/validation_needed_$(date +%Y%m%d).txt

# 3. Show statistics
python scripts/manage_knowledge_base.py stats > reports/stats_$(date +%Y%m%d).txt

# 4. Email reports to admin
# (add email command here)

echo "Weekly knowledge base maintenance complete"
```

### Initial Knowledge Base Setup

```bash
#!/bin/bash
# setup_initial_knowledge_base.sh

# Download public medical resources
mkdir -p /tmp/medical-guidelines

# Example: Download AHA/ACC guidelines (placeholder URLs)
wget https://www.acc.org/guidelines/diabetes.pdf -O /tmp/medical-guidelines/diabetes.pdf
wget https://www.heart.org/hypertension.pdf -O /tmp/medical-guidelines/hypertension.pdf

# Ingest all downloaded guidelines
python scripts/manage_knowledge_base.py batch-ingest \
  /tmp/medical-guidelines/ \
  --specialty cardiology \
  --type clinical_guideline

echo "Initial knowledge base setup complete"
```

## Tips & Best Practices

### Document Quality

1. **Clinical Guidelines** (0.85-0.95 quality)
   - Official medical society publications
   - Government health agencies (CDC, WHO, FDA)
   
2. **Research Papers** (0.80-0.90 quality)
   - Peer-reviewed journals
   - Published studies with citations

3. **Web Resources** (0.60-0.75 quality)
   - Medical websites (Mayo Clinic, WebMD)
   - Hospital protocols
   - Educational content

4. **User Submissions** (0.50 quality)
   - Needs expert validation
   - Mark as pending_review

### Search Optimization

- **Use specific queries**: "first-line treatment for Type 2 diabetes" > "diabetes"
- **Filter by specialty**: Improves relevance and speed
- **Set appropriate min_score**: 0.7 for general search, 0.85+ for critical decisions
- **Review top 5 results**: Beyond top 5, relevance typically drops

### Feedback Collection

- **Encourage ratings**: Ask users to rate responses 1-5
- **Specific corrections**: "Dose should be 10mg" > "Wrong information"
- **Track patterns**: 3+ similar corrections = knowledge gap
- **Validate corrections**: Don't auto-apply without review

### Continuous Improvement

```
Week 1-2: Collect user feedback (target: 500+ interactions)
Week 3: Analyze gaps, ingest missing knowledge
Week 4: Fine-tune model with corrected data
Week 5: A/B test new vs old model
Week 6: Deploy winner, repeat cycle
```

## Troubleshooting

**Issue: "pypdf not installed"**
```bash
pip install pypdf
```

**Issue: "Knowledge base routes not available"**
```bash
# Check if dependencies are installed
pip list | grep -E 'pypdf|beautifulsoup4|multipart'

# Restart application
pm2 restart api-gateway
```

**Issue: "No results found"**
- Check if documents are ingested: `python scripts/manage_knowledge_base.py stats`
- Verify specialty filter matches documents
- Lower min_score threshold
- Try broader query terms

**Issue: "Slow search performance"**
- Ensure HNSW indexes exist (created by init_database.py)
- Check PostgreSQL shared_buffers configuration
- Consider adding specialty pre-filter
- Monitor pgvector query plans

## Next Steps

1. **Populate Knowledge Base**
   - Identify 10-20 key clinical guidelines for your specialties
   - Batch ingest using manage_knowledge_base.py
   - Validate and set quality scores

2. **Enable Feedback Collection**
   - Add rating buttons to chat UI
   - Integrate /v1/knowledge/feedback endpoint
   - Train staff to provide corrections

3. **Schedule Maintenance**
   - Set up weekly gap analysis
   - Create validation review workflow
   - Plan quarterly knowledge updates

4. **Monitor Quality**
   - Track average quality score (target: >0.75)
   - Monitor verification status distribution
   - Review knowledge gaps monthly

5. **Continuous Learning**
   - Fine-tune models with feedback data monthly
   - A/B test improvements before deployment
   - Archive old knowledge versions

## Resources

- Full Documentation: [docs/KNOWLEDGE_BASE.md](./KNOWLEDGE_BASE.md)
- Training Guide: [docs/TRAINING.md](./TRAINING.md)
- Database Setup: [scripts/init_database.py](../scripts/init_database.py)
- CLI Tool: [scripts/manage_knowledge_base.py](../scripts/manage_knowledge_base.py)
