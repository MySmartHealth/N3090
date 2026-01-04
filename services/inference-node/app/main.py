import os
import time
import hashlib
import uuid
from typing import List, Optional, Dict, Any
from datetime import timedelta

from fastapi import FastAPI, Header, HTTPException, status, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from jose import jwt, JWTError
from loguru import logger
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy.ext.asyncio import AsyncSession

from .model_router import ModelRouter
from .rag_engine import RAGEngine
from .orchestrator import get_orchestrator, WorkflowType, AgentTask, WorkflowResult
from .auth import get_current_user, create_access_token, verify_password, User
from .database import get_db
from .middleware import (
    RateLimitMiddleware,
    PolicyEnforcementMiddleware,
    AuditEnrichmentMiddleware,
    ErrorHandlingMiddleware,
    SecurityHeadersMiddleware,
)

# Import knowledge base routes
try:
    from .knowledge_routes import router as knowledge_router
    KNOWLEDGE_ROUTES_AVAILABLE = True
except ImportError:
    KNOWLEDGE_ROUTES_AVAILABLE = False
    logger.warning("Knowledge base routes not available")

# Import web scraper
try:
    from .web_scraper import web_scraper, medical_scraper
    WEB_SCRAPER_AVAILABLE = True
except ImportError:
    WEB_SCRAPER_AVAILABLE = False
    logger.warning("Web scraper not available")

# Import agent key routes
try:
    from .agent_keys import router as agent_keys_router
    AGENT_KEYS_AVAILABLE = True
except ImportError:
    AGENT_KEYS_AVAILABLE = False
    logger.warning("Agent keys routes not available")

# Import web scraping routes
try:
    from .web_scraping_routes import router as web_scraping_router
    WEB_SCRAPING_ROUTES_AVAILABLE = True
except ImportError:
    WEB_SCRAPING_ROUTES_AVAILABLE = False
    logger.warning("Web scraping routes not available")

# Import AI Scribe & Document Processing routes
try:
    from .scribe_routes import router as scribe_router
    SCRIBE_ROUTES_AVAILABLE = True
except ImportError:
    SCRIBE_ROUTES_AVAILABLE = False
    logger.warning("AI Scribe routes not available")

# Import Multilingual Translation routes (IndicTrans2)
try:
    from .translation_routes import router as translation_router
    TRANSLATION_ROUTES_AVAILABLE = True
except ImportError:
    TRANSLATION_ROUTES_AVAILABLE = False
    logger.warning("Translation routes not available")

# Import Admin Dashboard routes
try:
    from .admin_routes import router as admin_router
    ADMIN_ROUTES_AVAILABLE = True
except ImportError:
    ADMIN_ROUTES_AVAILABLE = False
    logger.warning("Admin dashboard routes not available")

# Import GPU Load Balancing routes
try:
    from .gpu_load_balancing_routes import router as gpu_routes
    GPU_ROUTES_AVAILABLE = True
except ImportError:
    GPU_ROUTES_AVAILABLE = False
    logger.warning("GPU load balancing routes not available")

# Import Async Task Queue routes
try:
    from .async_task_routes import router as async_routes
    ASYNC_ROUTES_AVAILABLE = True
except ImportError:
    ASYNC_ROUTES_AVAILABLE = False
    logger.warning("Async task queue routes not available")

# Import Advanced AI routes (VLP, XAI, Gen AI, Quantum ML, SSL)
try:
    from .advanced_ai_routes import router as advanced_ai_routes
    ADVANCED_AI_ROUTES_AVAILABLE = True
except ImportError:
    ADVANCED_AI_ROUTES_AVAILABLE = False
    logger.warning("Advanced AI routes not available")

# Configure logging: avoid PHI; only metadata
logger.remove()
logger.add(lambda msg: print(msg, end=""), level="INFO")

app = FastAPI(
    title="Inference Node - Synthetic Intelligence Platform",
    version="1.0.0",
    description="Multi-model medical AI platform with JWT authentication"
)

# Initialize Prometheus metrics
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

# Initialize backend components
model_router = ModelRouter()
rag_engine = RAGEngine()
orchestrator = get_orchestrator(model_router)

