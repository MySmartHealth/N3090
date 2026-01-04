# Medical Document Ingestion Guide

Complete guide for adding clinical PDFs, research papers, and medical protocols to the knowledge base.

## Overview

The knowledge base system supports:
- **PDF documents**: Clinical guidelines, research papers, protocols
- **Web pages**: Medical websites, online resources, documentation
- **Text files**: Markdown, plain text documentation

All documents are:
- Chunked for optimal retrieval (500-1000 tokens per chunk)
- Embedded using BGE-large-en-v1.5 (CPU-based, 1024 dimensions)
- Stored in PostgreSQL with pgvector (HNSW indexing)
- Tagged by specialty, document type, and verification status

## Quick Start

### 1. Command Line (CLI)

```bash
# Activate virtual environment
cd /home/dgs/N3090/services/inference-node
source .venv/bin/activate

# Ingest a single PDF
python scripts/manage_knowledge_base.py ingest-pdf \
  path/to/clinical_guideline.pdf \
  --specialty cardiology \
  --type guideline \
  --verified

# Batch ingest multiple PDFs
python scripts/manage_knowledge_base.py batch-ingest \
  /path/to/medical/pdfs/ \
  --specialty general_medicine \
  --type reference

# Ingest from URL
python scripts/manage_knowledge_base.py ingest-web \
  "https://www.cdc.gov/some-guideline.html" \
  --specialty infectious_disease \
  --type guideline
```

### 2. REST API

```bash
# Get authentication token
TOKEN=$(curl -s -X POST http://localhost:8000/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"SecureAdmin2026!"}' | \
  python3 -c 'import sys, json; print(json.load(sys.stdin)["access_token"])')

# Upload PDF via API
curl -X POST http://localhost:8000/v1/knowledge/ingest/pdf \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@clinical_guideline.pdf" \
  -F "specialty=cardiology" \
  -F "doc_type=guideline" \
  -F "verified=true"

# Ingest from URL
curl -X POST http://localhost:8000/v1/knowledge/ingest/url \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "url": "https://medical-resource.org/guideline",
    "specialty": "cardiology",
    "doc_type": "guideline"
  }'

# Search knowledge base
curl -X POST http://localhost:8000/v1/knowledge/search \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "treatment protocol for hypertension",
    "specialty": "cardiology",
    "min_score": 0.7,
    "limit": 5
  }'
```

## Document Organization

### Specialty Categories

Tag documents by medical specialty:

- `cardiology` - Heart and cardiovascular
- `neurology` - Nervous system
- `oncology` - Cancer treatment
- `pediatrics` - Child health
- `emergency_medicine` - Emergency care
- `radiology` - Medical imaging
- `psychiatry` - Mental health
- `infectious_disease` - Infections
- `endocrinology` - Hormones and metabolism
- `general_medicine` - General practice
- `ai_operations` - AI/ML documentation (technical)

### Document Types

Classify by document type:

- `guideline` - Clinical practice guidelines
- `protocol` - Treatment protocols
- `research` - Research papers, studies
- `reference` - Reference materials, textbooks
- `policy` - Healthcare policies
- `training` - Training materials

### Verification Status

Track review status:

- `unverified` - Not yet reviewed (default)
- `in_review` - Under medical review
- `verified` - Reviewed and approved
- `outdated` - Superseded by newer guidelines

## Example Workflows

### Workflow 1: Clinical Guidelines Setup

```bash
#!/bin/bash
# setup_clinical_guidelines.sh

cd /home/dgs/N3090/services/inference-node
source .venv/bin/activate

# Create directory for guidelines
mkdir -p data/clinical_guidelines

# Download sample guidelines (examples)
# Add your actual guideline PDFs to data/clinical_guidelines/

# Batch ingest all guidelines
python scripts/manage_knowledge_base.py batch-ingest \
  data/clinical_guidelines/ \
  --specialty general_medicine \
  --type guideline \
  --verified

# View statistics
python scripts/manage_knowledge_base.py stats
```

### Workflow 2: Research Papers

