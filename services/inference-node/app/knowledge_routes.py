"""
Knowledge Base & Self-Learning API Endpoints

Routes:
- POST /v1/knowledge/ingest - Ingest new document
- GET /v1/knowledge/search - Search knowledge base
- POST /v1/knowledge/feedback - Submit user feedback
- GET /v1/knowledge/citations - Get citations for query
- GET /v1/knowledge/gaps - Identify knowledge gaps
- GET /v1/knowledge/stats - Knowledge base statistics
- POST /v1/knowledge/validate - Validate document
"""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from pydantic import BaseModel, Field
from datetime import datetime
from loguru import logger

from app.knowledge_base import (
    get_ingestion_engine,
    get_attribution_engine,
    get_learning_engine,
    Citation
)
from app.database import get_db, AsyncSession
from app.auth import get_current_user, User


router = APIRouter(prefix="/v1/knowledge", tags=["knowledge"])


# Request/Response Models
class IngestURLRequest(BaseModel):
    url: str
    title: str
    specialty: str
    document_type: str = "web_resource"
    quality_score: float = Field(default=0.6, ge=0.0, le=1.0)


class IngestTextRequest(BaseModel):
    content: str
    title: str
    specialty: str
    document_type: str = "user_submission"
    source_url: Optional[str] = None


class SearchRequest(BaseModel):
    query: str
    specialty: Optional[str] = None
    document_type: Optional[str] = None
    limit: int = Field(default=10, le=50)
    min_score: float = Field(default=0.7, ge=0.0, le=1.0)


class FeedbackRequest(BaseModel):
    session_id: str
    message_id: int
    signal_type: str  # positive, negative, correction, validation
    rating: Optional[float] = Field(None, ge=1.0, le=5.0)
    user_feedback: Optional[str] = None
    correction_text: Optional[str] = None


class CitationRequest(BaseModel):
    query: str
    specialty: Optional[str] = None
    top_k: int = Field(default=5, le=20)
    min_score: float = Field(default=0.7, ge=0.0, le=1.0)


class KnowledgeGapsRequest(BaseModel):
    days_back: int = Field(default=7, ge=1, le=90)
    min_occurrences: int = Field(default=3, ge=1)


class ValidateDocumentRequest(BaseModel):
    document_id: str
    verification_status: str  # verified, outdated, incorrect
    quality_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    notes: Optional[str] = None


# API Endpoints

