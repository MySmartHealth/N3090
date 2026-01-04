"""
Knowledge Base Management & Self-Learning System

Features:
1. Document Ingestion - Load PDFs, papers, guidelines, web sources
2. Source Attribution - Track citations and evidence for responses
3. Self-Learning Loop - Continuous improvement from user feedback
4. Knowledge Validation - Verify accuracy, update outdated info
5. Conflict Resolution - Handle contradictory information
6. Quality Scoring - Rate source reliability and evidence strength
"""
import os
import hashlib
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from pathlib import Path
from loguru import logger

# Document parsing libraries
try:
    import pypdf
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    logger.warning("pypdf not installed, PDF parsing disabled")

try:
    from bs4 import BeautifulSoup
    import requests
    WEB_SCRAPING_AVAILABLE = True
except ImportError:
    WEB_SCRAPING_AVAILABLE = False
    logger.warning("beautifulsoup4/requests not installed, web scraping disabled")

try:
    from app.database import (
        MedicalDocument, AsyncSessionLocal, 
        search_medical_documents, User
    )
    from app.rag_engine import EmbeddingEngine
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    logger.warning("Database not available, knowledge base disabled")

from sqlalchemy import select, func, and_, or_, update


@dataclass
class DocumentChunk:
    """A chunk of a larger document."""
    chunk_id: str
    content: str
    source_doc_id: str
    page_number: Optional[int] = None
    section: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class Citation:
    """Source citation for a response."""
    document_id: str
    title: str
    source_url: Optional[str]
    specialty: str
    relevance_score: float
    excerpt: str
    page_number: Optional[int] = None
    published_date: Optional[datetime] = None