```python
# ingest_research_papers.py
import asyncio
from app.knowledge_base import DocumentIngestionEngine

async def ingest_papers():
    engine = DocumentIngestionEngine()
    
    # List of research papers
    papers = [
        {
            "path": "data/research/diabetes_treatment_2024.pdf",
            "specialty": "endocrinology",
            "doc_type": "research",
            "title": "Diabetes Treatment Guidelines 2024"
        },
        {
            "path": "data/research/cancer_immunotherapy.pdf",
            "specialty": "oncology",
            "doc_type": "research",
            "title": "Advances in Cancer Immunotherapy"
        },
    ]
    
    for paper in papers:
        doc_id = await engine.ingest_pdf(
            file_path=paper["path"],
            specialty=paper["specialty"],
            doc_type=paper["doc_type"],
            title=paper.get("title"),
            verified=False  # Research needs review
        )
        print(f"✅ Ingested: {paper['title']} → {doc_id}")

if __name__ == "__main__":
    asyncio.run(ingest_papers())
```

### Workflow 3: Web Resources

```bash
# Ingest CDC guidelines from web
python scripts/manage_knowledge_base.py ingest-web \
  "https://www.cdc.gov/diabetes/prevention-type-2/index.html" \
  --specialty endocrinology \
  --type guideline

# Ingest medical database articles
python scripts/manage_knowledge_base.py ingest-web \
  "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC..." \
  --specialty oncology \
  --type research
```

## Sample Medical Documents

### Where to Find Quality Medical Content

1. **Clinical Practice Guidelines**
   - National Guideline Clearinghouse (NGC)
   - NICE Guidelines (UK)
   - CDC Guidelines (US)
   - WHO Guidelines

2. **Research Databases**
   - PubMed Central (free full-text articles)
   - arXiv (preprints, some medical AI)
   - bioRxiv (biology/medicine preprints)

3. **Medical Textbooks** (public domain)
   - Anatomy atlases
   - Medical terminology guides
   - Pharmacology references

4. **Hospital Protocols**
   - Your organization's internal protocols
   - Standardized treatment pathways
   - Emergency response procedures

### Example Downloads

```bash
# Create data directories
mkdir -p data/{guidelines,research,textbooks,protocols}

# Example: Download public domain medical content
# (Add your actual medical documents here)

# For testing, use the existing docs:
python scripts/manage_knowledge_base.py ingest-text \
  docs/VLLM_SETUP.md \
  --specialty ai_operations \
  --type reference
```

## Search and Retrieval

### Basic Search

```bash
# Search by keyword
python scripts/manage_knowledge_base.py search \
  "diabetes treatment protocol"

# Search within specialty
python scripts/manage_knowledge_base.py search \
  "hypertension management" \
  --specialty cardiology

# Limit results
python scripts/manage_knowledge_base.py search \
  "cancer screening" \
  --limit 3
```

### Advanced Search with API

```python
import requests

# Authenticate
response = requests.post(
    "http://localhost:8000/v1/auth/login",
    json={"username": "admin", "password": "SecureAdmin2026!"}
)
token = response.json()["access_token"]

# Search with filters
response = requests.post(
    "http://localhost:8000/v1/knowledge/search",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "query": "treatment options for type 2 diabetes",
        "specialty": "endocrinology",
        "doc_type": "guideline",
        "min_score": 0.75,
        "limit": 5
    }
)

results = response.json()
for result in results["results"]:
    print(f"Score: {result['score']:.2f}")
    print(f"Source: {result['title']}")
    print(f"Content: {result['content'][:200]}...")
    print("---")
```

## Citation and Source Attribution

### Generate Citations

```bash
# After searching, generate citations for results
python scripts/manage_knowledge_base.py search \
  "cardiac arrest protocols" \
  --specialty emergency_medicine

# Use API to get formatted citations
curl -X POST http://localhost:8000/v1/knowledge/citations \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "cardiac arrest protocols",
    "format": "markdown"
  }'
```

### Citation Formats

**Markdown:**
```
Based on medical literature [1][2]:

[1] "Emergency Cardiac Arrest Protocol" - Type: guideline, Specialty: emergency_medicine
[2] "Advanced Cardiovascular Life Support" - Type: protocol, Specialty: cardiology
```

