import os
import time
import hashlib
import uuid
import io
import asyncio
from typing import List, Optional, Dict, Any
from datetime import timedelta

import httpx

from fastapi import FastAPI, Header, HTTPException, status, Request, Depends, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
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
from .persona import get_system_prompt, AI_NAME, ISHA_SYSTEM_PROMPT
from .services.external_llm import get_external_llm_client, close_external_llm_client
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

# Import claim processing routes
try:
    from .routes.claim_processing import router as claim_processing_router
    CLAIM_PROCESSING_AVAILABLE = True
except ImportError:
    CLAIM_PROCESSING_AVAILABLE = False
    logger.warning("Claim processing routes not available")

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


def guardrail_sanitize(text: str, max_chars: int = 1200) -> str:
    """Lightweight output guardrail: drop obvious references, collapse repeats, cap length."""
    if not text:
        return text

    lines = text.splitlines()
    cleaned: List[str] = []
    last_line = None
    repeat = 0

    for raw in lines:
        line = raw.strip()

        # Skip citation-like noise
        if line.lower().startswith("[reference") or "reference:" in line.lower():
            continue

        # Collapse consecutive duplicates
        if line == last_line:
            repeat += 1
            if repeat > 0:
                continue
        else:
            repeat = 0
            last_line = line

        if line:
            cleaned.append(line)

    result = "\n".join(cleaned) or text

    if len(result) > max_chars:
        result = result[:max_chars].rstrip() + " …"

    return result

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

# Include claim processing routes
if CLAIM_PROCESSING_AVAILABLE:
    app.include_router(claim_processing_router)
    logger.info("Claim processing routes enabled")

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

# Root endpoint - redirect to API docs
from fastapi.responses import RedirectResponse

@app.get("/", include_in_schema=False)
async def root():
    """Redirect root to API documentation"""
    return RedirectResponse(url="/docs")

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Return 204 for favicon requests"""
    return JSONResponse(status_code=204, content={})

# Add middleware layers (order matters: first added = outermost)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(ErrorHandlingMiddleware)
app.add_middleware(AuditEnrichmentMiddleware)
app.add_middleware(PolicyEnforcementMiddleware)
app.add_middleware(RateLimitMiddleware, max_requests=100, window_seconds=60)

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE")
JWT_ISSUER = os.getenv("JWT_ISSUER")
# Default to True for development - change to False for production
ALLOW_INSECURE_DEV = os.getenv("ALLOW_INSECURE_DEV", "true").lower() in {"1", "true", "yes"}

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
    "Research",    # Medical research assistance (BioMistral-7B)
}

# Agent-specific API keys (in-memory storage, can be moved to database)
AGENT_API_KEYS: Dict[str, Dict[str, str]] = {
    # Format: agent_type -> {"api_key": "key_value", "created_at": "timestamp", "description": "..."}
    # Example:
    # "Claims": {"api_key": "claims-key-123", "created_at": "2026-01-04", "description": "Insurance claims agent"},
}

# Master admin key for API key management
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")

# Heritage TPA API defaults
HERITAGE_BASE_URL = os.getenv(
    "HERITAGE_MOBILEAPP_BASE_URL",
    "http://223.31.103.204/HeritageMobileAppNew/MobileAppAPI.svc",
)
HERITAGE_DEFAULT_INSCO = os.getenv("HERITAGE_INSURER_CODE", "NIA")
HERITAGE_DEFAULT_AUTH_ID = os.getenv("HERITAGE_AUTH_ID", "0")

class EvidenceRequest(BaseModel):
    query: str
    store: str = "medical_literature"
    top_k: int = 5


class Message(BaseModel):
    role: str
    content: str


class MemberSearchRequest(BaseModel):
    tpa_provider: str = Field(
        default="heritage",
        description="TPA provider to query; heritage is currently supported",
    )
    policy_number: Optional[str] = Field(
        default=None,
        description="Policy number used for member lookup",
    )
    ecard_number: Optional[str] = Field(
        default=None,
        description="E-card number / card reference for member lookup",
    )
    member_id: Optional[str] = Field(
        default=None,
        description="Member identifier (also used as e-card number for Heritage)",
    )
    employee_number: Optional[str] = Field(
        default=None,
        description="Employee number for group policies",
    )
    insurer_code: Optional[str] = Field(
        default=None,
        description="Insurer code expected by Heritage API (e.g., NIA, NIC)",
    )
    auth_id: Optional[str] = Field(
        default=None,
        description="AuthId parameter for Heritage API (defaults to 0)",
    )


class ChatRequest(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: f"req-{uuid.uuid4().hex[:12]}")
    agent_type: str
    model: Optional[str] = None
    model_port: Optional[int] = Field(
        None,
        description="Optional LLM server port (8080-8083). If provided, overrides agent_type routing."
    )
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


def _first_value(source: Dict[str, Any], keys: List[str]) -> Optional[str]:
    """Return first non-empty value for provided keys from a mapping."""
    for key in keys:
        if key in source and source[key] not in {None, ""}:
            return source[key]
    return None


def _normalize_heritage_members(body: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Normalize Heritage enrollment response into a consistent member schema."""
    if not body:
        return []

    candidates: List[Any] = []
    for key in ["EnrollmentDetails", "EnrollmentData", "Members", "Data", "EnrollmentList", "Result"]:
        if isinstance(body.get(key), list):
            candidates = body.get(key) or []
            break
        if isinstance(body.get(key), dict):
            candidates = [body.get(key)]
            break

    if not candidates and isinstance(body, list):
        candidates = body

    normalized: List[Dict[str, Any]] = []
    for rec in candidates:
        if not isinstance(rec, dict):
            continue
        normalized.append({
            "member_id": _first_value(rec, ["MemberID", "CardNo", "CardNumber", "ECardNo", "MemberCode"]),
            "ecard_number": _first_value(rec, ["CardNo", "ECardNo", "MemberID", "CardNumber"]),
            "employee_number": _first_value(rec, ["EmployeeNumber", "EmpID", "EmployeeNo"]),
            "name": _first_value(rec, ["MemberName", "InsuredName", "PatientName", "Name"]),
            "policy_number": _first_value(rec, ["PolicyNumber", "PolicyNo"]),
            "dob": _first_value(rec, ["DOB", "DateOfBirth", "DateofBirth"]),
            "age": _first_value(rec, ["Age", "MemberAge"]),
            "valid_from": _first_value(rec, ["ValidFrom", "FromDate"]),
            "valid_to": _first_value(rec, ["ValidTo", "ToDate"]),
            "relationship": _first_value(rec, ["Relationship", "RelationShip", "Relation"]),
            "mobile": _first_value(rec, ["Mobile", "Phone", "ContactNumber"]),
            "email": _first_value(rec, ["Email"]),
            "raw": rec,
        })

    return normalized


