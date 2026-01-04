"""
Web Scraping Routes
Endpoints for scraping websites and ingesting to knowledge base.
"""
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from loguru import logger

from .auth import get_current_user, User

router = APIRouter(prefix="/v1/knowledge", tags=["Web Scraping"])

# Import web scraper
try:
    from .web_scraper import web_scraper, medical_scraper
    WEB_SCRAPER_AVAILABLE = True
except ImportError:
    WEB_SCRAPER_AVAILABLE = False
    logger.warning("Web scraper not available")


class WebScrapeRequest(BaseModel):
    """Request to scrape a website."""
    url: str
    specialty: str = "general"
    doc_type: str = "reference"
    follow_links: bool = False
    max_depth: int = 2
    ingest_to_kb: bool = True


class WebScrapeResponse(BaseModel):
    """Web scraping response."""
    documents_scraped: int
    documents_ingested: int
    documents: List[Dict[str, Any]]
    errors: List[str] = []


class MultiURLScrapeRequest(BaseModel):
    """Request to scrape multiple URLs."""
    urls: List[str]
    specialty: str = "general"
    doc_type: str = "reference"
    follow_links: bool = False
    ingest_to_kb: bool = True


@router.post("/scrape", response_model=WebScrapeResponse)
async def scrape_website(
    request: WebScrapeRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Scrape a website and optionally ingest to knowledge base.
    
    Features:
    - Scrapes HTML pages and PDFs
    - Follows links recursively (configurable depth)
    - Automatically ingests to RAG knowledge base
    - Medical content filtering
    
    Example:
        curl -X POST http://localhost:8000/v1/knowledge/scrape \\
            -H "Authorization: Bearer YOUR_TOKEN" \\
            -H "Content-Type: application/json" \\
            -d '{
                "url": "https://www.cdc.gov/diabetes/",
                "specialty": "endocrinology",
                "doc_type": "guideline",
                "follow_links": true,
                "max_depth": 2,
                "ingest_to_kb": true
            }'
    """
    if not WEB_SCRAPER_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Web scraper not available. Install: pip install beautifulsoup4 PyPDF2"
        )
    
    try:
        # Configure scraper
        from .web_scraper import WebScraper
        scraper = WebScraper(max_depth=request.max_depth, max_pages=100)
        
        # Scrape website
        logger.info(f"Scraping {request.url} (depth={request.max_depth}, follow_links={request.follow_links})")
        documents = await scraper.scrape_url(
            url=request.url,
            specialty=request.specialty,
            doc_type=request.doc_type,
            follow_links=request.follow_links
        )
        
        ingested_count = 0
        errors = []
        
        # Ingest to knowledge base if requested
        if request.ingest_to_kb and documents:
            try:
                from .rag_engine import rag_engine
                for doc in documents:
                    try:
                        await rag_engine.ingest_document(
                            content=doc["content"],
                            title=doc["title"],
                            specialty=doc["specialty"],
                            doc_type=doc["doc_type"],
                            source_url=doc.get("source_url"),
                            metadata=doc.get("metadata", {})
                        )
                        ingested_count += 1
                    except Exception as e:
                        errors.append(f"Failed to ingest {doc['title']}: {str(e)}")
                        logger.error(f"Ingestion failed: {e}")
                
                logger.info(f"Ingested {ingested_count}/{len(documents)} documents to knowledge base")
            except Exception as e:
                errors.append(f"Knowledge base ingestion error: {str(e)}")
                logger.error(f"KB ingestion failed: {e}")
        
        return WebScrapeResponse(
            documents_scraped=len(documents),
            documents_ingested=ingested_count,
            documents=documents[:10],  # Return first 10 for preview
            errors=errors
        )
    
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Scraping failed: {str(e)}"
        )


@router.post("/scrape-multi", response_model=WebScrapeResponse)
async def scrape_multiple_websites(
    request: MultiURLScrapeRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Scrape multiple websites in parallel.
    
    Example:
        curl -X POST http://localhost:8000/v1/knowledge/scrape-multi \\
            -H "Authorization: Bearer YOUR_TOKEN" \\
            -H "Content-Type: application/json" \\
            -d '{
                "urls": [
                    "https://www.cdc.gov/diabetes/",
                    "https://www.nih.gov/health-information/diabetes"
                ],
                "specialty": "endocrinology",
                "ingest_to_kb": true
            }'
    """
    if not WEB_SCRAPER_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Web scraper not available"
        )
    
    try:
        from .web_scraper import WebScraper
        scraper = WebScraper(max_depth=2, max_pages=100)
        
        # Scrape all URLs in parallel
        logger.info(f"Scraping {len(request.urls)} URLs in parallel")
        documents = await scraper.scrape_multiple_urls(
            urls=request.urls,
            specialty=request.specialty,
            doc_type=request.doc_type,
            follow_links=request.follow_links
        )
        
        ingested_count = 0
        errors = []
        
        # Ingest to knowledge base
        if request.ingest_to_kb and documents:
            try:
                from .rag_engine import rag_engine
                for doc in documents:
                    try:
                        await rag_engine.ingest_document(
                            content=doc["content"],
                            title=doc["title"],
                            specialty=doc["specialty"],
                            doc_type=doc["doc_type"],
                            source_url=doc.get("source_url"),
                            metadata=doc.get("metadata", {})
                        )
                        ingested_count += 1
                    except Exception as e:
                        errors.append(f"Failed to ingest {doc['title']}: {str(e)}")
                
                logger.info(f"Ingested {ingested_count}/{len(documents)} documents")
            except Exception as e:
                errors.append(f"Ingestion error: {str(e)}")
        
        return WebScrapeResponse(
            documents_scraped=len(documents),
            documents_ingested=ingested_count,
            documents=documents[:10],
            errors=errors
        )
    
    except Exception as e:
        logger.error(f"Multi-scrape failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Scraping failed: {str(e)}"
        )


