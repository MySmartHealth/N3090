"""
Middleware components for the inference node.
Includes: rate limiting, policy enforcement, audit enrichment, error handling.
"""
import time
import hashlib
from typing import Dict, Any, Optional, Callable
from collections import defaultdict
from datetime import datetime, timedelta
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting per agent type and source IP."""
    
    def __init__(self, app, max_requests: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, list] = defaultdict(list)
    
    async def dispatch(self, request: Request, call_next):
        # Skip healthz
        if request.url.path == "/healthz":
            return await call_next(request)
        
        # Rate limit key: IP + agent type
        client_ip = request.client.host if request.client else "unknown"
        agent_type = request.headers.get("X-Agent-Type", "default")
        key = f"{client_ip}:{agent_type}"
        
        now = time.time()
        cutoff = now - self.window_seconds
        
        # Clean old entries
        self.requests[key] = [ts for ts in self.requests[key] if ts > cutoff]
        
        # Check limit
        if len(self.requests[key]) >= self.max_requests:
            logger.warning(f"Rate limit exceeded for {key}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit: {self.max_requests} requests per {self.window_seconds}s"
            )
        
        # Track request
        self.requests[key].append(now)
        
        response = await call_next(request)
        return response


class PolicyEnforcementMiddleware(BaseHTTPMiddleware):
    """Enforce agent-specific policies and constraints."""
    
    ALLOWED_AGENTS = {
        "Chat",
        "Appointment",
        "Documentation",
        "Billing",
        "Claims",
        "Monitoring",
        "MedicalQA",
        "Clinical",  # BioMistral Clinical decision support
    }
    
    # Agent-specific token limits
    AGENT_TOKEN_LIMITS = {
        "Chat": 1024,
        "Appointment": 512,
        "Documentation": 4096,
        "Billing": 2048,
        "Claims": 2048,
        "Monitoring": 1024,
        "MedicalQA": 2048,
        "Clinical": 2048,  # Clinical decision support
    }
    
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/healthz":
            return await call_next(request)
        
        if request.url.path == "/v1/chat/completions" and request.method == "POST":
            # Attach policy context to request state
            agent_type = request.headers.get("X-Agent-Type", "")
            
            if agent_type and agent_type not in self.ALLOWED_AGENTS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Agent type '{agent_type}' not allowed"
                )
            
            # Store policy limits in request state
            request.state.max_tokens = self.AGENT_TOKEN_LIMITS.get(agent_type, 1024)
            request.state.agent_type = agent_type
        
        response = await call_next(request)
        return response


class AuditEnrichmentMiddleware(BaseHTTPMiddleware):
    """Enrich requests with audit metadata."""
    
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/healthz":
            return await call_next(request)
        
        # Generate request tracking ID if not present
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = f"req-{int(time.time())}-{hashlib.sha256(str(time.time()).encode()).hexdigest()[:8]}"
        
        # Attach audit context
        request.state.request_id = request_id
        request.state.timestamp = datetime.utcnow().isoformat()
        request.state.client_ip = request.client.host if request.client else "unknown"
        
        logger.info(
            f"REQUEST {request_id} {request.method} {request.url.path} "
            f"from {request.state.client_ip}"
        )
        
        response = await call_next(request)
        
        # Add audit headers to response
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Timestamp"] = request.state.timestamp
        
        return response


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Centralized error handling and sanitization."""
    
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except HTTPException:
            # Let FastAPI handle HTTP exceptions
            raise
        except Exception as e:
            # Log full error but return sanitized response
            request_id = getattr(request.state, "request_id", "unknown")
            logger.error(f"ERROR {request_id}: {type(e).__name__}: {str(e)}")
            
            # Don't leak internal details
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error. Request logged for review."
            )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return response