@router.post("/ingest/url")
async def ingest_from_url(
    request: IngestURLRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Ingest document from URL."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        engine = get_ingestion_engine()
        doc_id = await engine.ingest_web_page(
            url=request.url,
            title=request.title,
            specialty=request.specialty,
            document_type=request.document_type,
            quality_score=request.quality_score
        )
        
        if doc_id:
            return {
                "success": True,
                "document_id": doc_id,
                "message": "Document ingested successfully"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to ingest document")
    
    except Exception as e:
        logger.error(f"Ingestion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest/text")
async def ingest_from_text(
    request: IngestTextRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Ingest document from text content."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        from app.knowledge_base import DocumentIngestionEngine, EmbeddingEngine
        from app.database import MedicalDocument, AsyncSessionLocal
        import hashlib
        
        # Generate embedding
        embedding_engine = EmbeddingEngine()
        embedding = embedding_engine.encode([request.content])[0]
        
        # Create document ID
        doc_id = hashlib.sha256(
            f"{request.title}_{request.specialty}".encode()
        ).hexdigest()[:16]
        
        # Store in database
        async with AsyncSessionLocal() as session:
            doc = MedicalDocument(
                document_id=doc_id,
                title=request.title,
                content=request.content,
                document_type=request.document_type,
                specialty=request.specialty,
                embedding=embedding,
                source_url=request.source_url,
                extra_data={
                    "submitted_by": current_user.username,
                    "submission_date": datetime.utcnow().isoformat()
                },
                quality_score=0.5,
                verification_status="pending_review",
                created_at=datetime.utcnow()
            )
            
            session.add(doc)
            await session.commit()
        
        return {
            "success": True,
            "document_id": doc_id,
            "message": "Document submitted for review"
        }
    
    except Exception as e:
        logger.error(f"Text ingestion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest/pdf")
async def ingest_from_pdf(
    file: UploadFile = File(...),
    title: str = None,
    specialty: str = None,
    document_type: str = "clinical_guideline",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Ingest PDF file."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files supported")
    
    try:
        import tempfile
        import os
        
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = tmp_file.name
        
        try:
            # Ingest PDF
            engine = get_ingestion_engine()
            doc_ids = await engine.ingest_pdf(
                pdf_path=tmp_path,
                title=title or file.filename,
                specialty=specialty or "general",
                document_type=document_type,
                extra_data={"uploaded_by": current_user.username}
            )
            
            return {
                "success": True,
                "document_ids": doc_ids,
                "chunks": len(doc_ids),
                "message": f"PDF ingested as {len(doc_ids)} chunks"
            }
        
        finally:
            # Clean up temp file
            os.unlink(tmp_path)
    
    except Exception as e:
        logger.error(f"PDF ingestion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def search_knowledge_base(
    request: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Search knowledge base."""
    try:
        from app.database import search_medical_documents
        
        results = await search_medical_documents(
            query=request.query,
            specialty=request.specialty,
            document_type=request.document_type,
            limit=request.limit
        )
        
        # Filter by minimum score
        filtered_results = [
            r for r in results 
            if r['similarity'] >= request.min_score
        ]
        
        return {
            "query": request.query,
            "results": filtered_results,
            "count": len(filtered_results),
            "total_searched": len(results)
        }
    
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/citations")
async def get_citations(
    request: CitationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Generate citations for a query."""
    try:
        engine = get_attribution_engine()
        citations = await engine.generate_citations(
            query=request.query,
            specialty=request.specialty,
            top_k=request.top_k,
            min_score=request.min_score
        )
        
        # Format citations
        formatted_md = engine.format_citations_markdown(citations)
        formatted_json = engine.format_citations_json(citations)
        
        return {
            "query": request.query,
            "citations": formatted_json,
            "markdown": formatted_md,
            "count": len(citations)
        }
    
    except Exception as e:
        logger.error(f"Citation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/feedback")
async def submit_feedback(
    request: FeedbackRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Submit user feedback for self-learning."""
    try:
        engine = get_learning_engine()
        
        await engine.record_feedback(
            session_id=request.session_id,
            message_id=request.message_id,
            signal_type=request.signal_type,
            user_feedback=request.user_feedback,
            correction_text=request.correction_text,
            rating=request.rating
        )
        
        return {
            "success": True,
            "message": "Feedback recorded successfully"
        }
    
    except Exception as e:
        logger.error(f"Feedback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/gaps")
async def identify_knowledge_gaps(
    request: KnowledgeGapsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Identify knowledge gaps from user feedback."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        engine = get_learning_engine()
        gaps = await engine.identify_knowledge_gaps(
            days_back=request.days_back,
            min_occurrences=request.min_occurrences
        )
        
        return {
            "gaps": gaps,
            "count": len(gaps),
            "analysis_period_days": request.days_back
        }
    
    except Exception as e:
        logger.error(f"Knowledge gaps error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_knowledge_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get knowledge base statistics."""
    try:
        from app.database import MedicalDocument
        from sqlalchemy import select, func
        
        async with db as session:
            # Total documents
            stmt = select(func.count(MedicalDocument.id))
            result = await session.execute(stmt)
            total_docs = result.scalar()
            
            # By specialty
            stmt = select(
                MedicalDocument.specialty,
                func.count(MedicalDocument.id)
            ).group_by(
                MedicalDocument.specialty
            ).order_by(
                func.count(MedicalDocument.id).desc()
            )
            result = await session.execute(stmt)
            by_specialty = {row[0]: row[1] for row in result}
            
            # By type
            stmt = select(
                MedicalDocument.document_type,
                func.count(MedicalDocument.id)
            ).group_by(
                MedicalDocument.document_type
            ).order_by(
                func.count(MedicalDocument.id).desc()
            )
            result = await session.execute(stmt)
            by_type = {row[0]: row[1] for row in result}
            
            # By verification status
            stmt = select(
                MedicalDocument.verification_status,
                func.count(MedicalDocument.id)
            ).group_by(
                MedicalDocument.verification_status
            )
            result = await session.execute(stmt)
            by_status = {row[0]: row[1] for row in result}
            
            # Quality stats
            stmt = select(
                func.avg(MedicalDocument.quality_score),
                func.min(MedicalDocument.quality_score),
                func.max(MedicalDocument.quality_score)
            )
            result = await session.execute(stmt)
            quality_stats = result.one()
        
        return {
            "total_documents": total_docs,
            "by_specialty": by_specialty,
            "by_type": by_type,
            "by_verification_status": by_status,
            "quality_scores": {
                "average": float(quality_stats[0]) if quality_stats[0] else 0.0,
                "min": float(quality_stats[1]) if quality_stats[1] else 0.0,
                "max": float(quality_stats[2]) if quality_stats[2] else 0.0
            }
        }
    
    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate/{document_id}")
async def validate_document(
    document_id: str,
    request: ValidateDocumentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Validate or update document quality."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        from app.database import MedicalDocument
        from sqlalchemy import select, update
        
        async with db as session:
            # Update document
            stmt = (
                update(MedicalDocument)
                .where(MedicalDocument.document_id == document_id)
                .values(
                    verification_status=request.verification_status,
                    quality_score=request.quality_score or MedicalDocument.quality_score,
                    last_verified=datetime.utcnow(),
                    verified_by=current_user.username,
                    extra_data={
                        "validation_notes": request.notes,
                        "validated_at": datetime.utcnow().isoformat()
                    }
                )
            )
            result = await session.execute(stmt)
            await session.commit()
            
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Document not found")
        
        return {
            "success": True,
            "message": "Document validated successfully",
            "document_id": document_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
