"""
Multi-Model Manager for Synthetic Intelligence Agentic RAG AI
Manages multiple GGUF models running simultaneously for parallel inference
"""
import os
import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
from loguru import logger
import httpx


@dataclass
class ModelInstance:
    """Configuration for a running model instance."""
    model_key: str
    model_path: str
    port: int
    gpu_id: int
    context_size: int
    gpu_layers: int
    status: str = "stopped"  # stopped, starting, running, error
    pid: Optional[int] = None
    endpoint: Optional[str] = None


class MultiModelManager:
    """
    Manages multiple llama.cpp instances for parallel model serving.
    Enables synthetic intelligence with simultaneous multi-model inference.
    """
    
    LLAMA_SERVER_BIN = os.getenv(
        "LLAMA_SERVER_BIN",
        "/home/dgs/llama.cpp/build/bin/llama-server"
    )
    
    MODEL_BASE = os.getenv(
        "MODEL_DIR",
        "/home/dgs/N3090/services/inference-node/models"
    )
    
    # Multi-model configuration for parallel execution
    MODEL_INSTANCES = {
        # GPU 0 (RTX 3090 - 24GB) - Medical & Complex Models
        "medical_qa": ModelInstance(
            model_key="bi-medix2",
            model_path=os.path.join(MODEL_BASE, "BiMediX2-8B-hf.i1-Q6_K.gguf"),
            port=8081,
            gpu_id=0,
            context_size=8192,
            gpu_layers=99,
        ),
        "documentation": ModelInstance(
            model_key="qwen-medical",
            model_path=os.path.join(MODEL_BASE, "qwen-0.6b-medicaldataset-f16.gguf"),
            port=8082,
            gpu_id=0,
            context_size=4096,
            gpu_layers=99,
        ),
        
        # GPU 1 (RTX 3060 - 12GB) - Fast Response Models
        "chat": ModelInstance(
            model_key="tiny-llama",
            model_path=os.path.join(MODEL_BASE, "tiny-llama-1.1b-chat-medical.fp16.gguf"),
            port=8083,
            gpu_id=1,
            context_size=4096,
            gpu_layers=99,
        ),
        "insurance": ModelInstance(
            model_key="openins-llama3",
            model_path=os.path.join(MODEL_BASE, "openinsurancellm-llama3-8b.Q5_K_M.gguf"),
            port=8084,
            gpu_id=1,
            context_size=8192,
            gpu_layers=99,
        ),
        
        # GPU 0 (RTX 3090) - Clinical Specialist
        "clinical": ModelInstance(
            model_key="bio-mistral-7b",
            model_path=os.path.join(MODEL_BASE, "BioMistral-Clinical-7B.Q8_0.gguf"),
            port=8085,
            gpu_id=0,
            context_size=8192,
            gpu_layers=99,
        ),
    }
    
    # Map agents to specific model instances for parallel execution
    AGENT_TO_INSTANCE = {
        "MedicalQA": "medical_qa",
        "Documentation": "documentation",
        "Chat": "chat",
        "Appointment": "chat",
        "Billing": "insurance",
        "Claims": "insurance",
        "Monitoring": "chat",
    }
    
    def __init__(self):
        self.instances: Dict[str, ModelInstance] = {}
        self.executor = ThreadPoolExecutor(max_workers=4)
        self._load_instances()
    
    def _load_instances(self):
        """Load model instance configurations."""
        self.instances = self.MODEL_INSTANCES.copy()
        logger.info(f"Loaded {len(self.instances)} model instance configurations")
    
    async def start_instance(self, instance_name: str) -> bool:
        """
        Start a specific model instance.
        
        Args:
            instance_name: Name of the instance to start
            
        Returns:
            True if started successfully
        """
        if instance_name not in self.instances:
            logger.error(f"Unknown instance: {instance_name}")
            return False
        
        instance = self.instances[instance_name]
        
        if instance.status == "running":
            logger.info(f"Instance {instance_name} already running")
            return True
        
        if not os.path.exists(instance.model_path):
            logger.error(f"Model not found: {instance.model_path}")
            instance.status = "error"
            return False
        
        # Build command
        cmd = [
            self.LLAMA_SERVER_BIN,
            "-m", instance.model_path,
            "-c", str(instance.context_size),
            "-ngl", str(instance.gpu_layers),
            "--port", str(instance.port),
            "--host", "0.0.0.0",
            "--api-key", "",
        ]
        
        # Set GPU
        env = os.environ.copy()
        env["CUDA_VISIBLE_DEVICES"] = str(instance.gpu_id)
        env["PATH"] = "/usr/local/cuda/bin:" + env.get("PATH", "")
        env["LD_LIBRARY_PATH"] = "/usr/local/cuda/lib64:" + env.get("LD_LIBRARY_PATH", "")
        
        try:
            import subprocess
            
            # Start process in background
            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            
            instance.pid = process.pid
            instance.endpoint = f"http://127.0.0.1:{instance.port}"
            instance.status = "starting"
            
            logger.info(
                f"Started {instance_name} (PID: {instance.pid}, "
                f"Port: {instance.port}, GPU: {instance.gpu_id})"
            )
            
            # Wait for server to be ready
            await self._wait_for_instance(instance, timeout=60)
            
            return instance.status == "running"
            
        except Exception as e:
            logger.error(f"Failed to start {instance_name}: {e}")
            instance.status = "error"
            return False
    
    async def _wait_for_instance(self, instance: ModelInstance, timeout: int = 60):
        """Wait for instance to be ready."""
        start_time = asyncio.get_event_loop().time()
        
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{instance.endpoint}/health",
                        timeout=2.0
                    )
                    if response.status_code == 200:
                        instance.status = "running"
                        logger.info(f"Instance ready: {instance.endpoint}")
                        return
            except:
                pass
            
            await asyncio.sleep(1)
        
        logger.warning(f"Instance timeout: {instance.endpoint}")
        instance.status = "error"
    
    async def start_all(self):
        """Start all configured model instances for parallel execution."""
        logger.info("Starting all model instances for parallel execution...")
        
        tasks = [
            self.start_instance(name)
            for name in self.instances.keys()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        running_count = sum(1 for r in results if r is True)
        logger.info(f"Started {running_count}/{len(self.instances)} instances")
        
        return running_count > 0
    
    def get_instance_for_agent(self, agent_type: str) -> Optional[ModelInstance]:
        """Get the appropriate model instance for an agent type."""
        instance_name = self.AGENT_TO_INSTANCE.get(agent_type)
        if not instance_name:
            return None
        
        instance = self.instances.get(instance_name)
        if instance and instance.status == "running":
            return instance
        
        return None
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of all model instances."""
        return {
            "total_instances": len(self.instances),
            "running": sum(1 for i in self.instances.values() if i.status == "running"),
            "instances": {
                name: {
                    "status": inst.status,
                    "endpoint": inst.endpoint,
                    "gpu_id": inst.gpu_id,
                    "port": inst.port,
                    "model": inst.model_key,
                }
                for name, inst in self.instances.items()
            }
        }
    
    async def generate(
        self,
        agent_type: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """
        Generate response using appropriate model instance.
        Supports parallel execution across multiple models.
        """
        instance = self.get_instance_for_agent(agent_type)
        
        if not instance:
            raise RuntimeError(f"No running instance for agent: {agent_type}")
        
        payload = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{instance.endpoint}/v1/chat/completions",
                    json=payload
                )
                response.raise_for_status()
                data = response.json()
            
            return {
                "text": data["choices"][0]["message"]["content"],
                "model": instance.model_key,
                "instance": instance.endpoint,
                "gpu_id": instance.gpu_id,
            }
            
        except Exception as e:
            logger.error(f"Generation failed on {instance.endpoint}: {e}")
            raise
