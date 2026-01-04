"""
Agent API Key Management
Provides agent-wise authentication and key management.
"""
import secrets
from typing import Dict, Optional
from datetime import datetime
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from loguru import logger
import os

router = APIRouter(prefix="/v1/admin/agent-keys", tags=["Agent Keys"])

# Agent API keys storage (in-memory, can be moved to database)
AGENT_API_KEYS: Dict[str, Dict[str, str]] = {}

def get_admin_api_key() -> str:
    """Get admin API key from environment."""
    return os.getenv("ADMIN_API_KEY", "")

ALLOWED_AGENTS = {
    "Chat",
    "Appointment",
    "Documentation",
    "Billing",
    "Claims",
    "Monitoring",
    "MedicalQA",
    "Clinical",
}


class AgentAPIKeyRequest(BaseModel):
    """Request to create/update agent API key."""
    agent_type: str
    description: Optional[str] = None


class AgentAPIKeyResponse(BaseModel):
    """Agent API key details."""
    agent_type: str
    api_key: str
    created_at: str
    description: Optional[str] = None


def verify_admin_key(api_key: Optional[str]) -> None:
    """Verify admin API key for management operations."""
    admin_key = get_admin_api_key()
    if not admin_key:
        raise HTTPException(
            status_code=500,
            detail="ADMIN_API_KEY not configured"
        )
    if not api_key or api_key != admin_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid admin API key"
        )


def verify_agent_api_key(agent_type: str, api_key: Optional[str]) -> bool:
    """
    Verify agent-specific API key.
    
    Returns:
        True if key is valid or no key is configured for agent
        Raises HTTPException if key is configured but invalid
    """
    if agent_type in AGENT_API_KEYS:
        expected_key = AGENT_API_KEYS[agent_type]["api_key"]
        if not api_key or api_key != expected_key:
            raise HTTPException(
                status_code=401,
                detail=f"Invalid API key for agent: {agent_type}"
            )
    return True


@router.post("", response_model=AgentAPIKeyResponse)
async def create_agent_api_key(
    request: AgentAPIKeyRequest,
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key")
):
    """
    Create or update API key for a specific agent type.
    Requires admin API key.
    
    Example:
        curl -X POST http://localhost:8000/v1/admin/agent-keys \\
            -H "X-Admin-Key: your-admin-key" \\
            -H "Content-Type: application/json" \\
            -d '{"agent_type": "Claims", "description": "Insurance claims agent key"}'
    """
    verify_admin_key(x_admin_key)
    
    if request.agent_type not in ALLOWED_AGENTS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid agent type. Allowed: {', '.join(ALLOWED_AGENTS)}"
        )
    
    # Generate new API key
    api_key = f"agent-{request.agent_type.lower()}-{secrets.token_urlsafe(32)}"
    
    AGENT_API_KEYS[request.agent_type] = {
        "api_key": api_key,
        "created_at": datetime.utcnow().isoformat(),
        "description": request.description or f"API key for {request.agent_type} agent"
    }
    
    logger.info(f"Created API key for agent: {request.agent_type}")
    
    return AgentAPIKeyResponse(
        agent_type=request.agent_type,
        api_key=api_key,
        created_at=AGENT_API_KEYS[request.agent_type]["created_at"],
        description=AGENT_API_KEYS[request.agent_type]["description"]
    )


@router.get("")
async def list_agent_api_keys(
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key")
):
    """
    List all agent API keys (without showing actual keys).
    Requires admin API key.
    """
    verify_admin_key(x_admin_key)
    
    keys_list = []
    for agent_type, key_data in AGENT_API_KEYS.items():
        keys_list.append({
            "agent_type": agent_type,
            "api_key_preview": key_data["api_key"][:20] + "...",
            "created_at": key_data["created_at"],
            "description": key_data["description"]
        })
    
    return {"agent_keys": keys_list, "total": len(keys_list)}


@router.delete("/{agent_type}")
async def delete_agent_api_key(
    agent_type: str,
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key")
):
    """
    Delete API key for a specific agent type.
    Requires admin API key.
    """
    verify_admin_key(x_admin_key)
    
    if agent_type not in AGENT_API_KEYS:
        raise HTTPException(
            status_code=404,
            detail=f"No API key found for agent: {agent_type}"
        )
    
    del AGENT_API_KEYS[agent_type]
    logger.info(f"Deleted API key for agent: {agent_type}")
    
    return {"message": f"API key deleted for {agent_type}"}


@router.post("/verify")
async def verify_key(
    agent_type: str,
    api_key: str = Header(alias="X-Agent-Key")
):
    """
    Verify an agent API key.
    
    Example:
        curl -X POST http://localhost:8000/v1/admin/agent-keys/verify?agent_type=Claims \\
            -H "X-Agent-Key: agent-claims-..."
    """
    verify_agent_api_key(agent_type, api_key)
    return {
        "valid": True,
        "agent_type": agent_type,
        "message": "API key is valid"
    }