class MedicalGuidelineScrapeRequest(BaseModel):
    """Request to scrape medical guidelines."""
    disease: str
    max_results: int = 10
    ingest_to_kb: bool = True


@router.post("/scrape-medical-guidelines")
async def scrape_medical_guidelines(
    request: MedicalGuidelineScrapeRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Scrape medical guidelines for a specific disease from trusted sources.
    
    Trusted sources include:
    - NIH (nih.gov)
    - CDC (cdc.gov)
    - WHO (who.int)
    - PubMed
    - Mayo Clinic
    - UpToDate
    
    Example:
        curl -X POST http://localhost:8000/v1/knowledge/scrape-medical-guidelines \\
            -H "Authorization: Bearer YOUR_TOKEN" \\
            -H "Content-Type: application/json" \\
            -d '{
                "disease": "diabetes",
                "max_results": 10,
                "ingest_to_kb": true
            }'
    """
    if not WEB_SCRAPER_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Web scraper not available"
        )
    
    try:
        from .web_scraper import medical_scraper
        
        logger.info(f"Scraping medical guidelines for: {request.disease}")
        documents = await medical_scraper.scrape_medical_guidelines(
            disease=request.disease,
            max_results=request.max_results
        )
        
        ingested_count = 0
        errors = []
        
        if request.ingest_to_kb and documents:
            try:
                from .rag_engine import rag_engine
                for doc in documents:
                    try:
                        await rag_engine.ingest_document(
                            content=doc["content"],
                            title=doc["title"],
                            specialty="general_medicine",
                            doc_type="guideline",
                            source_url=doc.get("source_url"),
                            metadata=doc.get("metadata", {})
                        )
                        ingested_count += 1
                    except Exception as e:
                        errors.append(f"Failed to ingest {doc['title']}: {str(e)}")
                
                logger.info(f"Ingested {ingested_count} medical guidelines")
            except Exception as e:
                errors.append(f"Ingestion error: {str(e)}")
        
        return WebScrapeResponse(
            documents_scraped=len(documents),
            documents_ingested=ingested_count,
            documents=documents,
            errors=errors
        )
    
    except Exception as e:
        logger.error(f"Medical guideline scraping failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to scrape guidelines: {str(e)}"
        )
