"""
vLLM Engine Configuration
Configures vLLM for high-performance inference on RTX 3090 with BioMistral and others.
"""
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass
from loguru import logger


@dataclass
class vLLMEngineConfig:
    """Configuration for a single vLLM engine instance."""
    model_name: str
    model_path: str
    tensor_parallel_size: int = 1
    pipeline_parallel_size: int = 1
    gpu_memory_utilization: float = 0.85
    max_model_len: Optional[int] = None
    enable_lora: bool = False
    trust_remote_code: bool = True
    dtype: str = "auto"  # auto, float16, float32, bfloat16
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to vLLM engine kwargs."""
        return {
            "model": self.model_path,
            "tensor_parallel_size": self.tensor_parallel_size,
            "pipeline_parallel_size": self.pipeline_parallel_size,
            "gpu_memory_utilization": self.gpu_memory_utilization,
            "max_model_len": self.max_model_len,
            "enable_lora": self.enable_lora,
            "trust_remote_code": self.trust_remote_code,
            "dtype": self.dtype,
        }


class vLLMEngineRegistry:
    """Registry of vLLM engines for models per RTX3090 blueprint."""
    
    MODEL_BASE = os.getenv("MODEL_DIR", "/home/dgs/N3090/services/inference-node/models")
    
    ENGINES = {
        # Primary: Medical Q&A / MedicalQA Agent
        "bimedix2-fp16": vLLMEngineConfig(
            model_name="BiMediX2-8B FP16 (Medical Q&A + multimodal)",
            model_path=os.path.join(MODEL_BASE, "BiMediX2-8B-fp16"),
            tensor_parallel_size=1,
            gpu_memory_utilization=0.85,
            max_model_len=8192,
            dtype="float16",  # FP16 for 8B medical + multimodal
        ),
        # Claims Parsing & Adjudication
        "mixtral-8x7b-4bit": vLLMEngineConfig(
            model_name="Mixtral-8x7B 4-bit (Claims processing)",
            model_path=os.path.join(MODEL_BASE, "mixtral-8x7b-4bit"),
            tensor_parallel_size=1,
            gpu_memory_utilization=0.80,
            max_model_len=8192,
            dtype="int4",
        ),
        # Documentation & Coverage Adjudication
        "qwen2.5-14b-4bit": vLLMEngineConfig(
            model_name="Qwen2.5-14B 4-bit (Documentation/Coverage)",
            model_path=os.path.join(MODEL_BASE, "qwen2.5-14b-4bit"),
            tensor_parallel_size=1,
            gpu_memory_utilization=0.80,
            max_model_len=8192,
            dtype="int4",
        ),
        # Patient Triage Chat (lightweight)
        "chatdoctor-7b-fp16": vLLMEngineConfig(
            model_name="ChatDoctor-7B FP16 (Patient chat/triage)",
            model_path=os.path.join(MODEL_BASE, "chatdoctor-7b-fp16"),
            tensor_parallel_size=1,
            gpu_memory_utilization=0.70,
            max_model_len=4096,
            dtype="float16",  # Lighter for concurrent chat sessions
        ),
    }
    
    @classmethod
    def get_engine_config(cls, model_key: str) -> Optional[vLLMEngineConfig]:
        """Get vLLM engine config for a model key."""
        return cls.ENGINES.get(model_key)
    
    @classmethod
    def list_engines(cls) -> Dict[str, str]:
        """List available vLLM engines and their statuses."""
        result = {}
        for key, config in cls.ENGINES.items():
            path = config.model_path
            exists = "✓ ready" if os.path.isdir(path) else "✗ downloading"
            result[key] = f"{config.model_name} ({exists})"
        return result


class vLLMEngineManager:
    """Manages vLLM engine lifecycle (start/stop/health check)."""
    
    def __init__(self):
        self.engines: Dict[str, Any] = {}
        self.registry = vLLMEngineRegistry()
    
    def initialize_engine(self, model_key: str) -> bool:
        """
        Initialize a vLLM engine for the given model key.
        
        In production, this would:
        1. Check model path exists
        2. Load model into vLLM
        3. Warm up with sample tokens
        4. Register health check
        
        For now, returns True if model path exists.
        """
        config = self.registry.get_engine_config(model_key)
        if not config:
            logger.error(f"No vLLM config for model: {model_key}")
            return False
        
        if not os.path.isdir(config.model_path):
            logger.warning(f"Model path not found: {config.model_path} (still downloading?)")
            return False
        
        logger.info(f"vLLM engine ready: {model_key} → {config.model_path}")
        # In production:
        # from vllm import LLM
        # self.engines[model_key] = LLM(**config.to_dict())
        self.engines[model_key] = {"status": "ready", "config": config}
        return True
    
    def get_engine(self, model_key: str) -> Optional[Any]:
        """Get initialized engine or None."""
        return self.engines.get(model_key)
    
    def list_engines(self) -> Dict[str, str]:
        """List all available engines."""
        return self.registry.list_engines()
    
    def health_check(self, model_key: str) -> bool:
        """Check if engine is healthy and responsive."""
        engine = self.get_engine(model_key)
        if not engine:
            return False
        # In production, run a quick inference test
        return engine.get("status") == "ready"