@dataclass
class LearningSignal:
    """Signal for self-learning improvement."""
    session_id: str
    message_id: int
    signal_type: str  # "positive", "negative", "correction", "validation"
    user_feedback: Optional[str] = None
    correction_text: Optional[str] = None
    rating: Optional[float] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class DocumentIngestionEngine:
    """
    Ingests documents from multiple sources into the knowledge base.
    Supports: PDFs, web pages, text files, medical databases.
    """
    
    def __init__(self, embedding_engine: Optional[EmbeddingEngine] = None):
        self.embedding_engine = embedding_engine or EmbeddingEngine()
        self.chunk_size = int(os.getenv("CHUNK_SIZE", "512"))
        self.chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "50"))
    
    async def ingest_pdf(
        self,
        pdf_path: str,
        title: str,
        specialty: str,
        document_type: str = "clinical_guideline",
        source_url: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> List[str]:
        """
        Ingest PDF document into knowledge base.
        
        Args:
            pdf_path: Path to PDF file
            title: Document title
            specialty: Medical specialty (cardiology, oncology, etc.)
            document_type: Type of document
            source_url: Original URL if downloaded
            metadata: Additional metadata
            
        Returns:
            List of document IDs created
        """
        if not PDF_AVAILABLE:
            logger.error("pypdf not installed, cannot parse PDFs")
            return []
        
        logger.info(f"Ingesting PDF: {pdf_path}")
        
        # Extract text from PDF
        chunks = await self._extract_pdf_chunks(pdf_path)
        
        # Create document entries
        doc_ids = []
        async with AsyncSessionLocal() as session:
            for i, chunk in enumerate(chunks):
                # Generate embedding
                embedding = self.embedding_engine.encode([chunk.content])[0]
                
                # Create unique document ID
                doc_id = hashlib.sha256(
                    f"{title}_{specialty}_{i}".encode()
                ).hexdigest()[:16]
                
                # Prepare metadata
                doc_metadata = metadata or {}
                doc_metadata.update({
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "page_number": chunk.page_number,
                    "section": chunk.section,
                    "ingestion_date": datetime.utcnow().isoformat()
                })
                
                # Create database entry
                doc = MedicalDocument(
                    document_id=doc_id,
                    title=f"{title} (Part {i+1}/{len(chunks)})",
                    content=chunk.content,
                    document_type=document_type,
                    specialty=specialty,
                    embedding=embedding,
                    source_url=source_url,
                    extra_data=doc_metadata,
                    quality_score=0.8,  # Default for clinical guidelines
                    verification_status="unverified",
                    created_at=datetime.utcnow(),
                    last_verified=None
                )
                
                session.add(doc)
                doc_ids.append(doc_id)
            
            await session.commit()
        
        logger.info(f"Ingested {len(doc_ids)} chunks from {pdf_path}")
        return doc_ids
    
    async def _extract_pdf_chunks(self, pdf_path: str) -> List[DocumentChunk]:
        """Extract and chunk text from PDF."""
        chunks = []
        
        with open(pdf_path, 'rb') as f:
            reader = pypdf.PdfReader(f)
            
            for page_num, page in enumerate(reader.pages):
                text = page.extract_text()
                
                # Split into chunks with overlap
                page_chunks = self._split_text(text, page_num + 1)
                chunks.extend(page_chunks)
        
        return chunks
    
    def _split_text(self, text: str, page_number: int) -> List[DocumentChunk]:
        """Split text into overlapping chunks."""
        chunks = []
        words = text.split()
        
        for i in range(0, len(words), self.chunk_size - self.chunk_overlap):
            chunk_words = words[i:i + self.chunk_size]
            chunk_text = " ".join(chunk_words)
            
            chunk_id = hashlib.sha256(chunk_text.encode()).hexdigest()[:16]
            
            chunks.append(DocumentChunk(
                chunk_id=chunk_id,
                content=chunk_text,
                source_doc_id="",
                page_number=page_number
            ))
        
        return chunks
    
    async def ingest_web_page(
        self,
        url: str,
        title: str,
        specialty: str,
        document_type: str = "web_resource",
        quality_score: float = 0.6
    ) -> Optional[str]:
        """
        Ingest web page content.
        
        Args:
            url: Web page URL
            title: Document title
            specialty: Medical specialty
            document_type: Type of document
            quality_score: Trust score (0.6 for web, 0.9 for journals)
            
        Returns:
            Document ID if successful
        """
        if not WEB_SCRAPING_AVAILABLE:
            logger.error("beautifulsoup4/requests not installed")
            return None
        
        logger.info(f"Ingesting web page: {url}")
        
        try:
            # Fetch content
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove script and style tags
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Extract text
            text = soup.get_text(separator=" ", strip=True)
            
            # Generate embedding
            embedding = self.embedding_engine.encode([text])[0]
            
            # Create document ID
            doc_id = hashlib.sha256(url.encode()).hexdigest()[:16]
            
            # Store in database
            async with AsyncSessionLocal() as session:
                doc = MedicalDocument(
                    document_id=doc_id,
                    title=title,
                    content=text,
                    document_type=document_type,
                    specialty=specialty,
                    embedding=embedding,
                    source_url=url,
                    extra_data={
                        "ingestion_date": datetime.utcnow().isoformat(),
                        "content_length": len(text)
                    },
                    quality_score=quality_score,
                    verification_status="unverified",
                    created_at=datetime.utcnow()
                )
                
                session.add(doc)
                await session.commit()
            
            logger.info(f"Ingested web page: {title}")
            return doc_id
        
        except Exception as e:
            logger.error(f"Failed to ingest {url}: {e}")
            return None
    
    async def ingest_text_file(
        self,
        file_path: str,
        title: str,
        specialty: str,
        document_type: str = "reference",
        source_url: Optional[str] = None
    ) -> Optional[str]:
        """Ingest plain text file."""
        logger.info(f"Ingesting text file: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
        
        # Generate embedding
        embedding = self.embedding_engine.encode([text])[0]
        
        # Create document ID
        doc_id = hashlib.sha256(f"{file_path}_{title}".encode()).hexdigest()[:16]
        
        # Store in database
        async with AsyncSessionLocal() as session:
            doc = MedicalDocument(
                document_id=doc_id,
                title=title,
                content=text,
                document_type=document_type,
                specialty=specialty,
                embedding=embedding,
                source_url=source_url,
                extra_data={
                    "file_path": file_path,
                    "ingestion_date": datetime.utcnow().isoformat()
                },
                quality_score=0.7,
                verification_status="unverified",
                created_at=datetime.utcnow()
            )
            
            session.add(doc)
            await session.commit()
        
        logger.info(f"Ingested text file: {title}")
        return doc_id


class SourceAttributionEngine:
    """
    Attributes sources and generates citations for AI responses.
    Ensures transparency and evidence-based answers.
    """
    
    def __init__(self, embedding_engine: Optional[EmbeddingEngine] = None):
        self.embedding_engine = embedding_engine or EmbeddingEngine()
    
    async def generate_citations(
        self,
        query: str,
        specialty: Optional[str] = None,
        top_k: int = 5,
        min_score: float = 0.7
    ) -> List[Citation]:
        """
        Generate citations for a query from knowledge base.
        
        Args:
            query: User query or AI response to cite
            specialty: Filter by medical specialty
            top_k: Number of citations to return
            min_score: Minimum relevance score
            
        Returns:
            List of citations with source attribution
        """
        # Search knowledge base
        results = await search_medical_documents(
            query=query,
            specialty=specialty,
            limit=top_k
        )
        
        citations = []
        for result in results:
            if result['similarity'] >= min_score:
                citations.append(Citation(
                    document_id=result['document_id'],
                    title=result['title'],
                    source_url=result.get('source_url'),
                    specialty=result['specialty'],
                    relevance_score=result['similarity'],
                    excerpt=result['content'][:200] + "...",
                    page_number=result.get('metadata', {}).get('page_number'),
                    published_date=result.get('created_at')
                ))
        
        logger.info(f"Generated {len(citations)} citations for query")
        return citations
    
    def format_citations_markdown(self, citations: List[Citation]) -> str:
        """Format citations as markdown for response."""
        if not citations:
            return ""
        
        md = "\n\n**Sources:**\n"
        for i, cite in enumerate(citations, 1):
            md += f"{i}. **{cite.title}** ({cite.specialty})"
            if cite.source_url:
                md += f" - [Link]({cite.source_url})"
            if cite.page_number:
                md += f" (Page {cite.page_number})"
            md += f"\n   *Relevance: {cite.relevance_score:.2%}*\n"
            md += f"   > {cite.excerpt}\n\n"
        
        return md
    
    def format_citations_json(self, citations: List[Citation]) -> List[Dict]:
        """Format citations as JSON for API responses."""
        return [
            {
                "document_id": cite.document_id,
                "title": cite.title,
                "source_url": cite.source_url,
                "specialty": cite.specialty,
                "relevance_score": cite.relevance_score,
                "excerpt": cite.excerpt,
                "page_number": cite.page_number,
                "published_date": cite.published_date.isoformat() if cite.published_date else None
            }
            for cite in citations
        ]


class SelfLearningEngine:
    """
    Implements continuous self-learning from user interactions.
    
    Learning Loop:
    1. Collect feedback signals (ratings, corrections, validations)
    2. Identify knowledge gaps and errors
    3. Update knowledge base with validated corrections
    4. Trigger model fine-tuning for repeated issues
    5. A/B test improvements before deployment
    """
    
    def __init__(self):
        self.learning_signals: List[LearningSignal] = []
    
    async def record_feedback(
        self,
        session_id: str,
        message_id: int,
        signal_type: str,
        user_feedback: Optional[str] = None,
        correction_text: Optional[str] = None,
        rating: Optional[float] = None
    ) -> None:
        """
        Record user feedback for self-learning.
        
        Args:
            session_id: Chat session ID
            message_id: Message ID
            signal_type: Type of feedback (positive, negative, correction, validation)
            user_feedback: Free-text feedback
            correction_text: Corrected response from user
            rating: Numerical rating (1-5)
        """
        signal = LearningSignal(
            session_id=session_id,
            message_id=message_id,
            signal_type=signal_type,
            user_feedback=user_feedback,
            correction_text=correction_text,
            rating=rating
        )
        
        self.learning_signals.append(signal)
        
        # Store in database for training data collection
        async with AsyncSessionLocal() as session:
            from app.database import ChatMessage
            
            # Update message with feedback
            stmt = (
                update(ChatMessage)
                .where(ChatMessage.id == message_id)
                .values(
                    user_rating=rating,
                    user_feedback=user_feedback,
                    extra_data={
                        "signal_type": signal_type,
                        "correction": correction_text,
                        "feedback_timestamp": datetime.utcnow().isoformat()
                    }
                )
            )
            await session.execute(stmt)
            await session.commit()
        
        logger.info(f"Recorded {signal_type} feedback for message {message_id}")
        
        # Trigger knowledge update for corrections
        if signal_type == "correction" and correction_text:
            await self._handle_correction(session_id, message_id, correction_text)
    
    async def _handle_correction(
        self,
        session_id: str,
        message_id: int,
        correction_text: str
    ) -> None:
        """Handle user corrections by updating knowledge base."""
        logger.info(f"Processing correction for message {message_id}")
        
        # TODO: Implement correction handling
        # 1. Extract corrected facts
        # 2. Find conflicting documents in knowledge base
        # 3. Create new document with correction
        # 4. Mark old documents as "needs_review"
        # 5. Trigger expert validation workflow
        
        async with AsyncSessionLocal() as session:
            from app.database import MedicalDocument
            
            # Create correction document
            embedding_engine = EmbeddingEngine()
            embedding = embedding_engine.encode([correction_text])[0]
            
            doc_id = hashlib.sha256(
                f"correction_{message_id}_{datetime.utcnow()}".encode()
            ).hexdigest()[:16]
            
            correction_doc = MedicalDocument(
                document_id=doc_id,
                title=f"User Correction - {datetime.utcnow().strftime('%Y-%m-%d')}",
                content=correction_text,
                document_type="user_correction",
                specialty="general",
                embedding=embedding,
                source_url=None,
                extra_data={
                    "session_id": session_id,
                    "message_id": message_id,
                    "correction_date": datetime.utcnow().isoformat()
                },
                quality_score=0.5,  # Needs validation
                verification_status="pending_review",
                created_at=datetime.utcnow()
            )
            
            session.add(correction_doc)
            await session.commit()
        
        logger.info(f"Created correction document: {doc_id}")
    
    async def identify_knowledge_gaps(
        self,
        days_back: int = 7,
        min_occurrences: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Identify knowledge gaps from user feedback.
        
        Args:
            days_back: Days to look back for feedback
            min_occurrences: Minimum occurrences to flag as gap
            
        Returns:
            List of knowledge gaps to address
        """
        since_date = datetime.utcnow() - timedelta(days=days_back)
        
        async with AsyncSessionLocal() as session:
            from app.database import ChatMessage
            
            # Find frequently asked questions with negative feedback
            stmt = select(
                ChatMessage.content,
                func.count(ChatMessage.id).label('count'),
                func.avg(ChatMessage.user_rating).label('avg_rating')
            ).where(
                and_(
                    ChatMessage.created_at >= since_date,
                    ChatMessage.role == "user",
                    ChatMessage.user_rating.isnot(None)
                )
            ).group_by(
                ChatMessage.content
            ).having(
                and_(
                    func.count(ChatMessage.id) >= min_occurrences,
                    func.avg(ChatMessage.user_rating) < 3.0
                )
            ).order_by(
                func.count(ChatMessage.id).desc()
            )
            
            result = await session.execute(stmt)
            gaps = []
            
            for row in result:
                gaps.append({
                    "query": row.content,
                    "occurrences": row.count,
                    "avg_rating": float(row.avg_rating),
                    "gap_type": "poor_response"
                })
        
        logger.info(f"Identified {len(gaps)} knowledge gaps")
        return gaps
    
    async def validate_knowledge(
        self,
        specialty: Optional[str] = None,
        max_age_days: int = 180
    ) -> List[str]:
        """
        Identify outdated knowledge needing validation.
        
        Args:
            specialty: Filter by specialty
            max_age_days: Maximum age before requiring revalidation
            
        Returns:
            List of document IDs needing validation
        """
        cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)
        
        async with AsyncSessionLocal() as session:
            from app.database import MedicalDocument
            
            # Find documents that haven't been verified recently
            stmt = select(MedicalDocument.document_id).where(
                or_(
                    MedicalDocument.last_verified.is_(None),
                    MedicalDocument.last_verified < cutoff_date
                )
            )
            
            if specialty:
                stmt = stmt.where(MedicalDocument.specialty == specialty)
            
            result = await session.execute(stmt)
            doc_ids = [row[0] for row in result]
        
        logger.info(f"Found {len(doc_ids)} documents needing validation")
        return doc_ids


# Global instances
_ingestion_engine = None
_attribution_engine = None
_learning_engine = None


def get_ingestion_engine() -> DocumentIngestionEngine:
    """Get or create document ingestion engine."""
    global _ingestion_engine
    if _ingestion_engine is None:
        _ingestion_engine = DocumentIngestionEngine()
    return _ingestion_engine


def get_attribution_engine() -> SourceAttributionEngine:
    """Get or create source attribution engine."""
    global _attribution_engine
    if _attribution_engine is None:
        _attribution_engine = SourceAttributionEngine()
    return _attribution_engine


def get_learning_engine() -> SelfLearningEngine:
    """Get or create self-learning engine."""
    global _learning_engine
    if _learning_engine is None:
        _learning_engine = SelfLearningEngine()
    return _learning_engine
