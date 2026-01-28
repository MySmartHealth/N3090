"""
External LLM Provider Integration
Supports OpenAI-compatible APIs (e.g., Mediqzy.com, Ollama, LM Studio, etc.)
"""

import os
import httpx
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    """Supported external LLM providers"""
    OPENAI = "openai"
    MEDIQZY = "mediqzy"
    OLLAMA = "ollama"
    CUSTOM = "custom"  # Generic OpenAI-compatible


@dataclass
class LLMConfig:
    """Configuration for external LLM"""
    provider: LLMProvider
    base_url: str
    api_key: Optional[str] = None
    model_name: str = "gpt-3.5-turbo"
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    timeout: int = 30  # seconds
    
    @classmethod
    def from_env(cls) -> Optional["LLMConfig"]:
        """Load config from environment variables"""
        if not os.getenv("EXTERNAL_LLM_ENABLED", "false").lower() == "true":
            return None
            
        provider_str = os.getenv("EXTERNAL_LLM_PROVIDER", "custom").lower()
        try:
            provider = LLMProvider(provider_str)
        except ValueError:
            logger.warning(f"Unknown LLM provider: {provider_str}, defaulting to custom")
            provider = LLMProvider.CUSTOM
        
        base_url = os.getenv("EXTERNAL_LLM_BASE_URL")
        if not base_url:
            logger.error("EXTERNAL_LLM_BASE_URL not set")
            return None
        
        return cls(
            provider=provider,
            base_url=base_url.rstrip("/"),  # Remove trailing slash
            api_key=os.getenv("EXTERNAL_LLM_API_KEY"),
            model_name=os.getenv("EXTERNAL_LLM_MODEL", "gpt-3.5-turbo"),
            temperature=float(os.getenv("EXTERNAL_LLM_TEMPERATURE", "0.7")),
            max_tokens=int(os.getenv("EXTERNAL_LLM_MAX_TOKENS", "0")) or None,
            timeout=int(os.getenv("EXTERNAL_LLM_TIMEOUT", "30")),
        )


class ExternalLLMClient:
    """Client for communicating with external LLM services"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = httpx.AsyncClient(timeout=config.timeout)
        logger.info(f"Initialized {config.provider} LLM client: {config.base_url}")
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Call external LLM for chat completion
        
        Args:
            messages: List of {"role": "user|assistant|system", "content": "..."} dicts
            temperature: Override config temperature
            max_tokens: Override config max_tokens
            
        Returns:
            Response text from the LLM
            
        Raises:
            httpx.RequestError: Network/connection error
            httpx.HTTPStatusError: API error (4xx, 5xx)
        """
        try:
            payload = {
                "model": self.config.model_name,
                "messages": messages,
                "temperature": temperature or self.config.temperature,
            }
            
            if max_tokens or self.config.max_tokens:
                payload["max_tokens"] = max_tokens or self.config.max_tokens
            
            headers = {"Content-Type": "application/json"}
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"
            
            # Endpoint follows OpenAI format: /v1/chat/completions
            url = f"{self.config.base_url}/v1/chat/completions"
            
            logger.debug(f"Calling {self.config.provider} at {url}")
            response = await self.client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            
            # Handle OpenAI-compatible response format
            if "choices" in result and len(result["choices"]) > 0:
                message = result["choices"][0].get("message", {})
                return message.get("content", "").strip()
            
            logger.error(f"Unexpected response format: {result}")
            return ""
            
        except httpx.RequestError as e:
            logger.error(f"Network error calling {self.config.provider}: {e}")
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"API error from {self.config.provider}: {e.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error calling {self.config.provider}: {e}")
            raise
    
    async def stream_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ):
        """
        Stream chat completion from external LLM
        
        Yields:
            Streamed response chunks (tokens)
        """
        try:
            payload = {
                "model": self.config.model_name,
                "messages": messages,
                "temperature": temperature or self.config.temperature,
                "stream": True,
            }
            
            if max_tokens or self.config.max_tokens:
                payload["max_tokens"] = max_tokens or self.config.max_tokens
            
            headers = {"Content-Type": "application/json"}
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"
            
            url = f"{self.config.base_url}/v1/chat/completions"
            
            logger.debug(f"Streaming from {self.config.provider} at {url}")
            async with self.client.stream("POST", url, json=payload, headers=headers) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if not line.strip() or line.startswith(":"):
                        continue
                    
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        
                        try:
                            import json
                            data = json.loads(data_str)
                            
                            if "choices" in data and len(data["choices"]) > 0:
                                delta = data["choices"][0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                        except Exception as e:
                            logger.debug(f"Error parsing stream chunk: {e}")
                            continue
                            
        except Exception as e:
            logger.error(f"Streaming error from {self.config.provider}: {e}")
            raise


# Global client instance (lazy-loaded)
_external_llm_client: Optional[ExternalLLMClient] = None


async def get_external_llm_client() -> Optional[ExternalLLMClient]:
    """Get or initialize the external LLM client (singleton pattern)"""
    global _external_llm_client
    
    if _external_llm_client is not None:
        return _external_llm_client
    
    config = LLMConfig.from_env()
    if not config:
        return None
    
    _external_llm_client = ExternalLLMClient(config)
    return _external_llm_client


async def close_external_llm_client():
    """Close the global external LLM client"""
    global _external_llm_client
    
    if _external_llm_client:
        await _external_llm_client.close()
        _external_llm_client = None
