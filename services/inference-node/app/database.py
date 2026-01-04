"""
Database layer using PostgreSQL with pgvector for RAG and user management.

PostgreSQL chosen for:
- pgvector extension: Native vector similarity search for RAG
- HNSW indexing: Fast approximate nearest neighbor search
- Hybrid storage: Users, sessions, chat history + embeddings
- Battle-tested: Industry standard for AI/ML applications
"""
import os
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, DateTime, Text, Boolean, Integer, func, select, text
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector
from loguru import logger


# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://medical_ai:medical_ai_pass@localhost:5432/medical_ai"
)

# Vector dimension for embeddings (BGE-large: 1024, OpenAI: 1536, etc.)
VECTOR_DIM = int(os.getenv("VECTOR_DIM", "1024"))


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class User(Base):
    """User accounts with hashed passwords for JWT authentication."""
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    location_id: Mapped[str] = mapped_column(String(50), default="default")
    preferred_language: Mapped[str] = mapped_column(String(10), default="en", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, onupdate=func.now())
    
    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, location={self.location_id}, language={self.preferred_language})>"


class ChatSession(Base):
    """Chat sessions for tracking conversations."""
    __tablename__ = "chat_sessions"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    location_id: Mapped[str] = mapped_column(String(50), index=True)
    agent_type: Mapped[str] = mapped_column(String(50), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    extra_data: Mapped[Optional[Dict]] = mapped_column(JSONB, nullable=True)
    
    def __repr__(self):
        return f"<ChatSession(id={self.id}, session_id={self.session_id}, agent={self.agent_type})>"


class ChatMessage(Base):
    """Individual chat messages with optional RAG context."""
    __tablename__ = "chat_messages"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(String(100), index=True)
    role: Mapped[str] = mapped_column(String(20))  # user, assistant, system
    content: Mapped[str] = mapped_column(Text)
    model_used: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rag_context_used: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Self-learning feedback
    user_rating: Mapped[Optional[float]] = mapped_column(nullable=True)  # 1-5 rating
    user_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    extra_data: Mapped[Optional[Dict]] = mapped_column(JSONB, nullable=True)
    
    def __repr__(self):
        return f"<ChatMessage(id={self.id}, session={self.session_id}, role={self.role})>"


class MedicalDocument(Base):
    """Medical documents/knowledge base with vector embeddings for RAG."""
    __tablename__ = "medical_documents"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text)
    document_type: Mapped[str] = mapped_column(String(50), index=True)  # guideline, protocol, reference, etc.
    specialty: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    
    # Vector embedding for semantic search (pgvector)
    # Use BGE-large-en-v1.5 (1024 dim) or similar medical embedding model
    embedding: Mapped[List[float]] = mapped_column(Vector(VECTOR_DIM))
    
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Knowledge validation and quality tracking
    quality_score: Mapped[float] = mapped_column(default=0.5)  # 0.0 - 1.0
    verification_status: Mapped[str] = mapped_column(String(50), default="unverified")  # verified, unverified, pending_review, outdated
    last_verified: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, onupdate=func.now())
    extra_data: Mapped[Optional[Dict]] = mapped_column(JSONB, nullable=True)
    
    def __repr__(self):
        return f"<MedicalDocument(id={self.id}, title={self.title[:50]}, type={self.document_type})>"


class PatientContext(Base):
    """Patient-specific context for personalized RAG retrieval."""
    __tablename__ = "patient_context"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[str] = mapped_column(String(100), index=True)
    context_type: Mapped[str] = mapped_column(String(50), index=True)  # allergy, diagnosis, medication, etc.
    content: Mapped[str] = mapped_column(Text)
    
    # Vector embedding for patient-specific semantic search
    embedding: Mapped[List[float]] = mapped_column(Vector(VECTOR_DIM))
    
    location_id: Mapped[str] = mapped_column(String(50), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, onupdate=func.now())
    extra_data: Mapped[Optional[Dict]] = mapped_column(JSONB, nullable=True)
    
    def __repr__(self):
        return f"<PatientContext(id={self.id}, patient={self.patient_id}, type={self.context_type})>"


# Database engine and session factory
engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("DB_ECHO", "false").lower() == "true",
    pool_size=int(os.getenv("DB_POOL_SIZE", "20")),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "40")),
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """Dependency for getting database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database schema and pgvector extension."""
    async with engine.begin() as conn:
        # Enable pgvector extension
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
        
        # Create HNSW index for fast vector similarity search on medical documents
        await conn.execute(text(
            f"""
            CREATE INDEX IF NOT EXISTS idx_medical_docs_embedding 
            ON medical_documents 
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
            """
        ))
        
        # Create HNSW index for patient context
        await conn.execute(text(
            f"""
            CREATE INDEX IF NOT EXISTS idx_patient_context_embedding 
            ON patient_context 
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
            """
        ))
        
    logger.info("Database initialized with pgvector extension and HNSW indexes")


async def create_admin_user(username: str, password: str, email: str):
    """Create initial admin user."""
    from app.auth import hash_password
    
    async with AsyncSessionLocal() as session:
        # Check if user exists
        result = await session.execute(
            select(User).where(User.username == username)
        )
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            logger.info(f"Admin user '{username}' already exists")
            return
        
        # Create new admin user
        hashed_pw = hash_password(password)
        admin = User(
            username=username,
            email=email,
            hashed_password=hashed_pw,
            is_admin=True,
            is_active=True,
            location_id="admin",
        )
        
        session.add(admin)
        await session.commit()
        logger.info(f"Created admin user: {username}")


# Vector search functions for RAG
async def search_medical_documents(
    query_embedding: List[float],
    limit: int = 5,
    specialty: Optional[str] = None,
    document_type: Optional[str] = None,
) -> List[MedicalDocument]:
    """
    Search medical documents using vector similarity.
    Uses pgvector's cosine similarity with HNSW index for fast retrieval.
    """
    async with AsyncSessionLocal() as session:
        query = select(MedicalDocument).order_by(
            MedicalDocument.embedding.cosine_distance(query_embedding)
        )
        
        if specialty:
            query = query.where(MedicalDocument.specialty == specialty)
        if document_type:
            query = query.where(MedicalDocument.document_type == document_type)
        
        query = query.limit(limit)
        
        result = await session.execute(query)
        return result.scalars().all()


async def search_patient_context(
    query_embedding: List[float],
    patient_id: str,
    limit: int = 3,
    context_type: Optional[str] = None,
) -> List[PatientContext]:
    """
    Search patient-specific context using vector similarity.
    Used for personalized RAG retrieval.
    """
    async with AsyncSessionLocal() as session:
        query = select(PatientContext).where(
            PatientContext.patient_id == patient_id
        ).order_by(
            PatientContext.embedding.cosine_distance(query_embedding)
        )
        
        if context_type:
            query = query.where(PatientContext.context_type == context_type)
        
        query = query.limit(limit)
        
        result = await session.execute(query)
        return result.scalars().all()
