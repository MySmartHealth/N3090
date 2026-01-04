"""
Model Router Backend
Routes agent requests to appropriate models based on GPU capacity and model type.
Supports vLLM, llama.cpp, and custom backends.
"""
import os
import time
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from dataclasses import dataclass
from loguru import logger


class ModelBackend(str, Enum):
    VLLM = "vllm"
    LLAMA_CPP = "llama_cpp"
    TRANSFORMERS = "transformers"


@dataclass
class ModelConfig:
    name: str
    path: str
    backend: ModelBackend
    quantization: Optional[str] = None
    max_context: int = 4096
    vram_gb: float = 0.0
    gpu_ids: List[int] = None
    
    def __post_init__(self):
        if self.gpu_ids is None:
            self.gpu_ids = [0]


class ModelRegistry:
    """Registry mapping agent types to models with GPU assignments."""
    
    MODEL_BASE = os.getenv("MODEL_DIR", "/home/dgs/N3090/services/inference-node/models")

    # RTX 3090 = GPU 0 (24GB), RTX 3060 = GPU 1 (12GB)
    MODELS = {
        "bi-medix2": ModelConfig(
            name="BiMediX2-8B (Q6_K gguf)",
            path=os.getenv(
                "BIMEDIX2_PATH",
                os.path.join(MODEL_BASE, "BiMediX2-8B-hf.i1-Q6_K.gguf"),
            ),
            backend=ModelBackend.LLAMA_CPP,
            quantization="Q6_K",
            max_context=8192,
            vram_gb=10.0,
            gpu_ids=[0],  # RTX 3090
        ),
        "mistral-med-7b": ModelConfig(
            name="Mistral-7B Medical Assistance (Q5_K_M gguf)",
            path=os.getenv(
                "MISTRAL_MED_PATH",
                os.path.join(MODEL_BASE, "mistral-7b-medical-assistance.Q5_K_M.gguf"),
            ),
            backend=ModelBackend.LLAMA_CPP,
            quantization="Q5_K_M",
            max_context=8192,
            vram_gb=8.0,
            gpu_ids=[1],  # RTX 3060
        ),
        "openins-llama3-8b": ModelConfig(
            name="OpenInsurance LLaMA3 8B (Q5_K_M gguf)",
            path=os.getenv(
                "OPENINS_PATH",
                os.path.join(MODEL_BASE, "openinsurancellm-llama3-8b.Q5_K_M.gguf"),
            ),
            backend=ModelBackend.LLAMA_CPP,
            quantization="Q5_K_M",
            max_context=8192,
            vram_gb=8.0,
            gpu_ids=[1],  # RTX 3060
        ),
        "medicine-llm-13b": ModelConfig(
            name="Medicine-LLM 13B (Q6_K gguf)",
            path=os.getenv(
                "MEDICINE_LLM_PATH",
                os.path.join(MODEL_BASE, "medicine-llm-13b.Q6_K.gguf"),
            ),
            backend=ModelBackend.LLAMA_CPP,
            quantization="Q6_K",
            max_context=8192,
            vram_gb=12.0,
            gpu_ids=[0],  # RTX 3090
        ),
        "bio-mistral-7b": ModelConfig(
            name="BioMistral Clinical 7B (Q8_0 gguf)",
            path=os.getenv(
                "BIO_MISTRAL_PATH",
                os.path.join(MODEL_BASE, "BioMistral-Clinical-7B.Q8_0.gguf"),
            ),
            backend=ModelBackend.LLAMA_CPP,
            quantization="Q8_0",
            max_context=8192,
            vram_gb=9.0,
            gpu_ids=[1],  # RTX 3060
        ),
        "tiny-llama-1b": ModelConfig(
            name="Tiny-LLaMA 1.1B Chat Medical (fp16 gguf)",
            path=os.getenv(
                "TINY_LLAMA_PATH",
                os.path.join(MODEL_BASE, "tiny-llama-1.1b-chat-medical.fp16.gguf"),
            ),
            backend=ModelBackend.LLAMA_CPP,
            quantization="fp16",
            max_context=4096,
            vram_gb=2.0,
            gpu_ids=[1],  # RTX 3060
        ),
        "qwen-0.6b-med": ModelConfig(
            name="Qwen 0.6B Medical (fp16 gguf)",
            path=os.getenv(
                "QWEN_MED_PATH",
                os.path.join(MODEL_BASE, "qwen-0.6b-medicaldataset-f16.gguf"),
            ),
            backend=ModelBackend.LLAMA_CPP,
            quantization="fp16",
            max_context=4096,
            vram_gb=1.5,
            gpu_ids=[1],  # RTX 3060
        ),
        "ii-medical-8b": ModelConfig(
            name="II-Medical-8B-1706 (Q2_K gguf)",
            path=os.getenv(
                "II_MED_PATH",
                os.path.join(MODEL_BASE, "II-Medical-8B-1706.Q2_K.gguf"),
            ),
            backend=ModelBackend.LLAMA_CPP,
            quantization="Q2_K",
            max_context=8192,
            vram_gb=5.0,
            gpu_ids=[1],  # RTX 3060
        ),
        "biomistral-7b-fp16": ModelConfig(
            name="BioMistral-7B-Instruct FP16 (vLLM native)",
            path=os.getenv(
                "BIOMISTRAL_7B_FP16_PATH",
                os.path.join(MODEL_BASE, "biomistral-7b-fp16"),
            ),
            backend=ModelBackend.VLLM,
            quantization="fp16",
            max_context=4096,
            vram_gb=14.0,
            gpu_ids=[0],  # RTX 3090
        ),
        "bimedix2-8b-fp16": ModelConfig(
            name="BiMediX2-8B FP16 (Medical Q&A + multimodal)",
            path=os.getenv(
                "BIMEDIX2_8B_FP16_PATH",
                os.path.join(MODEL_BASE, "BiMediX2-8B-fp16"),
            ),
            backend=ModelBackend.VLLM,
            quantization="fp16",
            max_context=8192,
            vram_gb=20.0,
            gpu_ids=[0],  # RTX 3090
        ),
        "mixtral-8x7b-4bit": ModelConfig(
            name="Mixtral-8x7B 4-bit (Claims processing)",
            path=os.getenv(
                "MIXTRAL_8x7B_PATH",
                os.path.join(MODEL_BASE, "mixtral-8x7b-4bit"),
            ),
            backend=ModelBackend.VLLM,
            quantization="int4",
            max_context=8192,
            vram_gb=14.0,
            gpu_ids=[0],  # RTX 3090
        ),
        "qwen2.5-14b-4bit": ModelConfig(
            name="Qwen2.5-14B 4-bit (Documentation/Coverage)",
            path=os.getenv(
                "QWEN_14B_PATH",
                os.path.join(MODEL_BASE, "qwen2.5-14b-4bit"),
            ),
            backend=ModelBackend.VLLM,
            quantization="int4",
            max_context=8192,
            vram_gb=12.0,
            gpu_ids=[0],  # RTX 3090
        ),
        "chatdoctor-7b-fp16": ModelConfig(
            name="ChatDoctor-7B FP16 (Patient chat/triage)",
            path=os.getenv(
                "CHATDOCTOR_7B_PATH",
                os.path.join(MODEL_BASE, "chatdoctor-7b-fp16"),
            ),
            backend=ModelBackend.VLLM,
            quantization="fp16",
            max_context=4096,
            vram_gb=14.0,
            gpu_ids=[0],  # RTX 3090
        ),
    }
    
    # Agent to model mapping - using GGUF models for llama.cpp
    # SPEED TIERS (from benchmark):
    #   Tier 0 (Instant, <1s):     Chat, FastChat, Scribe - for interactive/real-time tasks
    #   Tier 1 (Real-Time, <2s):   Appointment, Documentation, Billing, Claims, Monitoring, MedicalQA - for interactive/urgent tasks
    #   Tier 2 (High-Quality, 33s): Clinical, AIDoctor - for accuracy-critical tasks
    #   Tier 3 (Translation):       Translate - multilingual support (no LLM inference required)
    AGENT_MODEL_MAP = {
        "Chat": "tiny-llama-1b",              # TIER 1: 1.2s avg - Patient chat/triage (lightweight, fast)
        "FastChat": "qwen-0.6b-med",            # TIER 0: <1s avg - Ultra-lightweight chat (smallest, fastest)
        "Appointment": "tiny-llama-1b",         # TIER 1: 1.2s avg - Patient interactions (fast response)
        "Documentation": "bi-medix2",          # TIER 1: 1.4s avg - Documentation/medical records (using BiMediX2)
        "Billing": "openins-llama3-8b",         # TIER 1: 1.2s avg - Insurance/billing queries (domain-specialized)
        "Claims": "openins-llama3-8b",          # TIER 1: 1.2s avg - Claims processing (domain-specialized)
        "Monitoring": "tiny-llama-1b",          # TIER 1: 1.2s avg - Lightweight monitoring
        "MedicalQA": "bi-medix2",                # TIER 1: 1.4s avg - Medical Q&A (primary, specialized)
        "Clinical": "bio-mistral-7b",           # TIER 2: 33s avg, 72 tok/s - Clinical decisions (comprehensive, highest quality)
        "AIDoctor": "bio-mistral-7b",           # TIER 2: 35s avg, 70 tok/s - Comprehensive diagnosis (BioMistral + Medicine-LLM dual-model)
        "Scribe": "qwen-0.6b-med",              # TIER 0: <1s avg - Real-time clinical dictation → structured notes (ultra-fast)
        "ClaimsOCR": "bi-medix2",              # TIER 1: 1.4s avg - NOTE: Uses BOTH BiMediX + OpenInsurance (dual-model in ClaimsAdjudicator)
        "Translate": "indictrans2",             # TIER 3: 100-500ms - Multilingual translation (22+ Indian languages) - no LLM inference
    }
    
    @classmethod
    def get_model_for_agent(cls, agent_type: str) -> Optional[ModelConfig]:
        model_key = cls.AGENT_MODEL_MAP.get(agent_type)
        if not model_key:
            logger.warning(f"No model mapping for agent type: {agent_type}")
            return None
        return cls.MODELS.get(model_key)