# Initialize GPU-aware load balancer
try:
    from .gpu_orchestrator import initialize_load_balancer
    load_balancer = None
    LOAD_BALANCER_ENABLED = True
except ImportError:
    LOAD_BALANCER_ENABLED = False
    logger.warning("GPU load balancer not available")

# Include knowledge base routes if available
if KNOWLEDGE_ROUTES_AVAILABLE:
    app.include_router(knowledge_router)
    logger.info("Knowledge base routes enabled")

# Include agent key management routes
if AGENT_KEYS_AVAILABLE:
    app.include_router(agent_keys_router)
    logger.info("Agent key management routes enabled")

# Include web scraping routes
if WEB_SCRAPING_ROUTES_AVAILABLE:
    app.include_router(web_scraping_router)
    logger.info("Web scraping routes enabled")

# Include AI Scribe & Document Processing routes
if SCRIBE_ROUTES_AVAILABLE:
    app.include_router(scribe_router)
    logger.info("AI Scribe & Document Processing routes enabled")

# Include Multilingual Translation routes
if TRANSLATION_ROUTES_AVAILABLE:
    app.include_router(translation_router)
    logger.info("Multilingual Translation (IndicTrans2) routes enabled")

# Include Admin Dashboard routes
if ADMIN_ROUTES_AVAILABLE:
    app.include_router(admin_router)
    logger.info("Admin dashboard routes enabled")

# Include GPU Load Balancing routes
if GPU_ROUTES_AVAILABLE:
    app.include_router(gpu_routes)
    logger.info("GPU load balancing routes enabled")

# Include Async Task Queue routes
if ASYNC_ROUTES_AVAILABLE:
    app.include_router(async_routes)
    logger.info("Async task queue routes enabled")

# Include Advanced AI routes (VLP, XAI, Gen AI, Quantum ML, SSL)
if ADVANCED_AI_ROUTES_AVAILABLE:
    app.include_router(advanced_ai_routes)
    logger.info("Advanced AI routes enabled (VLP, XAI, Gen AI, Quantum ML, SSL)")

# Mount static files for web UI
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    logger.info(f"Static files enabled: {static_dir}")

# Add middleware layers (order matters: first added = outermost)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(ErrorHandlingMiddleware)
app.add_middleware(AuditEnrichmentMiddleware)
app.add_middleware(PolicyEnforcementMiddleware)
app.add_middleware(RateLimitMiddleware, max_requests=100, window_seconds=60)

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE")
JWT_ISSUER = os.getenv("JWT_ISSUER")
ALLOW_INSECURE_DEV = os.getenv("ALLOW_INSECURE_DEV", "").lower() in {"1", "true", "yes"}

ALLOWED_AGENTS = {
    "Chat",
    "FastChat",    # Qwen 0.6B - ultra-lightweight
    "Appointment",
    "Documentation",
    "Billing",
    "Claims",
    "Monitoring",
    "MedicalQA",
    "AIDoctor",    # NEW: Comprehensive diagnosis (BioMistral + Medicine-LLM)
    "Scribe",      # Clinical documentation
    "ClaimsOCR",   # Document processing + adjudication
    "Clinical",    # BioMistral Clinical decision support
    "Translate",   # Multilingual translation (IndicTrans2) - 22+ Indian languages
}

# Agent-specific API keys (in-memory storage, can be moved to database)
AGENT_API_KEYS: Dict[str, Dict[str, str]] = {
    # Format: agent_type -> {"api_key": "key_value", "created_at": "timestamp", "description": "..."}
    # Example:
    # "Claims": {"api_key": "claims-key-123", "created_at": "2026-01-04", "description": "Insurance claims agent"},
}

# Master admin key for API key management
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")

class EvidenceRequest(BaseModel):
    query: str
    store: str = "medical_literature"
    top_k: int = 5


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: f"req-{uuid.uuid4().hex[:12]}")
    agent_type: str
    model: Optional[str] = None
    constraints: Optional[Dict[str, Any]] = None
    messages: List[Message]
    # Translation parameters
    user_language: Optional[str] = Field(
        None, 
        description="User's preferred language (e.g., 'hi', 'ta', 'en'). If set, response will be translated."
    )
    translate_input: Optional[bool] = Field(
        False,
        description="Whether to translate input messages to system language before processing"
    )