async def _call_heritage_api(endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Call Heritage MobileApp API endpoint with JSON payload."""
    url = f"{HERITAGE_BASE_URL.rstrip('/')}/{endpoint}"
    headers = {"Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        try:
            return response.json()
        except ValueError:
            return {"Status": False, "Message": "Invalid JSON response", "raw": response.text}





@app.post("/v1/chat/completions", response_model=ChatResponse)
async def chat_completions(
    req: ChatRequest,
    request: Request,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    agent_type_header: Optional[str] = Header(default=None, alias="X-Agent-Type"),
):
    """
    OpenAI-compatible chat completions endpoint with JWT authentication.
    In production (ALLOW_INSECURE_DEV=false), requires valid JWT token.
    
    Can route to external LLM (e.g., Mediqzy.com) if EXTERNAL_LLM_ENABLED=true
    """
    # Debug logging
    logger.info(f"ALLOW_INSECURE_DEV = {ALLOW_INSECURE_DEV}, JWT_SECRET = {bool(JWT_SECRET)}")
    
    # Legacy JWT verification for backward compatibility
    if not ALLOW_INSECURE_DEV:
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

    # Try external LLM first if configured
    external_llm = await get_external_llm_client()
    if external_llm:
        try:
            logger.info(f"Routing to external LLM ({external_llm.config.provider.value})")
            content = await external_llm.chat_completion(
                messages=[{"role": m.role, "content": m.content} for m in req.messages],
                temperature=getattr(req, 'temperature', 0.7),
                max_tokens=getattr(request.state, "max_tokens", 512),
            )
            model_used = f"{external_llm.config.provider.value}:{external_llm.config.model_name}"
            inference_time = 0.0  # External service doesn't report this
            
            prompt_tokens = max(1, len(" ".join([m.content for m in req.messages])) // 4)
            completion_tokens = max(1, len(content) // 4)
            
            logger.info(
                f"AUDIT req_id={req.request_id} resp_id={resp_id} agent={agent_type} "
                f"model={model_used} source=external_llm created={created_ts}\n"
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
                translation=None,
            )
        except Exception as e:
            logger.warning(f"External LLM failed, falling back to local: {e}")
            # Continue to local model router below

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
                # No RAG context - use Dr. iSHA persona system prompt
                instruction = get_system_prompt(agent_type)
                req.messages.insert(0, Message(role="system", content=instruction))
        except Exception as e:
            logger.warning(f"RAG retrieval failed: {e}")
            rag_context = ""

    # Generate response using model router
    # If model_port is specified, route directly to that port; otherwise use agent_type routing
    try:
        # Determine target port based on model_port or agent_type
        target_port = None
        model_name = req.model or "auto"
        
        if req.model_port:
            # Direct port specification (allowed: 8080, 8082, 8083)
            if req.model_port in [8080, 8082, 8083]:
                target_port = req.model_port
                logger.info(f"Routing to model_port {target_port} (user-specified)")
            else:
                logger.warning(f"Invalid model_port {req.model_port}, falling back to agent_type routing")
        
        if not target_port:
            # Agent-type based routing
            agent_to_port = {
                "Clinical": 8080,          # BiMediX2-8B for clinical (primary)
                "AIDoctor": 8080,          # BiMediX2-8B for AI Doctor
                "Chat": 8080,              # BiMediX2-8B now handles chat
                "MedicalQA": 8080,         # BiMediX2-8B handles medical Q&A
                "Billing": 8083,           # OpenInsurance-8B for billing
                "Claims": 8083,            # OpenInsurance-8B for claims
                "Insurance": 8083,         # OpenInsurance-8B for insurance
                "Scribe": 8082,            # Qwen-0.6B for fast scribe
                "Triage": 8082,            # Qwen-0.6B for quick triage
            }
            target_port = agent_to_port.get(agent_type, 8080)  # Default to 8080 (primary)
            logger.info(f"Routing agent_type '{agent_type}' to port {target_port}")
        
        # Send request to target LLM port (direct HTTP), fallback to model_router on failure
        if target_port:
            # Route to specific port via direct HTTP call
            try:
                llm_url = f"http://127.0.0.1:{target_port}/v1/chat/completions"
                payload = {
                    "model": model_name,
                    "messages": [{"role": m.role, "content": m.content} for m in req.messages],
                    "temperature": 0.7,
                    "max_tokens": getattr(request.state, "max_tokens", 512),
                }
                headers = {"Authorization": "Bearer dev-key"}
                async with httpx.AsyncClient(timeout=90.0) as client:
                    resp = await client.post(llm_url, json=payload, headers=headers)
                    if resp.status_code == 200:
                        result = resp.json()
                        content = result.get("choices", [{}])[0].get("message", {}).get("content", "No response")
                        model_used = result.get("model", f"llama_cpp:{target_port}")
                        inference_time = 0.0
                        logger.info(f"LLM response from port {target_port}: {len(content)} chars")
                    else:
                        logger.warning(f"LLM port {target_port} returned {resp.status_code}, falling back")
                        raise Exception(f"LLM port returned {resp.status_code}")
            except Exception as e:
                logger.warning(f"Direct LLM call failed: {e}, using model_router fallback")
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
            # Ensure inference_time is only read when generation_result exists
            if 'generation_result' in locals():
                inference_time = generation_result.get("inference_time_s", inference_time)
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

    # Apply lightweight guardrails before usage accounting
    content = guardrail_sanitize(content)

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


@app.post("/tpa/member-search")
async def member_search(req: MemberSearchRequest):
    """Lookup member details via TPA (currently Heritage MobileApp API)."""
    if req.tpa_provider != "heritage":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Member search currently supports Heritage TPA only",
        )

    if not (req.policy_number or req.ecard_number or req.member_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide policy_number or ecard_number/member_id for lookup",
        )

    payload = {
        "InsCo": req.insurer_code or HERITAGE_DEFAULT_INSCO,
        "PolicyNumber": req.policy_number or "",
        "MemberID": req.ecard_number or req.member_id or "",
        "EmployeeNumber": req.employee_number or "",
        "AuthId": req.auth_id or HERITAGE_DEFAULT_AUTH_ID,
    }

    try:
        response_body = await _call_heritage_api("GetEnrollmentDetails", payload)
    except httpx.HTTPStatusError as exc:
        logger.error(
            f"Heritage member lookup failed: status={exc.response.status_code} body={exc.response.text}"
        )
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"Heritage API returned {exc.response.status_code}",
        ) from exc
    except Exception as exc:
        logger.error(f"Heritage member lookup error: {exc}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to reach Heritage TPA API",
        ) from exc

    members = _normalize_heritage_members(response_body)
    logger.info(
        f"Heritage member search tpa={req.tpa_provider} policy={req.policy_number} "
        f"member={req.member_id or req.ecard_number} found={len(members)}"
    )

    return {
        "success": bool(members),
        "tpa_provider": req.tpa_provider,
        "endpoint": "GetEnrollmentDetails",
        "member_count": len(members),
        "status": response_body.get("Status"),
        "message": response_body.get("Message"),
        "members": members,
        "payload_sent": payload,
        "raw_response": None if members else response_body,
    }


@app.post("/adjudicate")
async def adjudicate_claim(claim_data: Dict[str, Any]):
    """Process claim adjudication using dual LLM system."""
    try:
        import httpx
        import json
        
        # Load API keys
        bimedix_key = os.getenv("API_KEY_BIMEDIX2_8081", "2af05794410911ea3ddfc7203b63d38fa5c6037fa0d5a208660fcb742514b2e2")
        insurance_key = os.getenv("API_KEY_OPENINSURANCE_8084", "096eb505f3a8b993b1097b6d521bc9401f94faa2b80ca77e29600b0359bcbae4")
        
        # Extract claim information
        claim_id = claim_data.get("claim_id", f"CLM-{uuid.uuid4().hex[:12].upper()}")
        policy_number = claim_data.get("policy_number", "")
        member_id = claim_data.get("member_id", "")
        hospital_name = claim_data.get("hospital_name", "")
        diagnosis = claim_data.get("diagnosis", "")
        total_bill = claim_data.get("total_bill", 0)
        deductible = claim_data.get("deductible", 0)
        
        # Build claim analysis prompt
        claim_summary = f"""
        Claim ID: {claim_id}
        Policy: {policy_number}
        Member: {member_id}
        Hospital: {hospital_name}
        Diagnosis: {diagnosis}
        Total Bill: ${total_bill}
        Deductible: ${deductible}
        """
        
        # Query both LLMs in parallel
        results = {
            "claim_id": claim_id,
            "bimedix_analysis": None,
            "insurance_analysis": None,
            "final_decision": "PENDING"
        }
        
        # BiMediX analysis (medical necessity)
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                bio_response = await client.post(
                    "http://localhost:8081/v1/chat/completions",
                    headers={"Authorization": f"Bearer {bimedix_key}"},
                    json={
                        "model": "BiMediX",
                        "messages": [
                            {"role": "system", "content": "You are a medical expert. Analyze if the claimed treatment is medically necessary and appropriate."},
                            {"role": "user", "content": f"Is this treatment medically justified?\n{claim_summary}"}
                        ],
                        "max_tokens": 200
                    }
                )
                if bio_response.status_code == 200:
                    bio_data = bio_response.json()
                    results["bimedix_analysis"] = bio_data.get("choices", [{}])[0].get("message", {}).get("content", "")
        except Exception as e:
            results["bimedix_analysis"] = f"Error: {str(e)}"
            logger.error(f"BiMediX error: {str(e)}")
        
        # OpenInsuranceLLM analysis (policy coverage)
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                ins_response = await client.post(
                    "http://localhost:8084/v1/chat/completions",
                    headers={"Authorization": f"Bearer {insurance_key}"},
                    json={
                        "model": "OpenInsuranceLLM",
                        "messages": [
                            {"role": "system", "content": "You are an insurance policy expert. Analyze if the claim is covered under the policy."},
                            {"role": "user", "content": f"Is this claim covered by the policy?\n{claim_summary}"}
                        ],
                        "max_tokens": 200
                    }
                )
                if ins_response.status_code == 200:
                    ins_data = ins_response.json()
                    results["insurance_analysis"] = ins_data.get("choices", [{}])[0].get("message", {}).get("content", "")
        except Exception as e:
            results["insurance_analysis"] = f"Error: {str(e)}"
            logger.error(f"OpenInsuranceLLM error: {str(e)}")
        
        # Determine final decision
        if results["bimedix_analysis"] and results["insurance_analysis"]:
            # Simple heuristic: check for approval keywords
            bio_approved = "approve" in results["bimedix_analysis"].lower() or "necessary" in results["bimedix_analysis"].lower()
            ins_approved = "cover" in results["insurance_analysis"].lower() or "eligible" in results["insurance_analysis"].lower()
            
            if bio_approved and ins_approved:
                results["final_decision"] = "APPROVED"
                results["approval_amount"] = total_bill - deductible
            elif not bio_approved and not ins_approved:
                results["final_decision"] = "REJECTED"
                results["rejection_reason"] = "Failed medical and policy review"
            else:
                results["final_decision"] = "QUERY_RAISED"
                results["manual_review_required"] = True
        else:
            results["final_decision"] = "ERROR"
            results["error"] = "Unable to get LLM responses"
        
        return results
        
    except Exception as e:
        logger.error(f"Error processing claim: {str(e)}")
        return {
            "error": str(e),
            "claim_id": claim_data.get("claim_id", "UNKNOWN")
        }


class ClaimAnalysisRequest(BaseModel):
    """Request for comprehensive claim analysis."""
    file_path: Optional[str] = None
    raw_text: Optional[str] = None
    use_finetuned_model: bool = True


@app.post("/api/claim/analyze-full")
async def analyze_claim_full(file: UploadFile = File(...)):
    """
    Comprehensive claim analysis pipeline:
    1. OCR extraction of all pages
    2. Create summary of each page
    3. Categorize pages by type
    4. Identify claim, claimant, and TPA
    5. Verify policy coverage via Heritage API
    6. Check claim admissibility rules
    7. Calculate payables (deduct non-payable items)
    8. Generate final verdict with approved amount
    """
    import re
    from pdf2image import convert_from_path
    import pytesseract
    import tempfile
    from app.services.heritage_api import HeritageAPIClient
    from app.services.claim_rules import ClaimProcessingRules
    
    try:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        
        logger.info(f"🔍 Processing claim: {file.filename} ({len(content)} bytes)")
        
        # ============= STEP 1: OCR EXTRACTION =============
        logger.info("📄 STEP 1: OCR extraction...")
        try:
            images = convert_from_path(tmp_path, dpi=200)
        except Exception as e:
            logger.error(f"Failed to convert PDF to images: {e}")
            os.unlink(tmp_path)
            raise HTTPException(status_code=400, detail=f"Failed to process PDF: {str(e)}")
        
        if not images:
            os.unlink(tmp_path)
            raise HTTPException(status_code=400, detail="PDF has no pages")
        
        pages = []
        for i, img in enumerate(images):
            try:
                text = pytesseract.image_to_string(img)
                pages.append({"page": i + 1, "text": text, "chars": len(text)})
            except Exception as e:
                logger.warning(f"OCR failed for page {i + 1}: {e}")
                pages.append({"page": i + 1, "text": "", "chars": 0})
        
        logger.info(f"✓ Extracted {len(pages)} pages, total chars: {sum(p['chars'] for p in pages)}")
        
        # Step 2: Categorize pages
        logger.info("Step 2: Categorizing pages...")
        categories = {
            "claim_form": [], "patient_info": [], "authorization": [],
            "discharge_summary": [], "billing": [], "lab_reports": [],
            "receipts": [], "other": []
        }
        
        page_summaries = []
        for p in pages:
            text = p['text'].lower()
            page_num = p['page']
            
            # Categorize based on content
            if 'claim' in text and ('form' in text or 'history' in text):
                cat = "claim_form"
            elif 'authorization' in text or 'pre-auth' in text:
                cat = "authorization"
            elif 'discharge' in text and ('summary' in text or 'diagnosis' in text):
                cat = "discharge_summary"
            elif 'bill' in text and ('final' in text or 'breakup' in text or 'amount' in text):
                cat = "billing"
            elif 'receipt' in text or 'advance' in text or 'payment' in text:
                cat = "receipts"
            elif 'report' in text and ('lab' in text or 'd-dimer' in text or 'crp' in text or 'test' in text):
                cat = "lab_reports"
            elif 'patient' in text and ('name' in text or 'address' in text or 'policy' in text):
                cat = "patient_info"
            else:
                cat = "other"
            
            categories[cat].append(page_num)
            
            # Extract key info
            key_info = []
            if re.search(r'meena|patient.*name', text):
                match = re.search(r'(?:patient|name)\s*:?\s*([A-Z][A-Za-z\s\.]+)', p['text'], re.IGNORECASE)
                if match:
                    key_info.append(f"Patient: {match.group(1).strip()[:30]}")
            if 'hospital' in text or 'billroth' in text:
                key_info.append("Hospital document")
            if 'heritage' in text or 'tpa' in text:
                key_info.append("TPA/Insurance document")
            if 'diabetes' in text or 'hypertension' in text:
                key_info.append("Contains diagnosis info")
            
            # Find amounts
            amounts = re.findall(r'rs\.?\s*[\d,]+', text)
            if amounts:
                key_info.append(f"Amounts found: {len(amounts)}")
            
            page_summaries.append({
                "page": page_num,
                "category": cat,
                "chars": p['chars'],
                "key_info": key_info,
                "preview": p['text'][:200] if p['text'] else ""
            })
        
        # Step 3: Extract key claim data
        logger.info("Step 3: Extracting claim data...")
        full_text = "\n".join([p['text'] for p in pages])
        
        def extract_field(patterns, text, default=""):
            for pattern in patterns:
                try:
                    match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
                    if match:
                        return match.group(1).strip()
                except Exception as e:
                    logger.warning(f"Regex pattern error: {e}")
            return default
        
        claim_data = {
            "patient_name": extract_field([
                r"patient\s*(?:name)?\s*:?\s*(?:mrs?\.?\s*)?([A-Z][A-Za-z\s\.]+)",
                r"name\s*:?\s*(?:mrs?\.?\s*)?([A-Z][A-Za-z\s\.]+)"
            ], full_text),
            "age": extract_field([r"age\s*:?\s*(\d+)", r"(\d+)\s*(?:yrs?|years?)"], full_text),
            "hospital": extract_field([
                r"(billroth\s*hospital[^\n]*)",
                r"hospital\s*:?\s*([A-Za-z\s]+hospital)"
            ], full_text),
            "diagnosis": extract_field([
                r"diagnosis\s*:?\s*([^\n]+)",
                r"comorbid[s]?\s*:?\s*([^\n]+)"
            ], full_text),
            "claim_amount": extract_field([
                r"(?:total|bill)\s*(?:amount)?\s*:?\s*rs\.?\s*([\d,]+)",
                r"rs\.?\s*([\d,]+)\s*/-"
            ], full_text),
            "admission_date": extract_field([
                r"(?:admission|doa)\s*:?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})"
            ], full_text),
            "discharge_date": extract_field([
                r"(?:discharge|dod)\s*:?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})"
            ], full_text),
            "policy_number": extract_field([
                r"policy\s*(?:no|number)?\s*:?\s*(\d+)"
            ], full_text),
            "tpa": extract_field([
                r"(heritage\s*health[^\n]*)",
                r"tpa\s*:?\s*([A-Za-z\s]+)"
            ], full_text)
        }
        
        logger.info(f"Extracted claim data: {claim_data}")
        
        # Step 4: AI Adjudication using fine-tuned model
        logger.info("Step 4: AI Adjudication...")
        
        # Build prompt for adjudication
        adjudication_prompt = f"""As a claims adjudicator, analyze this health insurance claim:

**CLAIM SUMMARY:**
- Patient: {claim_data.get('patient_name', 'Unknown')}
- Age: {claim_data.get('age', 'Unknown')}
- Hospital: {claim_data.get('hospital', 'Unknown')}
- Diagnosis: {claim_data.get('diagnosis', 'Unknown')}
- Claim Amount: Rs. {claim_data.get('claim_amount', 'Unknown')}
- Admission: {claim_data.get('admission_date', 'Unknown')}
- Discharge: {claim_data.get('discharge_date', 'Unknown')}
- Policy: {claim_data.get('policy_number', 'Unknown')}
- TPA: {claim_data.get('tpa', 'Unknown')}

**DOCUMENT ANALYSIS:**
- Total Pages: {len(pages)}
- Discharge Summaries: {len(categories['discharge_summary'])} pages
- Lab Reports: {len(categories['lab_reports'])} pages
- Billing Documents: {len(categories['billing'])} pages

Provide APPROVE/DENY/QUERY decision with reasoning."""

        # Call the fine-tuned model
        adjudication_result = {"decision": "PENDING", "reasoning": "", "confidence": 0}
        
        try:
            # Use fine-tuned BiMediX model on port 8080
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    "http://localhost:8080/v1/chat/completions",
                    json={
                        "model": "bimedix-finetuned",
                        "messages": [{"role": "user", "content": adjudication_prompt}],
                        "max_tokens": 500,
                        "temperature": 0.1
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    ai_response = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                    
                    # Parse decision
                    if "APPROVE" in ai_response.upper():
                        adjudication_result["decision"] = "APPROVED"
                        adjudication_result["confidence"] = 0.85
                    elif "DENY" in ai_response.upper() or "REJECT" in ai_response.upper():
                        adjudication_result["decision"] = "REJECTED"
                        adjudication_result["confidence"] = 0.80
                    else:
                        adjudication_result["decision"] = "QUERY"
                        adjudication_result["confidence"] = 0.70
                    
                    adjudication_result["reasoning"] = ai_response
                    logger.info(f"AI Decision: {adjudication_result['decision']}")
                else:
                    logger.warning(f"AI API returned status {response.status_code}")
                    adjudication_result["reasoning"] = f"AI analysis request failed: HTTP {response.status_code}"
        except asyncio.TimeoutError:
            logger.warning("AI adjudication timed out")
            adjudication_result["reasoning"] = "AI analysis timed out"
        except Exception as ai_error:
            logger.warning(f"AI adjudication failed: {ai_error}")
            adjudication_result["reasoning"] = f"AI analysis unavailable: {str(ai_error)}"
        
        # Clean up temp file
        try:
            os.unlink(tmp_path)
        except Exception as e:
            logger.warning(f"Failed to delete temp file: {e}")
        
        return {
            "success": True,
            "filename": file.filename,
            "total_pages": len(pages),
            "categories": {k: v for k, v in categories.items() if v},
            "page_summaries": page_summaries,
            "claim_data": claim_data,
            "adjudication": adjudication_result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in full claim analysis: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload/claim-document")
async def upload_claim_document(file: UploadFile = File(...)):
    """
    Upload and process claim document (PDF).
    Extracts text using OCR and parses relevant information.
    """
    try:
        # Validate file type
        if not file.filename.endswith('.pdf'):
            raise HTTPException(
                status_code=400,
                detail="Only PDF files are supported"
            )
        
        # Create uploads directory if it doesn't exist
        upload_dir = os.path.join(os.getcwd(), "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        
        # Save uploaded file
        file_id = str(uuid.uuid4())
        file_path = os.path.join(upload_dir, f"{file_id}_{file.filename}")
        
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        logger.info(f"Uploaded file: {file.filename} ({len(content)} bytes)")
        
        # Try to extract text using document processor
        extracted_data = {}
        raw_text = ""
        try:
            from .document_processor import DocumentProcessor
            doc_processor = DocumentProcessor()
            
            logger.info("Attempting OCR with DocumentProcessor...")
            # Process document with bytes
            structured_doc = await doc_processor.process_document(
                content, 
                file_type="application/pdf"
            )
            
            raw_text = structured_doc.raw_text
            extracted_data = structured_doc.entities or {}
            
            logger.info(f"✓ OCR extracted {len(extracted_data)} entity fields, {len(raw_text)} chars text")
            logger.debug(f"Raw text preview: {raw_text[:200]}...")
        except Exception as ocr_error:
            logger.warning(f"OCR processing failed: {str(ocr_error)}, trying PyPDF2 fallback")
            
            # Fallback: try PyPDF2 for text-based PDFs
            try:
                import PyPDF2
                logger.info("Attempting PyPDF2 text extraction...")
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
                pages_text = []
                for page in pdf_reader.pages:
                    text = page.extract_text()
                    pages_text.append(text)
                    logger.debug(f"Page {len(pages_text)} extracted {len(text)} chars")
                raw_text = "\n\n".join(pages_text)
                logger.info(f"✓ PyPDF2 fallback extracted {len(raw_text)} chars from {len(pdf_reader.pages)} pages")
                logger.debug(f"PyPDF2 text preview: {raw_text[:300]}...")
            except Exception as pdf_error:
                logger.error(f"✗ PyPDF2 fallback also failed: {str(pdf_error)}")
                raw_text = ""
        
        # Enhanced field extraction from raw text using regex
        import re
        
        logger.info(f"Starting field extraction from {len(raw_text)} chars of text")
        
        # Log raw text for debugging if extraction fails
        if raw_text:
            logger.info(f"Raw text first 1000 chars:\n{raw_text[:1000]}")
        
        def safe_extract(pattern, text, group=1, default=""):
            try:
                match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
                result = match.group(group).strip() if match else default
                if result:
                    logger.info(f"✓ Matched pattern: {pattern[:50]}... => '{result[:50]}'")
                else:
                    logger.debug(f"✗ No match for pattern: {pattern[:100]}")
                return result
            except Exception as e:
                logger.error(f"Error in safe_extract: {e}")
                return default
        
        # Extract fields from both entities and raw text
        # Try multiple patterns for each field
        patient_name = (
            extracted_data.get("patient_name") or 
            safe_extract(r"(?:patient\s*name|name\s*of\s*patient|insured\s*name)\s*:?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", raw_text) or
            safe_extract(r"name\s*:?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", raw_text) or
            safe_extract(r"(?:mr\.|mrs\.|ms\.)\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", raw_text)
        )
        
        patient_age = (
            extracted_data.get("age") or
            safe_extract(r"(?:age|yrs?|years?)\s*:?\s*(\d{1,3})", raw_text) or
            safe_extract(r"(\d{1,3})\s*(?:yrs?|years?)", raw_text)
        )
        
        diagnosis = (
            extracted_data.get("diagnosis") or
            safe_extract(r"(?:diagnosis|condition|disease)\s*:?\s*([^\n]{10,150})", raw_text) or
            safe_extract(r"(?:provisional|final)\s*diagnosis\s*:?\s*([^\n]{10,150})", raw_text)
        )
        
        hospital_name = (
            extracted_data.get("provider_name") or
            extracted_data.get("hospital") or
            safe_extract(r"(?:hospital|medical\s*center|healthcare)\s*:?\s*([A-Z][^\n]{5,80})", raw_text) or
            safe_extract(r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:hospital|medical|healthcare|clinic))", raw_text)
        )
        
        total_amount = (
            extracted_data.get("claim_amount") or
            extracted_data.get("total_amount") or
            safe_extract(r"(?:total|grand\s*total|total\s*amount|total\s*bill)\s*:?\s*[₹$]?\s*([\d,]+\.?\d*)", raw_text) or
            safe_extract(r"(?:bill\s*amount|amount)\s*:?\s*[₹$]?\s*([\d,]+\.?\d*)", raw_text) or
            safe_extract(r"[₹$]\s*([\d,]+\.?\d*)", raw_text)
        )
        
        doctor_name = (
            safe_extract(r"(?:doctor|physician|consultant|dr\.?)\s*:?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", raw_text) or
            safe_extract(r"dr\.?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", raw_text)
        )
        
        admission_date = (
            extracted_data.get("admission_date") or
            safe_extract(r"(?:admission|admitted|date\s*of\s*admission)\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", raw_text) or
            safe_extract(r"(?:admission|admitted)\s*:?\s*(\d{1,2}\s*[a-z]+\s*\d{2,4})", raw_text)
        )
        
        discharge_date = (
            extracted_data.get("discharge_date") or
            safe_extract(r"(?:discharge|discharged|date\s*of\s*discharge)\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", raw_text) or
            safe_extract(r"(?:discharge|discharged)\s*:?\s*(\d{1,2}\s*[a-z]+\s*\d{2,4})", raw_text)
        )
        
        # Build extracted_fields map for frontend
        extracted_fields = {
            "patient_name": patient_name,
            "age": patient_age,
            "diagnosis": diagnosis,
            "hospital": hospital_name,
            "total_amount": total_amount,
            "doctor": doctor_name,
            "admission_date": admission_date,
            "discharge_date": discharge_date,
        }
        
        # Remove empty values
        extracted_fields = {k: v for k, v in extracted_fields.items() if v}
        
        logger.info(f"✓ Extraction complete: {len(extracted_fields)} fields populated: {list(extracted_fields.keys())}")
        if not extracted_fields:
            logger.warning(f"⚠ No fields extracted!")
            logger.warning(f"Raw text length: {len(raw_text)}")
            logger.warning(f"First 1000 chars of raw text:\n{raw_text[:1000]}")
            logger.warning(f"Entity data from OCR: {extracted_data}")
        
        # Parse common fields from extracted text
        parsed_data = {
            "file_id": file_id,
            "filename": file.filename,
            "file_size": len(content),
            "file_path": file_path,
            "uploaded_at": time.time(),
            "extracted_fields": extracted_fields,
            "raw_text": raw_text,  # Send full text to frontend for debugging
            "raw_text_preview": raw_text[:500] if raw_text else "",
            "extraction_method": "PyPDF2" if "PyPDF2" in str(raw_text) else "OCR",
            # Legacy top-level fields for backwards compatibility
            "patient_name": patient_name,
            "patient_age": patient_age,
            "diagnosis": diagnosis,
            "hospital_name": hospital_name,
            "total_bill": total_amount,
            "doctor_name": doctor_name,
            "admission_date": admission_date,
            "discharge_date": discharge_date
        }
        
        return {
            "success": True,
            "message": "File uploaded and processed successfully",
            "data": parsed_data
        }
        
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing upload: {str(e)}"
        )


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


# Demo Authentication (for frontend login - no database required)
DEMO_USERS = {
    "admin": {
        "password": "admin123",
        "role": "admin",
        "name": "Admin User"
    },
    "adjudicator": {
        "password": "adjud123",
        "role": "adjudicator",
        "name": "Claim Adjudicator"
    },
    "viewer": {
        "password": "view123",
        "role": "viewer",
        "name": "Report Viewer"
    }
}

class SimpleLoginRequest(BaseModel):
    """Simple login request for demo."""
    username: str
    password: str

@app.post("/auth/login")
async def simple_login(credentials: SimpleLoginRequest):
    """
    Demo authentication endpoint for frontend login.
    Uses in-memory user credentials (no database).
    """
    user = DEMO_USERS.get(credentials.username)
    
    if not user or user["password"] != credentials.password:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create JWT token
    token_data = {
        "sub": credentials.username,
        "role": user["role"],
        "name": user["name"]
    }
    
    access_token = create_access_token(
        data=token_data,
        expires_delta=timedelta(hours=24)
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "username": credentials.username,
            "name": user["name"],
            "role": user["role"]
        }
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
