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
        "medpalm2-8b": ModelConfig(
            name="MedPalm2-imitate 8B (Q6_K gguf)",
            path=os.getenv(
                "MEDPALM2_PATH",
                os.path.join(MODEL_BASE, "Llama-3.1-MedPalm2-imitate-8B-Instruct.Q6_K.gguf"),
            ),
            backend=ModelBackend.LLAMA_CPP,
            quantization="Q6_K",
            max_context=4096,
            vram_gb=7.0,
            gpu_ids=[0],  # RTX 3090
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
    # ═══════════════════════════════════════════════════════════════════════════
    # 4-MODEL TANDEM CONFIGURATION (fits in 24GB RTX 3090):
    #
    # PRIMARY TIER - BiMediX2-8B (Port 8080)
    #   - Main model for ALL medical tasks
    #   - Best quality + speed balance (~65 tok/s, ~99 tok/s peak)
    #   - VRAM: 6.9GB
    #
    # TANDEM TIER - Work alongside BiMediX2
    #   - OpenInsurance-8B (Port 8084): Insurance/Claims specialist
    #   - Qwen-0.6B (Port 8082): Lightweight quick responses, triage
    #
    # BACKUP TIER - MedPalm2-8B (Port 8081)
    #   - Fallback ONLY when BiMediX2 fails
    #   - Good quality but slower (~55 tok/s)
    #   - VRAM: 6.9GB
    # ═══════════════════════════════════════════════════════════════════════════
    
    # Primary model for fallback logic
    PRIMARY_MODEL = "bi-medix2"
    BACKUP_MODEL = "medpalm2-8b"
    
    AGENT_MODEL_MAP = {
        # ═══════════════════════════════════════════════════════════════════════
        # PRIMARY: BiMediX2-8B - All core medical tasks (Port 8080)
        # ═══════════════════════════════════════════════════════════════════════
        "Chat": "bi-medix2",
        "Scribe": "bi-medix2",
        "FastChat": "bi-medix2",
        "MedicalQA": "bi-medix2",
        "Clinical": "bi-medix2",
        "AIDoctor": "bi-medix2",
        "Research": "bi-medix2",
        "Documentation": "bi-medix2",
        "Appointment": "bi-medix2",
        "Monitoring": "bi-medix2",
        "ImageAnalysis": "bi-medix2",
        "Radiology": "bi-medix2",
        "DischargeSummary": "bi-medix2",
        "LabReport": "bi-medix2",
        "PatientHistory": "bi-medix2",
        "Diagnosis": "bi-medix2",
        "Treatment": "bi-medix2",
        "Prescription": "bi-medix2",
        
        # ═══════════════════════════════════════════════════════════════════════
        # TANDEM: OpenInsurance-8B - Insurance domain specialist (Port 8084)
        # ═══════════════════════════════════════════════════════════════════════
        "Billing": "openins-llama3-8b",
        "Claims": "openins-llama3-8b",
        "ClaimsOCR": "openins-llama3-8b",
        "Insurance": "openins-llama3-8b",
        "Coverage": "openins-llama3-8b",
        "PreAuth": "openins-llama3-8b",
        "Reimbursement": "openins-llama3-8b",
        
        # ═══════════════════════════════════════════════════════════════════════
        # TANDEM: Qwen-0.6B - Lightweight quick tasks (Port 8082)
        # ═══════════════════════════════════════════════════════════════════════
        "Triage": "qwen-0.6b-med",
        "QuickResponse": "qwen-0.6b-med",
        "Greeting": "qwen-0.6b-med",
        "SimpleQA": "qwen-0.6b-med",
        "StatusCheck": "qwen-0.6b-med",
        
        # ═══════════════════════════════════════════════════════════════════════
        # BACKUP: MedPalm2-8B - Fallback only (Port 8081)
        # ═══════════════════════════════════════════════════════════════════════
        "Backup": "medpalm2-8b",
        "Fallback": "medpalm2-8b",
        
        # ─── TRANSLATION ────────────────────────────────────────────────────────
        "Translate": "indictrans2",
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
    
    # Port mapping for 4 models - BiMediX2 PRIMARY on port 8080
    MODEL_PORTS = {
        "bi-medix2": 8080,            # PRIMARY: BiMediX2 8B (best quality + speed)
        "medpalm2-8b": 8081,          # BACKUP: MedPalm2 8B (fallback only)
        "qwen-0.6b-med": 8082,        # TANDEM: Qwen 0.6B (lightweight quick tasks)
        "openins-llama3-8b": 8084,    # TANDEM: OpenInsurance 8B (insurance domain)
    }
    
    # Fallback chain: if primary fails, try these in order
    FALLBACK_CHAIN = [
        "bi-medix2",       # Try primary first
        "medpalm2-8b",     # Backup with similar capabilities
        "qwen-0.6b-med",   # Last resort lightweight
    ]
    
    # API keys for each model instance
    MODEL_API_KEYS = {
        "bi-medix2": os.getenv("API_KEY_BIMEDIX2_8080", "dev-key"),
        "medpalm2-8b": os.getenv("API_KEY_MEDPALM2_8081", "dev-key"),
        "qwen-0.6b-med": os.getenv("API_KEY_QWEN_8082", "dev-key"),
        "openins-llama3-8b": os.getenv("API_KEY_OPENINSURANCE_8084", "dev-key"),
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
            # Default to primary model (BiMediX2) if no mapping exists
            logger.warning(f"No model mapping for {agent_type}, using PRIMARY (bi-medix2)")
            model_config = self.registry.MODELS.get("bi-medix2")
            if not model_config:
                raise ValueError(f"No model available for agent: {agent_type}")
        
        logger.info(
            f"Routing {agent_type} → {model_config.name} "
            f"(GPU {model_config.gpu_ids}, {model_config.backend})"
        )

        backend_used = model_config.backend
        response_text: Optional[str] = None
        model_name = model_config.name
        fallback_used = False

        # llama.cpp HTTP server path with fallback chain
        if model_config.backend == ModelBackend.LLAMA_CPP:
            # Try primary model first
            try:
                response_text, model_name = self._llama_cpp_generate(
                    messages=messages,
                    model_config=model_config,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
            except Exception as e:
                logger.warning(f"Primary model ({model_config.name}) failed: {e}")
                
                # Try fallback chain
                for fallback_key in self.FALLBACK_CHAIN:
                    if fallback_key == self._get_model_key(model_config):
                        continue  # Skip the model that just failed
                    
                    fallback_config = self.registry.MODELS.get(fallback_key)
                    if not fallback_config:
                        continue
                    
                    logger.info(f"Attempting fallback to {fallback_config.name}")
                    try:
                        response_text, model_name = self._llama_cpp_generate(
                            messages=messages,
                            model_config=fallback_config,
                            max_tokens=max_tokens,
                            temperature=temperature,
                        )
                        fallback_used = True
                        backend_used = fallback_config.backend
                        logger.info(f"Fallback to {fallback_config.name} successful")
                        break
                    except Exception as fallback_error:
                        logger.warning(f"Fallback {fallback_config.name} also failed: {fallback_error}")
                        continue

        # TODO: wire vLLM path when engines are initialized

        # Fallback stub if all backends unavailable
        if response_text is None:
            logger.error("All models failed, using stub response")
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
            "fallback_used": fallback_used,
        }
    
    def _get_model_key(self, model_config: ModelConfig) -> Optional[str]:
        """Get the model key from config."""
        for key, config in self.registry.MODELS.items():
            if config == model_config:
                return key
        return None
    
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
            "top_p": 0.9,                 # Tighter nucleus sampling
            "frequency_penalty": 0.3,     # Penalize repeated tokens
            "presence_penalty": 0.3,      # Encourage topic diversity
            "repeat_penalty": 1.3,        # Stronger repetition penalty
            "stop": [                     # Comprehensive stop tokens for all models
                "</s>", "<|end|>", "<|eot_id|>", "<|endoftext|>",
                "<|im_end|>",             # Qwen/ChatML format
                "<|assistant|>",          # Prevent role leakage
                "Human:", "User:",        # Prevent conversation continuation
                "\n\n\n",                 # Triple newline = stop
            ],
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
                
                # Post-process to remove repetitive content
                content = self._clean_response(content)
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
    
    def _clean_response(self, content: str) -> str:
        """
        Post-process model output to remove repetitive/garbage content.
        Some models (like MedPalm2-imitate) have training artifacts.
        """
        import re
        
        # Remove social media handles and promotional content
        patterns_to_remove = [
            r'Follow me on Twitter.*?(?=\n|$)',
            r'@\w+',                               # Twitter handles
            r'#\w+',                               # Hashtags
            r'Contact Email:.*?(?=\n|$)',
            r'Website\s*:.*?(?=\n|$)',
            r'Address\s*:.*?(?=\n|$)',
            r'Phone:.*?(?=\n|$)',
            r'Instagram\s*@.*?(?=\n|$)',
            r'DM or message me.*?(?=\n|$)',
            r'www\.\S+',                           # URLs
            r'\S+@\S+\.\S+',                       # Emails
        ]
        
        for pattern in patterns_to_remove:
            content = re.sub(pattern, '', content, flags=re.IGNORECASE)
        
        # Detect and truncate at first repetition
        lines = content.split('\n')
        seen_lines = set()
        clean_lines = []
        repeat_count = 0
        
        for line in lines:
            stripped = line.strip()
            # Skip empty lines
            if not stripped:
                clean_lines.append(line)
                continue
                
            # Check for repeating lines (allow some duplicates)
            if stripped in seen_lines:
                repeat_count += 1
                if repeat_count > 2:  # Stop after 2 repeats
                    break
            else:
                seen_lines.add(stripped)
                repeat_count = 0
                clean_lines.append(line)
        
        content = '\n'.join(clean_lines)
        
        # Remove excessive whitespace
        content = re.sub(r'\n{3,}', '\n\n', content)
        content = content.strip()
        
        # If response is still too long or empty, truncate/provide fallback
        if len(content) > 1500:
            # Find a good break point
            sentences = content[:1500].rsplit('.', 1)
            if len(sentences) > 1:
                content = sentences[0] + '.'
            else:
                content = content[:1500] + '...'
        
        if not content:
            content = "Hello! How can I assist you today?"
            
        return content
    
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