class ChoiceMessage(BaseModel):
    role: str
    content: str

class Choice(BaseModel):
    index: int
    finish_reason: str
    message: ChoiceMessage

class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class ChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str = "stub-local"
    choices: List[Choice]
    usage: Usage
    policy: Dict[str, Any]
    # Translation metadata
    translation: Optional[Dict[str, Any]] = None  # Translation info if translation was applied


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _compute_prompt_hash(messages: List[Message]) -> str:
    # Concatenate roles + SHA256 of content to avoid PHI exposure
    parts = []
    for m in messages:
        parts.append(f"{m.role}:{_hash_text(m.content)}")
    return _hash_text("|".join(parts))


def _verify_jwt(token: Optional[str]) -> None:
    if JWT_SECRET:
        if not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"], audience=JWT_AUDIENCE, issuer=JWT_ISSUER)
            # Minimal check: exp enforced by jose
            if not payload:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        except JWTError as e:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Unauthorized: {str(e)}")
    else:
        if not ALLOW_INSECURE_DEV:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="JWT not configured; set ALLOW_INSECURE_DEV=true for local testing")





@app.post("/v1/chat/completions", response_model=ChatResponse)
async def chat_completions(
    req: ChatRequest,
    request: Request,
    current_user: User = Depends(get_current_user) if not ALLOW_INSECURE_DEV else None,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    agent_type_header: Optional[str] = Header(default=None, alias="X-Agent-Type"),
):
    """
    OpenAI-compatible chat completions endpoint with JWT authentication.
    In production (ALLOW_INSECURE_DEV=false), requires valid JWT token.
    """
    # Legacy JWT verification for backward compatibility
    if not ALLOW_INSECURE_DEV and current_user is None:
        bearer = None
        if authorization and authorization.lower().startswith("bearer "):
            bearer = authorization[7:].strip()
        _verify_jwt(bearer)

    agent_type = agent_type_header or req.agent_type
    if agent_type not in ALLOWED_AGENTS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or unsupported agent type")

    if not req.messages or len(req.messages) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="messages must be non-empty")

    # Audit-friendly metadata
    prompt_hash = _compute_prompt_hash(req.messages)
    created_ts = int(time.time())
    resp_id = f"cmpl-{uuid.uuid4().hex[:24]}"

    mode = (req.constraints or {}).get("mode", "draft-only")
    policy_flags = {
        "agent_type": agent_type,
        "constraints_mode": mode,
        "draft_only": mode == "draft-only",
        "side_effects": False,
    }

    # Get RAG context if applicable
    last_user = next((m.content for m in reversed(req.messages) if m.role == "user"), "")
    rag_context = ""
    if agent_type in ["Documentation", "MedicalQA", "Claims", "Billing"]:
        try:
            rag_context = rag_engine.get_context_for_agent(agent_type, last_user, top_k=3)
            if rag_context:
                # Prepend context as system message
                req.messages.insert(0, Message(role="system", content=rag_context))
            else:
                # No context found - add instruction to use model's built-in knowledge
                fallback_instructions = {
                    "Claims": "You are an insurance claims specialist. Use your knowledge of standard health insurance policies, coverage rules, and claims processing to answer the user's question. Provide helpful information about typical coverage while noting that specific policy details may vary.",
                    "Billing": "You are a medical billing expert. Use your knowledge of ICD-10, CPT codes, insurance reimbursement rules, and medical billing procedures to answer the user's question.",
                    "MedicalQA": "You are a medical expert. Use your medical knowledge to provide an accurate, evidence-based answer to the user's question.",
                    "Documentation": "You are a medical documentation specialist. Use your knowledge to help with the medical documentation request."
                }
                instruction = fallback_instructions.get(agent_type, "You are a helpful AI assistant. Answer the question to the best of your ability.")
                req.messages.insert(0, Message(role="system", content=instruction))
        except Exception as e:
            logger.warning(f"RAG retrieval failed: {e}")
            rag_context = ""

    # Generate response using model router
    try:
        generation_result = await model_router.generate(
            agent_type=agent_type,
            messages=[{"role": m.role, "content": m.content} for m in req.messages],
            constraints=req.constraints,
            max_tokens=getattr(request.state, "max_tokens", 512),
            temperature=0.7,
        )
        content = generation_result["text"]
        model_used = generation_result["model"]
        inference_time = generation_result["inference_time_s"]
    except Exception as e:
        logger.error(f"Model router error: {e}")
        # Fallback to stub
        content = (
            f"Draft only. No side effects.\n\n"
            f"Summary (proposed, not final):\n"
            f"- User input hash: {_hash_text(last_user)}\n"
            f"- Agent: {agent_type}\n"
            f"- Constraints: {mode}\n\n"
            f"Model router unavailable. Using fallback response."
        )
        model_used = "fallback"
        inference_time = 0.0

    # Token usage: coarse estimate
    prompt_tokens = max(1, len(" ".join([m.content for m in req.messages])) // 4)
    completion_tokens = max(1, len(content) // 4)

    # Handle translation if requested
    translation_metadata = None
    if req.user_language and req.user_language != "en":
        try:
            from .translation_integration import get_translation_service, TranslationContext
            
            translation_service = get_translation_service()
            result = await translation_service.translate_message(
                content,
                source_language="en",
                target_language=req.user_language,
                context=TranslationContext.CHAT
            )
            
            if result.is_translated:
                translation_metadata = {
                    "source_language": "en",
                    "target_language": req.user_language,
                    "confidence": result.confidence,
                    "model": result.model_used,
                    "original_content": content
                }
                content = result.translated_text
                logger.info(f"Translated response to {req.user_language} (confidence: {result.confidence})")
        except Exception as e:
            logger.warning(f"Translation to {req.user_language} failed: {e}")

    logger.info(
        f"AUDIT req_id={req.request_id} resp_id={resp_id} agent={agent_type} "
        f"prompt_hash={prompt_hash} model={model_used} created={created_ts} "
        f"inference_time={inference_time:.3f}s rag_used={bool(rag_context)} "
        f"translated={bool(translation_metadata)}\n"
    )

    return ChatResponse(
        id=resp_id,
        created=created_ts,
        model=model_used,
        choices=[
            Choice(index=0, finish_reason="stop", message=ChoiceMessage(role="assistant", content=content))
        ],
        usage=Usage(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=prompt_tokens + completion_tokens),
        policy=policy_flags,
        translation=translation_metadata,
    )


@app.get("/healthz")
async def healthz():
    """Health check with backend connectivity status."""
    import httpx
    
    health_status = {
        "status": "ok",
        "ts": int(time.time()),
        "backends": {}
    }
    
    # Check llama.cpp server connectivity
    llama_server = model_router.LLAMA_CPP_SERVER
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(f"{llama_server}/health")
            if resp.status_code == 200:
                health_status["backends"]["llama_cpp"] = {"status": "connected", "url": llama_server}
            else:
                health_status["backends"]["llama_cpp"] = {"status": "unhealthy", "url": llama_server}
    except Exception as e:
        health_status["backends"]["llama_cpp"] = {"status": "disconnected", "url": llama_server, "error": str(e)}
        health_status["status"] = "degraded"
    
    return health_status


@app.get("/models")
async def get_models():
    """Return available models and agent mappings."""
    return model_router.get_model_info()


@app.post("/evidence/retrieve")
async def retrieve_evidence(
    req: EvidenceRequest,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
):
    """Retrieve evidence from RAG stores."""
    bearer = None
    if authorization and authorization.lower().startswith("bearer "):
        bearer = authorization[7:].strip()
    _verify_jwt(bearer)
    
    results = rag_engine.retrieve(req.query, req.store, req.top_k)
    
    return {
        "query": req.query,
        "store": req.store,
        "results": [
            {
                "rank": r.rank,
                "score": r.score,
                "content": r.document.content,
                "metadata": r.document.metadata,
            }
            for r in results
        ]
    }


# ==================== ORCHESTRATOR ENDPOINTS ====================

class WorkflowRequest(BaseModel):
    """Request for executing a multi-agent workflow."""
    workflow_type: str
    context: Dict[str, Any]
    custom_tasks: Optional[List[Dict[str, Any]]] = None


class WorkflowResponseModel(BaseModel):
    """Response from workflow execution."""
    workflow_type: str
    success: bool
    aggregated_content: str
    total_latency_ms: float
    parallel_efficiency: float
    metadata: Dict[str, Any]
    results: List[Dict[str, Any]]


@app.post("/v1/workflows/execute", response_model=WorkflowResponseModel)
async def execute_workflow(
    req: WorkflowRequest,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
):
    """
    Execute a multi-agent workflow with parallel task execution.
    
    Supported workflow types:
    - discharge_summary: Clinical summary + Billing codes
    - pharmacy_documentation: Drug analysis + Pharmacy billing
    - insurance_claim: Medical necessity + Claim processing
    - lab_report: Clinical lab interpretation
    - radiology_report: Radiology interpretation
    - comprehensive_assessment: All agents in parallel
    - billing_with_justification: Medical justification + Billing
    - parallel_qa: Same question to multiple agents
    """
    bearer = None
    if authorization and authorization.lower().startswith("bearer "):
        bearer = authorization[7:].strip()
    _verify_jwt(bearer)
    
    # Validate workflow type
    try:
        workflow_type = WorkflowType(req.workflow_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid workflow type: {req.workflow_type}. Valid types: {[t.value for t in WorkflowType]}"
        )
    
    # Convert custom tasks if provided
    custom_tasks = None
    if req.custom_tasks:
        custom_tasks = [
            AgentTask(
                agent_type=t["agent_type"],
                prompt=t["prompt"],
                priority=t.get("priority", 0),
                max_tokens=t.get("max_tokens", 512),
                temperature=t.get("temperature", 0.7),
                dependencies=t.get("dependencies", []),
                task_id=t.get("task_id")
            )
            for t in req.custom_tasks
        ]
    
    # Execute workflow
    result = await orchestrator.execute_workflow(
        workflow_type=workflow_type,
        context=req.context,
        custom_tasks=custom_tasks
    )
    
    # Convert result to response
    return WorkflowResponseModel(
        workflow_type=result.workflow_type,
        success=result.success,
        aggregated_content=result.aggregated_content,
        total_latency_ms=result.total_latency_ms,
        parallel_efficiency=result.parallel_efficiency,
        metadata=result.metadata,
        results=[
            {
                "task_id": r.task_id,
                "agent_type": r.agent_type,
                "success": r.success,
                "content": r.content,
                "model": r.model,
                "latency_ms": r.latency_ms,
                "tokens": r.tokens,
                "error": r.error,
                "metadata": r.metadata
            }
            for r in result.results
        ]
    )


@app.get("/v1/workflows/types")
async def list_workflow_types():
    """List available workflow types and their descriptions."""
    workflows = {
        "discharge_summary": {
            "description": "Generate discharge summary with clinical content and billing codes",
            "agents": ["Clinical", "Billing"],
            "parallel": True,
            "required_context": ["patient_data", "admission_date", "discharge_date"]
        },
        "pharmacy_documentation": {
            "description": "Pharmacy documentation with drug analysis and billing",
            "agents": ["Clinical", "Billing"],
            "parallel": False,  # Billing depends on clinical
            "required_context": ["medications", "patient_info"]
        },
        "insurance_claim": {
            "description": "Insurance claim with medical necessity justification",
            "agents": ["MedicalQA", "Claims"],
            "parallel": False,
            "required_context": ["procedure", "diagnosis", "patient_data"]
        },
        "lab_report": {
            "description": "Clinical interpretation of laboratory results",
            "agents": ["Clinical"],
            "parallel": False,
            "required_context": ["lab_results", "patient_info"]
        },
        "radiology_report": {
            "description": "Radiology report generation",
            "agents": ["Clinical"],
            "parallel": False,
            "required_context": ["findings", "study_type"]
        },
        "comprehensive_assessment": {
            "description": "Comprehensive patient assessment using all agents",
            "agents": ["MedicalQA", "Clinical", "Billing"],
            "parallel": True,
            "required_context": ["patient_case"]
        },
        "billing_with_justification": {
            "description": "Billing codes with medical justification",
            "agents": ["MedicalQA", "Billing"],
            "parallel": False,
            "required_context": ["service"]
        },
        "parallel_qa": {
            "description": "Send same question to multiple agents for comparison",
            "agents": ["MedicalQA", "Clinical"],
            "parallel": True,
            "required_context": ["question"]
        }
    }
    
    return {
        "workflows": workflows,
        "total_count": len(workflows)
    }


@app.post("/v1/workflows/discharge-summary")
async def quick_discharge_summary(
    patient_data: str,
    admission_date: str,
    discharge_date: str,
    current_user: User = Depends(get_current_user) if not ALLOW_INSECURE_DEV else None,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
):
    """Quick endpoint for discharge summary generation."""
    if not ALLOW_INSECURE_DEV:
        bearer = None
        if authorization and authorization.lower().startswith("bearer "):
            bearer = authorization[7:].strip()
        _verify_jwt(bearer)
    
    result = await orchestrator.execute_workflow(
        workflow_type=WorkflowType.DISCHARGE_SUMMARY,
        context={
            "patient_data": patient_data,
            "admission_date": admission_date,
            "discharge_date": discharge_date
        }
    )
    
    return {
        "success": result.success,
        "content": result.aggregated_content,
        "latency_ms": result.total_latency_ms,
        "efficiency": result.parallel_efficiency
    }


# ============================================================================
# JWT Authentication Endpoints
# ============================================================================

class LoginRequest(BaseModel):
    """Login credentials."""
    username: str
    password: str
    location_id: Optional[str] = None


class TokenResponse(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


@app.post("/v1/auth/login", response_model=TokenResponse)
async def login(credentials: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Authenticate user and issue JWT token.
    Verifies credentials against PostgreSQL database.
    """
    from app.auth import authenticate_user
    
    # Authenticate against database
    user = await authenticate_user(credentials.username, credentials.password, db)
    
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create JWT token
    token_data = {
        "sub": user.username,
        "location_id": user.location_id,
    }
    
    access_token = create_access_token(
        data=token_data,
        expires_delta=timedelta(hours=24)
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=24 * 3600  # 24 hours in seconds
    )


@app.get("/v1/auth/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Get current authenticated user information.
    Requires valid JWT token.
    """
    return {
        "username": current_user.username,
        "location_id": current_user.location_id,
        "authenticated": True
    }


class ChangePasswordRequest(BaseModel):
    """Password change request."""
    current_password: str
    new_password: str


@app.post("/v1/auth/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Change current user's password.
    Requires valid JWT token and current password verification.
    """
    from app.auth import authenticate_user, pwd_context
    from sqlalchemy import update
    from app.database import User as DBUser
    
    # Verify current password
    user = await authenticate_user(current_user.username, request.current_password, db)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Current password is incorrect"
        )
    
    # Validate new password strength
    if len(request.new_password) < 8:
        raise HTTPException(
            status_code=400,
            detail="New password must be at least 8 characters long"
        )
    
    # Hash new password
    hashed_password = pwd_context.hash(request.new_password)
    
    # Update password in database
    stmt = (
        update(DBUser)
        .where(DBUser.username == current_user.username)
        .values(hashed_password=hashed_password)
    )
    await db.execute(stmt)
    await db.commit()
    
    logger.info(f"Password changed for user: {current_user.username}")
    
    return {
        "status": "success",
        "message": "Password changed successfully"
    }


# Startup event: Initialize GPU load balancer
@app.on_event("startup")
async def startup_event():
    """Initialize GPU load balancer on startup"""
    global load_balancer
    try:
        if globals().get('LOAD_BALANCER_ENABLED', False):
            from .gpu_orchestrator import get_load_balancer
            load_balancer = get_load_balancer()
            # Register models
            from .gpu_orchestrator import BackendType
            load_balancer.register_model("tiny-llama-1b", BackendType.LLAMA_CPP, 2.3, 8080)
            load_balancer.register_model("bi-medix2", BackendType.LLAMA_CPP, 6.5, 8081)
            load_balancer.register_model("openins-llama3-8b", BackendType.LLAMA_CPP, 7.8, 8084)
            logger.info("✓ GPU load balancer ready")
    except Exception as e:
        logger.info(f"GPU load balancer skipped: {e}")


# Shutdown event: Stop GPU monitoring
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    if LOAD_BALANCER_ENABLED and load_balancer:
        try:
            load_balancer.stop()
            logger.info("✓ GPU load balancer stopped")
        except Exception as e:
            logger.error(f"Error stopping GPU load balancer: {e}")
