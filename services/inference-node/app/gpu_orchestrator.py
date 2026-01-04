"""
GPU-Aware Load Balancing Orchestrator
Manages RTX 3090 (24GB) memory efficiently with smart switching between llama.cpp and vLLM
"""
import asyncio
import time
import subprocess
import json
import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger
from datetime import datetime, timedelta


class BackendType(str, Enum):
    """Available inference backends"""
    LLAMA_CPP = "llama_cpp"
    VLLM = "vllm"


@dataclass
class GPUMemoryState:
    """Current GPU memory state"""
    gpu_id: int
    total_memory_gb: float
    used_memory_gb: float
    available_memory_gb: float
    temperature_c: float
    power_draw_w: float
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def memory_utilization_percent(self) -> float:
        """GPU memory utilization percentage"""
        if self.total_memory_gb == 0:
            return 0.0
        return (self.used_memory_gb / self.total_memory_gb) * 100

    @property
    def is_thermal_throttled(self) -> bool:
        """Check if GPU is overheating"""
        return self.temperature_c > 80  # RTX 3090 throttles around 80°C


@dataclass
class ModelLoadInfo:
    """Information about a model's memory requirements and performance"""
    model_name: str
    backend: BackendType
    vram_gb: float
    port: int
    is_active: bool = False
    avg_latency_ms: float = 0.0
    queue_size: int = 0
    failure_count: int = 0
    last_used: Optional[datetime] = None

    @property
    def priority_score(self) -> float:
        """Score for prioritizing model based on perf & reliability"""
        # Lower is better
        base_score = self.avg_latency_ms + (self.failure_count * 100)
        if self.queue_size > 5:
            base_score += 50  # Penalize overloaded models
        return base_score


@dataclass
class LoadBalancingDecision:
    """Decision for routing a request"""
    model_name: str
    backend: BackendType
    port: int
    reason: str
    gpu_id: int
    estimated_duration_ms: float
    will_exceed_memory: bool = False


