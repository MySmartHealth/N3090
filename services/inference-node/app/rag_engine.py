"""
RAG Engine with PostgreSQL pgvector
Handles embeddings, vector storage, and evidence retrieval for medical AI.
"""
import os
import hashlib
import asyncio
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from loguru import logger

# Import sentence transformers for embeddings
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.warning("sentence-transformers not installed, embeddings disabled")

# Import database functions
try:
    from app.database import search_medical_documents, search_patient_context, AsyncSessionLocal
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    logger.warning("Database not available, RAG retrieval disabled")


@dataclass
class Document:
    """A retrievable document."""
    id: str
    content: str
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None


@dataclass
class RetrievalResult:
    """Search result with score."""
    document: Document
    score: float
    rank: int


class EmbeddingEngine:
    """
    Generates embeddings using sentence-transformers (BGE-large-en-v1.5).
    Optimized for medical/biomedical text with GPU acceleration.
    """
    
    def __init__(self, model_name: Optional[str] = None):
        """
        Initialize embedding model.
        
        Args:
            model_name: HuggingFace model name (default: BAAI/bge-large-en-v1.5)
        """
        self.model_name = model_name or os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")
        self.dimension = int(os.getenv("VECTOR_DIM", "1024"))
        self.model = None
        
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                logger.info(f"Loading embedding model: {self.model_name}")
                # Use CPU for embeddings to avoid GPU OOM (LLMs use GPU)
                device = os.getenv("EMBEDDING_DEVICE", "cpu")
                self.model = SentenceTransformer(
                    self.model_name,
                    device=device
                )
                self.dimension = self.model.get_sentence_embedding_dimension()
                logger.info(f"Embedding model loaded (dim={self.dimension}, device={device})")
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")
                self.model = None
        else:
            logger.warning("sentence-transformers not available, using stub embeddings")
    
    def encode(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """
        Generate embeddings for texts.
        
        Args:
            texts: List of text strings
            batch_size: Batch size for encoding
            
        Returns:
            List of embedding vectors (dimension: 1024 for BGE-large)
        """
        if self.model:
            try:
                # Real embeddings using sentence-transformers
                embeddings = self.model.encode(
                    texts,
                    batch_size=batch_size,
                    convert_to_numpy=True,
                    show_progress_bar=len(texts) > 100
                )
                return embeddings.tolist()
            except Exception as e:
                logger.error(f"Embedding encoding failed: {e}, falling back to stub")
        
        # Stub: return hash-based embeddings if model unavailable
        logger.warning(f"Using stub embeddings for {len(texts)} texts")
        embeddings = []
        for text in texts:
            # Deterministic stub embedding
            hash_val = int(hashlib.sha256(text.encode()).hexdigest(), 16)
            embedding = [(hash_val >> (i * 8)) % 256 / 255.0 for i in range(self.dimension)]
            embeddings.append(embedding)
        
        logger.debug(f"Generated {len(embeddings)} embeddings (stub)")
        return embeddings
    
    def encode_single(self, text: str) -> List[float]:
        """Encode a single text."""
        return self.encode([text])[0]


class VectorStore:
    """In-memory vector store with cosine similarity search."""
    
    def __init__(self):
        self.documents: Dict[str, Document] = {}
        self.embeddings_engine = EmbeddingEngine()
    
    def add_documents(self, documents: List[Document]):
        """Add documents to the store and generate embeddings."""
        texts = [doc.content for doc in documents]
        embeddings = self.embeddings_engine.encode(texts)
        
        for doc, emb in zip(documents, embeddings):
            doc.embedding = emb
            self.documents[doc.id] = doc
        
        logger.info(f"Added {len(documents)} documents to vector store")
    
    def search(self, query: str, top_k: int = 5) -> List[RetrievalResult]:
        """
        Search for documents using cosine similarity.
        
        Args:
            query: Search query text
            top_k: Number of results to return
            
        Returns:
            Ranked retrieval results
        """
        if not self.documents:
            logger.warning("Vector store is empty")
            return []
        
        # Encode query
        query_emb = self.embeddings_engine.encode_single(query)
        
        # Calculate similarities
        scores = []
        for doc_id, doc in self.documents.items():
            if doc.embedding:
                score = self._cosine_similarity(query_emb, doc.embedding)
                scores.append((doc, score))
        
        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)
        
        # Return top_k results
        results = [
            RetrievalResult(document=doc, score=score, rank=i+1)
            for i, (doc, score) in enumerate(scores[:top_k])
        ]
        
        logger.info(f"Retrieved {len(results)} documents for query")
        return results
    
    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot_product / (norm_a * norm_b)


