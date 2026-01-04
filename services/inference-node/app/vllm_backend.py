"""
vLLM Backend Integration Example
Shows how to integrate vLLM for high-performance inference.
Enable by setting USE_VLLM=1 env var and ensuring models are downloaded.
"""
import os
from typing import Dict, List, Any, Optional
from loguru import logger


class vLLMBackend:
    """Wraps vLLM for inference (placeholder; requires vllm package)."""
    
    def __init__(self, model_path: str, max_model_len: int = 4096, dtype: str = "float16"):
        self.model_path = model_path
        self.max_model_len = max_model_len
        self.dtype = dtype
        self.engine = None
        self._load_engine()
    
    def _load_engine(self):
        """Load vLLM engine (requires 'pip install vllm')."""
        try:
            from vllm import LLM, SamplingParams
            
            logger.info(f"Loading vLLM engine for {self.model_path}...")
            self.engine = LLM(
                model=self.model_path,
                dtype=self.dtype,
                gpu_memory_utilization=0.85,
                max_model_len=self.max_model_len,
                trust_remote_code=True,
            )
            logger.info("vLLM engine ready")
        except ImportError:
            logger.warning("vLLM not installed; run 'pip install vllm'")
            self.engine = None
        except Exception as e:
            logger.error(f"Failed to load vLLM engine: {e}")
            self.engine = None
    
    def generate(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.95,
    ) -> str:
        """Generate text via vLLM."""
        if not self.engine:
            raise RuntimeError("vLLM engine not loaded")
        
        try:
            from vllm import SamplingParams
            
            # Convert OpenAI-style messages to prompt
            prompt = self._messages_to_prompt(messages)
            
            sampling_params = SamplingParams(
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
            )
            
            outputs = self.engine.generate([prompt], sampling_params)
            return outputs[0].outputs[0].text
        except Exception as e:
            logger.error(f"vLLM generation failed: {e}")
            raise
    
    def _messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        """Convert OpenAI messages to model prompt format."""
        # Simple format for Mistral-like models
        prompt = ""
        for msg in messages:
            role = msg["role"].upper()
            content = msg["content"]
            prompt += f"{role}: {content}\n"
        prompt += "ASSISTANT:"
        return prompt


def use_vllm_if_available(agent_type: str, model_path: str) -> Optional[vLLMBackend]:
    """
    Instantiate vLLM backend if:
    1. USE_VLLM=1 env var set
    2. Model path exists
    3. vllm package installed
    """
    if not os.getenv("USE_VLLM", "").lower() in {"1", "true", "yes"}:
        return None
    
    if not os.path.isdir(model_path):
        logger.warning(f"Model path not found, cannot use vLLM: {model_path}")
        return None
    
    try:
        return vLLMBackend(model_path=model_path)
    except Exception as e:
        logger.warning(f"vLLM initialization failed, falling back to llama.cpp: {e}")
        return None


# Integration example for model_router.py:
# 
# In ModelRouter.generate():
#
#   # Try vLLM first if available
#   if model_config.backend == ModelBackend.VLLM:
#       vllm_backend = use_vllm_if_available(agent_type, model_config.path)
#       if vllm_backend:
#           response_text = vllm_backend.generate(
#               messages=messages,
#               max_tokens=max_tokens,
#               temperature=temperature,
#           )
#           return {
#               "text": response_text,
#               "model": model_config.name,
#               "backend": "vllm",
#               "gpu_ids": model_config.gpu_ids,
#               "inference_time_s": elapsed,
#           }
#
#   # Fallback to stub or llama.cpp
#   response_text = self._stub_generate(agent_type, messages, model_config)
#   ...