class GPUMonitor:
    """Real-time GPU memory and performance monitoring"""

    def __init__(self, gpu_id: int = 0, poll_interval_s: float = 2.0):
        self.gpu_id = gpu_id
        self.poll_interval = poll_interval_s
        self.memory_history: List[GPUMemoryState] = []
        self.max_history = 100
        self.is_running = False

    async def start_monitoring(self):
        """Start background GPU monitoring"""
        self.is_running = True
        while self.is_running:
            try:
                state = await self.get_current_state()
                self.memory_history.append(state)
                if len(self.memory_history) > self.max_history:
                    self.memory_history.pop(0)
            except Exception as e:
                logger.warning(f"GPU monitoring error: {e}")
            await asyncio.sleep(self.poll_interval)

    async def get_current_state(self) -> GPUMemoryState:
        """Get current GPU memory and thermal state"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_nvidia_smi_state)

    def _get_nvidia_smi_state(self) -> GPUMemoryState:
        """Query nvidia-smi for GPU state"""
        try:
            cmd = (
                "nvidia-smi "
                f"--id={self.gpu_id} "
                "--query-gpu=memory.total,memory.used,temperature.gpu,power.draw "
                "--format=csv,nounits,noheader"
            )
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
            
            if result.returncode != 0:
                logger.error(f"nvidia-smi failed: {result.stderr}")
                # Return conservative estimate
                return GPUMemoryState(
                    gpu_id=self.gpu_id,
                    total_memory_gb=24.0,
                    used_memory_gb=12.0,  # Conservative
                    available_memory_gb=12.0,
                    temperature_c=50.0,
                    power_draw_w=100.0,
                )

            parts = result.stdout.strip().split(",")
            if len(parts) >= 4:
                total_mb = float(parts[0].strip())
                used_mb = float(parts[1].strip())
                temp_c = float(parts[2].strip())
                power_w = float(parts[3].strip())

                total_gb = total_mb / 1024
                used_gb = used_mb / 1024
                available_gb = total_gb - used_gb

                return GPUMemoryState(
                    gpu_id=self.gpu_id,
                    total_memory_gb=total_gb,
                    used_memory_gb=used_gb,
                    available_memory_gb=available_gb,
                    temperature_c=temp_c,
                    power_draw_w=power_w,
                )
        except Exception as e:
            logger.error(f"Failed to get GPU state: {e}")
            # Return safe default
            return GPUMemoryState(
                gpu_id=self.gpu_id,
                total_memory_gb=24.0,
                used_memory_gb=18.0,
                available_memory_gb=6.0,
                temperature_c=75.0,
                power_draw_w=250.0,
            )

    def get_latest_state(self) -> Optional[GPUMemoryState]:
        """Get most recent GPU state"""
        return self.memory_history[-1] if self.memory_history else None

    def get_average_memory_usage_gb(self, seconds: int = 30) -> float:
        """Get average memory usage over time period"""
        cutoff = datetime.now() - timedelta(seconds=seconds)
        recent = [m for m in self.memory_history if m.timestamp > cutoff]
        if not recent:
            return 0.0
        return sum(m.used_memory_gb for m in recent) / len(recent)

    def stop_monitoring(self):
        """Stop background monitoring"""
        self.is_running = False


class SmartLoadBalancer:
    """Intelligent load balancing between llama.cpp and vLLM backends"""

    def __init__(self):
        self.gpu_monitor = GPUMonitor(gpu_id=0)
        self.models: Dict[str, ModelLoadInfo] = {}
        self.backend_config: Dict[BackendType, Dict[str, Any]] = {
            BackendType.LLAMA_CPP: {
                "base_url": "http://127.0.0.1:8080",
                "ports": [8080, 8081, 8082, 8083, 8084, 8085],
                "max_instances": 4,
                "context_memory_ratio": 0.8,  # 80% of model VRAM for context
            },
            BackendType.VLLM: {
                "base_url": "http://127.0.0.1:8000",
                "ports": [9000, 9001, 9002],
                "max_instances": 2,
                "context_memory_ratio": 0.9,  # 90% of model VRAM for context
            },
        }
        self.memory_thresholds = {
            "critical": 0.95,  # 95% = only critical requests
            "high": 0.85,      # 85% = prefer smaller models
            "normal": 0.70,    # 70% = balanced
            "low": 0.50,       # 50% = can use large models
        }

    def register_model(
        self,
        model_name: str,
        backend: BackendType,
        vram_gb: float,
        port: int,
    ):
        """Register a model for load balancing"""
        self.models[model_name] = ModelLoadInfo(
            model_name=model_name,
            backend=backend,
            vram_gb=vram_gb,
            port=port,
        )
        logger.info(f"Registered model: {model_name} ({backend}) on port {port} - {vram_gb}GB VRAM")

    async def get_memory_state(self) -> GPUMemoryState:
        """Get current GPU memory state"""
        return await self.gpu_monitor.get_current_state()

    def _get_memory_pressure_level(self, utilization: float) -> str:
        """Determine memory pressure level"""
        for level, threshold in sorted(self.memory_thresholds.items(), key=lambda x: x[1]):
            if utilization <= threshold:
                return level
        return "critical"

    def _calculate_model_fit(self, model: ModelLoadInfo, available_gb: float) -> bool:
        """Check if model can fit in available memory with overhead"""
        # Account for 1GB system overhead + 2GB buffer
        safe_available = available_gb - 3.0
        return safe_available >= model.vram_gb

    async def decide_model_and_backend(
        self,
        agent_type: str,
        preferred_model: Optional[str] = None,
        min_context_tokens: int = 2048,
        prefer_llama_cpp: bool = True,
    ) -> LoadBalancingDecision:
        """
        Make intelligent decision on which model/backend to use
        
        Args:
            agent_type: Type of agent making request
            preferred_model: Preferred model name (may fall back if memory constrained)
            min_context_tokens: Minimum context requirement
            prefer_llama_cpp: Prefer llama.cpp for lower latency if available
            
        Returns:
            LoadBalancingDecision with routing info
        """
        gpu_state = await self.get_memory_state()
        utilization = gpu_state.memory_utilization_percent
        pressure_level = self._get_memory_pressure_level(utilization)

        logger.info(
            f"Load balancing decision: agent={agent_type}, "
            f"GPU util={utilization:.1f}%, pressure={pressure_level}, "
            f"mem_avail={gpu_state.available_memory_gb:.1f}GB, "
            f"temp={gpu_state.temperature_c:.0f}°C"
        )

        # Under critical pressure, only allow smallest models
        if pressure_level == "critical":
            logger.warning(f"CRITICAL memory pressure ({utilization:.1f}%) - restricting to smallest models")
            return await self._fallback_to_smallest_model(agent_type)

        # Under high pressure, prefer memory-efficient backends
        if pressure_level == "high":
            logger.info(f"HIGH memory pressure ({utilization:.1f}%) - switching to llama.cpp (more efficient)")
            prefer_llama_cpp = True

        # Check thermal throttling
        if gpu_state.is_thermal_throttled:
            logger.warning(f"GPU thermal throttled ({gpu_state.temperature_c:.0f}°C) - reducing load")
            return await self._fallback_to_smallest_model(agent_type)

        # Try preferred model first
        if preferred_model and preferred_model in self.models:
            model = self.models[preferred_model]
            if self._calculate_model_fit(model, gpu_state.available_memory_gb):
                decision = await self._make_backend_decision(
                    model, gpu_state, prefer_llama_cpp, agent_type
                )
                decision.reason = f"Using preferred model {preferred_model}"
                return decision

        # Find best available model based on memory and performance
        candidates = self._get_candidate_models(
            gpu_state.available_memory_gb, prefer_llama_cpp, agent_type
        )

        if not candidates:
            logger.error("No models available that fit in memory!")
            raise RuntimeError("No available models within memory constraints")

        best_model = min(candidates, key=lambda m: m[1].priority_score)
        model = best_model[1]

        decision = await self._make_backend_decision(model, gpu_state, prefer_llama_cpp, agent_type)
        decision.reason = f"Selected {model.model_name} (pressure={pressure_level})"
        return decision

    async def _make_backend_decision(
        self,
        model: ModelLoadInfo,
        gpu_state: GPUMemoryState,
        prefer_llama_cpp: bool,
        agent_type: str,
    ) -> LoadBalancingDecision:
        """Decide backend for a specific model"""
        backend = model.backend

        # If model is dual-backend capable, choose based on conditions
        if model.backend == BackendType.LLAMA_CPP and prefer_llama_cpp:
            backend = BackendType.LLAMA_CPP
            reason = "llama.cpp (low latency, memory efficient)"
        elif model.backend == BackendType.VLLM and gpu_state.available_memory_gb > 10:
            backend = BackendType.VLLM
            reason = "vLLM (throughput optimized)"
        else:
            reason = f"Primary backend ({backend})"

        # Estimate processing time
        estimated_ms = self._estimate_inference_time(model, agent_type)

        return LoadBalancingDecision(
            model_name=model.model_name,
            backend=backend,
            port=model.port,
            reason=reason,
            gpu_id=0,
            estimated_duration_ms=estimated_ms,
            will_exceed_memory=not self._calculate_model_fit(model, gpu_state.available_memory_gb),
        )

    def _get_candidate_models(
        self,
        available_gb: float,
        prefer_llama_cpp: bool,
        agent_type: str,
    ) -> List[Tuple[str, ModelLoadInfo]]:
        """Get models that fit in available memory, sorted by suitability"""
        candidates = []
        for name, model in self.models.items():
            if self._calculate_model_fit(model, available_gb):
                # Prefer requested backend if possible
                if prefer_llama_cpp and model.backend == BackendType.LLAMA_CPP:
                    candidates.append((name, model))
                elif not prefer_llama_cpp and model.backend == BackendType.VLLM:
                    candidates.append((name, model))
                else:
                    candidates.append((name, model))

        return candidates

    async def _fallback_to_smallest_model(self, agent_type: str) -> LoadBalancingDecision:
        """Fall back to smallest available model"""
        smallest = min(self.models.values(), key=lambda m: m.vram_gb)
        gpu_state = await self.get_memory_state()

        return LoadBalancingDecision(
            model_name=smallest.model_name,
            backend=smallest.backend,
            port=smallest.port,
            reason=f"FALLBACK: Memory critical, using smallest model {smallest.model_name}",
            gpu_id=0,
            estimated_duration_ms=self._estimate_inference_time(smallest, agent_type),
            will_exceed_memory=not self._calculate_model_fit(smallest, gpu_state.available_memory_gb),
        )

    def _estimate_inference_time(self, model: ModelLoadInfo, agent_type: str) -> float:
        """Estimate inference time based on model history and type"""
        # Use historical latency if available
        if model.avg_latency_ms > 0:
            return model.avg_latency_ms

        # Estimate based on model size and backend
        if model.backend == BackendType.LLAMA_CPP:
            # llama.cpp estimates (tokens/sec on RTX 3090)
            base_tokens_per_sec = {
                "tiny": 200,      # <2GB models
                "small": 150,     # 2-8GB models
                "medium": 100,    # 8-15GB models
                "large": 50,      # 15GB+ models
            }
        else:  # vLLM
            base_tokens_per_sec = {
                "tiny": 300,
                "small": 250,
                "medium": 200,
                "large": 150,
            }

        # Classify model by size
        if model.vram_gb < 2:
            size_class = "tiny"
        elif model.vram_gb < 8:
            size_class = "small"
        elif model.vram_gb < 15:
            size_class = "medium"
        else:
            size_class = "large"

        # Estimate 512 token response
        tokens_per_sec = base_tokens_per_sec[size_class]
        estimated_ms = (512 / tokens_per_sec) * 1000

        return estimated_ms

    def update_model_metrics(self, model_name: str, latency_ms: float, queue_size: int):
        """Update metrics for a model after inference"""
        if model_name not in self.models:
            return

        model = self.models[model_name]
        # Exponential moving average for latency
        if model.avg_latency_ms == 0:
            model.avg_latency_ms = latency_ms
        else:
            model.avg_latency_ms = 0.7 * model.avg_latency_ms + 0.3 * latency_ms

        model.queue_size = queue_size
        model.last_used = datetime.now()

    def report_model_failure(self, model_name: str):
        """Report a failure for a model"""
        if model_name in self.models:
            self.models[model_name].failure_count += 1
            logger.warning(f"Model {model_name} failure reported (total: {self.models[model_name].failure_count})")

    async def start(self):
        """Start the load balancer"""
        await self.gpu_monitor.start_monitoring()
        logger.info("GPU Load Balancer started")

    def stop(self):
        """Stop the load balancer"""
        self.gpu_monitor.stop_monitoring()
        logger.info("GPU Load Balancer stopped")

    def get_status_summary(self) -> Dict[str, Any]:
        """Get status summary for monitoring"""
        latest_state = self.gpu_monitor.get_latest_state()
        if not latest_state:
            return {"status": "initializing"}

        return {
            "gpu": {
                "id": latest_state.gpu_id,
                "memory_used_gb": latest_state.used_memory_gb,
                "memory_total_gb": latest_state.total_memory_gb,
                "memory_available_gb": latest_state.available_memory_gb,
                "utilization_percent": latest_state.memory_utilization_percent,
                "temperature_c": latest_state.temperature_c,
                "power_draw_w": latest_state.power_draw_w,
                "is_throttled": latest_state.is_thermal_throttled,
            },
            "models": {
                name: {
                    "vram_gb": model.vram_gb,
                    "backend": model.backend,
                    "avg_latency_ms": model.avg_latency_ms,
                    "queue_size": model.queue_size,
                    "failure_count": model.failure_count,
                }
                for name, model in self.models.items()
            },
            "timestamp": latest_state.timestamp.isoformat(),
        }


# Global orchestrator instance
_load_balancer: Optional[SmartLoadBalancer] = None


def get_load_balancer() -> SmartLoadBalancer:
    """Get or create global load balancer"""
    global _load_balancer
    if _load_balancer is None:
        _load_balancer = SmartLoadBalancer()
    return _load_balancer


async def initialize_load_balancer():
    """Initialize load balancer with registered models"""
    balancer = get_load_balancer()

    # Register llama.cpp models
    balancer.register_model("tiny-llama-1b", BackendType.LLAMA_CPP, 2.3, 8080)
    balancer.register_model("bi-medix2", BackendType.LLAMA_CPP, 6.5, 8081)
    balancer.register_model("openins-llama3-8b", BackendType.LLAMA_CPP, 7.8, 8084)

    # Register vLLM models (when available)
    # balancer.register_model("biomistral-7b-fp16", BackendType.VLLM, 14.0, 9000)
    # balancer.register_model("qwen2.5-14b-4bit", BackendType.VLLM, 12.0, 9001)

    await balancer.start()
    return balancer