class RAGEngine:
    """
    Retrieval-Augmented Generation engine with PostgreSQL pgvector backend.
    """
    
    def __init__(self):
        """Initialize RAG engine with embedding model and database connection."""
        self.embeddings_engine = EmbeddingEngine()
        self.dimension = self.embeddings_engine.dimension
        
        # Legacy in-memory stores for backward compatibility
        self.stores: Dict[str, VectorStore] = {
            "medical_literature": VectorStore(),
            "insurance_policies": VectorStore(),
            "clinical_guidelines": VectorStore(),
        }
        self._load_sample_documents()
        
        logger.info(f"RAG engine initialized (dim={self.dimension})")
    
    async def search_medical_knowledge(
        self,
        query: str,
        limit: int = 5,
        specialty: Optional[str] = None,
        document_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search medical knowledge base using pgvector.
        
        Args:
            query: Search query text
            limit: Number of results to return
            specialty: Filter by medical specialty
            document_type: Filter by document type (guideline, protocol, reference)
            
        Returns:
            List of relevant documents with metadata
        """
        if not DB_AVAILABLE:
            logger.warning("Database not available, using in-memory fallback")
            return self._fallback_search(query, limit)
        
        try:
            # Generate query embedding
            query_embedding = self.embeddings_engine.encode_single(query)
            
            # Search using pgvector (async)
            from app.database import search_medical_documents
            async with AsyncSessionLocal() as session:
                results = await search_medical_documents(
                    query_embedding=query_embedding,
                    limit=limit,
                    specialty=specialty,
                    document_type=document_type
                )
            
            # Format results
            documents = []
            for result in results:
                documents.append({
                    "id": result.document_id,
                    "title": result.title,
                    "content": result.content,
                    "type": result.document_type,
                    "specialty": result.specialty,
                    "source": result.source_url,
                    "metadata": result.metadata or {}
                })
            
            logger.info(f"Retrieved {len(documents)} documents from pgvector")
            return documents
            
        except Exception as e:
            logger.error(f"Database search failed: {e}, falling back to in-memory")
            return self._fallback_search(query, limit)
    
    async def search_patient_specific(
        self,
        query: str,
        patient_id: str,
        limit: int = 3,
        context_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search patient-specific context for personalized RAG.
        
        Args:
            query: Search query text
            patient_id: Patient identifier
            limit: Number of results
            context_type: Filter by context type (allergy, diagnosis, medication)
            
        Returns:
            Patient-specific context items
        """
        if not DB_AVAILABLE:
            logger.warning("Database not available for patient search")
            return []
        
        try:
            query_embedding = self.embeddings_engine.encode_single(query)
            
            from app.database import search_patient_context
            async with AsyncSessionLocal() as session:
                results = await search_patient_context(
                    query_embedding=query_embedding,
                    patient_id=patient_id,
                    limit=limit,
                    context_type=context_type
                )
            
            contexts = []
            for result in results:
                contexts.append({
                    "id": result.id,
                    "patient_id": result.patient_id,
                    "type": result.context_type,
                    "content": result.content,
                    "location_id": result.location_id,
                    "metadata": result.metadata or {}
                })
            
            logger.info(f"Retrieved {len(contexts)} patient contexts")
            return contexts
            
        except Exception as e:
            logger.error(f"Patient context search failed: {e}")
            return []
    
    def _fallback_search(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Fallback to in-memory vector store if database unavailable."""
        results = []
        for store_name, store in self.stores.items():
            store_results = store.search(query, top_k=limit)
            for result in store_results:
                results.append({
                    "id": result.document.id,
                    "content": result.document.content,
                    "score": result.score,
                    "rank": result.rank,
                    "source": store_name,
                    "metadata": result.document.metadata
                })
        
        # Sort by score and return top limit
        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        return results[:limit]
    
    def _load_sample_documents(self):
        """Load sample documents (stub)."""
        # Medical literature samples
        med_docs = [
            Document(
                id="med-001",
                content="Acute cough is typically caused by viral upper respiratory infections. "
                        "Most cases resolve without antibiotics within 2-3 weeks.",
                metadata={"source": "clinical_guidelines", "year": 2023}
            ),
            Document(
                id="med-002",
                content="Procedure code 99213: Office visit, established patient, 20-29 minutes. "
                        "Requires at least two of: detailed history, detailed exam, low complexity MDM.",
                metadata={"source": "cpt_codes", "category": "E/M"}
            ),
        ]
        
        # Insurance policy samples
        policy_docs = [
            Document(
                id="policy-001",
                content="Pre-authorization required for MRI, CT scans, and procedures exceeding $5000. "
                        "Emergency services exempt from pre-auth requirements.",
                metadata={"source": "coverage_policy", "plan": "gold"}
            ),
        ]
        
        self.stores["medical_literature"].add_documents(med_docs)
        self.stores["insurance_policies"].add_documents(policy_docs)
        
        logger.info("Sample documents loaded into RAG stores")
    
    def retrieve(
        self,
        query: str,
        store_name: str = "medical_literature",
        top_k: int = 5
    ) -> List[RetrievalResult]:
        """
        Retrieve relevant documents from a specific store.
        
        Args:
            query: Search query
            store_name: Which document store to search
            top_k: Number of results
            
        Returns:
            Ranked results
        """
        store = self.stores.get(store_name)
        if not store:
            logger.error(f"Store not found: {store_name}")
            return []
        
        return store.search(query, top_k=top_k)
    
    def get_context_for_agent(
        self,
        agent_type: str,
        query: str,
        top_k: int = 3
    ) -> str:
        """
        Get RAG context formatted for agent prompts.
        
        Args:
            agent_type: Agent requesting context
            query: User query
            top_k: Number of documents to retrieve
            
        Returns:
            Formatted context string
        """
        # Route to appropriate store
        store_mapping = {
            "Documentation": "medical_literature",
            "MedicalQA": "medical_literature",
            "Claims": "insurance_policies",
            "Billing": "insurance_policies",
        }
        
        store_name = store_mapping.get(agent_type, "medical_literature")
        results = self.retrieve(query, store_name, top_k)
        
        if not results:
            return ""
        
        # Format as context
        context_parts = ["Retrieved evidence:"]
        for result in results:
            context_parts.append(
                f"[{result.rank}] (relevance: {result.score:.2f}) "
                f"{result.document.content}"
            )
        
        return "\n".join(context_parts)