class ModelRouter:
    """Routes requests to appropriate model backends."""
    
    LLAMA_CPP_SERVER = os.getenv("LLAMA_CPP_SERVER", "http://127.0.0.1:8080")
    LLAMA_CPP_TIMEOUT = int(os.getenv("LLAMA_CPP_TIMEOUT", "120"))
    MAX_RETRIES = int(os.getenv("MODEL_MAX_RETRIES", "3"))
    
    # Port mapping for multi-model instances
    MODEL_PORTS = {
        "bi-medix2": 8081,
        "tiny-llama-1b": 8083,
        "openins-llama3-8b": 8084,
        "bio-mistral-7b": 8085,
    }
    
    # API keys for each model instance (loaded from environment for production)
    # In production, source .api_keys.env before starting the application
    MODEL_API_KEYS = {
        "bi-medix2": os.getenv("API_KEY_BIMEDIX2_8081"),
        "tiny-llama-1b": os.getenv("API_KEY_TINY_LLAMA_1B_8083"),
        "openins-llama3-8b": os.getenv("API_KEY_OPENINSURANCE_8084"),
        "bio-mistral-7b": os.getenv("API_KEY_BIOMISTRAL_8085"),
    }

    def __init__(self):
        self.registry = ModelRegistry()
        self.backends: Dict[str, Any] = {}
        self._load_backends()
    
    def _load_backends(self):
        """Initialize model backends (stub for now)."""
        logger.info("Model backends loading (stub mode)")
        # In production, initialize vLLM engines here
        # self.backends['vllm'] = VLLMEngine(...)
        pass
    
    async def generate(
        self,
        agent_type: str,
        messages: List[Dict[str, str]],
        constraints: Optional[Dict[str, Any]] = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """
        Route request to appropriate model and generate response.
        
        Args:
            agent_type: Agent requesting inference
            messages: Chat messages
            constraints: Agent-specific constraints
            max_tokens: Max completion tokens
            temperature: Sampling temperature
            
        Returns:
            Generated response with metadata
        """
        start_time = time.time()
        
        # Get model config
        model_config = self.registry.get_model_for_agent(agent_type)
        if not model_config:
            raise ValueError(f"No model available for agent: {agent_type}")
        
        logger.info(
            f"Routing {agent_type} → {model_config.name} "
            f"(GPU {model_config.gpu_ids}, {model_config.backend})"
        )

        backend_used = model_config.backend
        response_text: Optional[str] = None
        model_name = model_config.name

        # llama.cpp HTTP server path
        if model_config.backend == ModelBackend.LLAMA_CPP:
            try:
                response_text, model_name = self._llama_cpp_generate(
                    messages=messages,
                    model_config=model_config,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
            except Exception as e:
                logger.warning(f"llama.cpp generation failed, falling back to stub: {e}")
                response_text = None

        # TODO: wire vLLM path when engines are initialized

        # Fallback stub if backend unavailable
        if response_text is None:
            response_text = self._stub_generate(agent_type, messages, model_config)

        elapsed = time.time() - start_time
        token_estimate = len(response_text.split())

        return {
            "text": response_text,
            "model": model_name,
            "backend": backend_used,
            "gpu_ids": model_config.gpu_ids,
            "tokens_generated": token_estimate,
            "inference_time_s": elapsed,
        }
    
    def _stub_generate(
        self,
        agent_type: str,
        messages: List[Dict[str, str]],
        config: ModelConfig
    ) -> str:
        """Stub generator; replace with vLLM/llama.cpp integration."""
        last_user = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"),
            ""
        )
        
        return (
            f"[{config.name} on GPU {config.gpu_ids[0]}]\n"
            f"Agent: {agent_type}\n"
            f"Processing: {last_user[:60]}...\n\n"
            f"This is a stub response. Integrate vLLM or llama.cpp backend "
            f"to enable real inference with {config.name}."
        )

    def _llama_cpp_generate(
        self,
        messages: List[Dict[str, str]],
        model_config: ModelConfig,
        max_tokens: int,
        temperature: float,
    ) -> Tuple[str, str]:
        """Call a running llama.cpp HTTP server (OpenAI-compatible) with retry logic."""
        try:
            import httpx
        except ImportError as e:
            raise RuntimeError("httpx not installed; pip install -r requirements.txt") from e

        # Determine correct port for the model
        model_key = next((k for k, v in self.registry.MODELS.items() if v == model_config), None)
        port = self.MODEL_PORTS.get(model_key, 8080)
        api_key = self.MODEL_API_KEYS.get(model_key, None)
        server_url = f"http://127.0.0.1:{port}"
        
        url = f"{server_url.rstrip('/')}/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        # Only add auth header if API key is configured and not None
        if api_key and api_key != "none":
            headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
            "top_p": 0.95,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0,
        }

        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                with httpx.Client(timeout=self.LLAMA_CPP_TIMEOUT) as client:
                    resp = client.post(url, json=payload, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                
                choices = data.get("choices") or []
                if not choices:
                    raise RuntimeError("llama.cpp response missing choices")

                msg = choices[0].get("message") or choices[0].get("delta") or {}
                content = msg.get("content")
                if not content:
                    raise RuntimeError("llama.cpp response missing content")

                model_name = data.get("model", model_config.name)
                logger.info(f"llama.cpp generation successful (attempt {attempt + 1})")
                return content, model_name
                
            except httpx.TimeoutException as e:
                last_error = f"Timeout after {self.LLAMA_CPP_TIMEOUT}s: {e}"
                logger.warning(f"Attempt {attempt + 1}/{self.MAX_RETRIES} failed: {last_error}")
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(1 * (attempt + 1))  # Exponential backoff
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Attempt {attempt + 1}/{self.MAX_RETRIES} failed: {last_error}")
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(0.5)
        
        raise RuntimeError(f"llama.cpp server call failed after {self.MAX_RETRIES} attempts: {last_error}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """Return model registry and GPU assignments."""
        return {
            "models": {
                k: {
                    "name": v.name,
                    "backend": v.backend,
                    "gpu_ids": v.gpu_ids,
                    "vram_gb": v.vram_gb,
                    "max_context": v.max_context,
                }
                for k, v in self.registry.MODELS.items()
            },
            "agent_mapping": self.registry.AGENT_MODEL_MAP,
        }