**JSON:**
```json
{
  "citations": [
    {
      "document_id": "abc123",
      "title": "Emergency Cardiac Arrest Protocol",
      "specialty": "emergency_medicine",
      "doc_type": "guideline",
      "relevance_score": 0.92
    }
  ]
}
```

## Quality and Maintenance

### Document Validation

```bash
# List unverified documents
python scripts/manage_knowledge_base.py validate

# Mark document as verified (admin only)
curl -X POST http://localhost:8000/v1/knowledge/validate/abc123 \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"status": "verified"}'
```

### Knowledge Gaps Analysis

```bash
# Identify knowledge gaps from user feedback
python scripts/manage_knowledge_base.py gaps

# API version
curl -X POST http://localhost:8000/v1/knowledge/gaps \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"min_occurrences": 3, "limit": 10}'
```

### Weekly Maintenance

```bash
#!/bin/bash
# weekly_knowledge_maintenance.sh

cd /home/dgs/N3090/services/inference-node
source .venv/bin/activate

echo "📊 Knowledge Base Statistics:"
python scripts/manage_knowledge_base.py stats

echo "
🔍 Documents Needing Verification:"
python scripts/manage_knowledge_base.py validate

echo "
🕳️ Knowledge Gaps (from user feedback):"
python scripts/manage_knowledge_base.py gaps --min-occurrences 2

echo "
✅ Maintenance check complete"
```

## Performance Tips

1. **Batch Ingestion**: Use `batch-ingest` for multiple files
2. **Specialty Tagging**: Always tag documents by specialty for better filtering
3. **Quality Scores**: Higher quality documents get better scores (0-1.0)
4. **Chunk Size**: Default 800 tokens works well for medical content
5. **Overlap**: 100-token overlap ensures context continuity
6. **Embeddings**: CPU-based BGE-large provides good quality without GPU memory pressure

## Troubleshooting

### Issue: PDF Extraction Fails

```bash
# Check if file is valid PDF
file medical_doc.pdf

# Try with different extraction method
python -c "
import pypdf
reader = pypdf.PdfReader('medical_doc.pdf')
print(f'Pages: {len(reader.pages)}')
print(reader.pages[0].extract_text()[:500])
"
```

### Issue: Out of Memory

```bash
# Reduce batch size for large PDFs
# Edit app/knowledge_base.py, reduce chunk_size or batch_size

# Or ingest one file at a time
for pdf in data/guidelines/*.pdf; do
    python scripts/manage_knowledge_base.py ingest-pdf "$pdf" \
      --specialty general_medicine \
      --type guideline
    sleep 1  # Pause between ingestions
done
```

### Issue: Poor Search Results

```bash
# Check document count
python scripts/manage_knowledge_base.py stats

# Verify embeddings are working (should not say "stub embeddings")
pm2 logs api-gateway | grep -i embedding

# Lower min_score threshold
python scripts/manage_knowledge_base.py search "query" --min-score 0.6
```

## Next Steps

1. **Add Your Medical Documents**: Place PDFs in `data/` directories
2. **Batch Ingest**: Use the batch-ingest command for efficiency
3. **Tag Properly**: Use correct specialty and document type tags
4. **Validate Content**: Review and verify important clinical documents
5. **Monitor Quality**: Check knowledge gaps and user feedback regularly
6. **Update Regularly**: Refresh outdated guidelines with new versions

## Security & Privacy

- **PHI Protection**: Do not ingest documents containing patient identifiable information
- **Access Control**: Only admins can ingest documents (JWT auth required)
- **Audit Logging**: All ingestion events are logged
- **Version Control**: Keep original PDFs in version-controlled storage
- **Review Process**: Implement medical review before marking documents as "verified"

## Support

For issues or questions:
- Check logs: `pm2 logs api-gateway`
- View database: `psql medical_ai -c "SELECT COUNT(*), specialty FROM medical_documents GROUP BY specialty;"`
- Test API: Use the example curl commands above
- Documentation: See `docs/KNOWLEDGE_BASE.md` for architecture details
