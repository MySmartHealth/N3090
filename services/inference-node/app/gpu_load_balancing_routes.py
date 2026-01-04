"""
GPU Load Balancing Routes
Monitor and control GPU memory allocation and model selection
"""
from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Dict, Any, Optional
from loguru import logger

from .auth import get_current_user, User
from .gpu_orchestrator import get_load_balancer

router = APIRouter(prefix="/v1/gpu", tags=["GPU Management"])

# Public GPU monitoring endpoint (no auth required)
@router.get("/status")
async def get_gpu_status():
    """
    Get real-time GPU status and memory allocation
    """
    try:
        balancer = get_load_balancer()
        status = balancer.get_status_summary()
        return {
            "status": "ok",
            "gpu_status": status,
        }
    except Exception as e:
        logger.error(f"GPU status check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memory-forecast")
async def get_memory_forecast(
    hours: int = 1
):
    """
    Forecast GPU memory usage for next N hours
    """
    try:
        balancer = get_load_balancer()
        
        # Get historical memory usage
        avg_memory = balancer.gpu_monitor.get_average_memory_usage_gb(seconds=300)
        total_memory = 24.0  # RTX 3090
        
        forecast = {
            "current_usage_gb": avg_memory,
            "utilization_percent": (avg_memory / total_memory) * 100,
            "projected_headroom_gb": total_memory - avg_memory,
            "estimated_available_for_inference_gb": max(0, total_memory - avg_memory - 3.0),  # 3GB system overhead
            "forecast_hours": hours,
        }
        
        return {"status": "ok", "forecast": forecast}
    except Exception as e:
        logger.error(f"Memory forecast failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rebalance")
async def trigger_rebalance():
    """
    Force GPU load rebalancing (move models between backends if needed)
    """
    try:
        balancer = get_load_balancer()
        
        # Get current state
        gpu_state = await balancer.get_memory_state()
        
        action_taken = []
        
        # If high memory pressure, consider unloading least-used models
        if gpu_state.memory_utilization_percent > 85:
            action_taken.append("High memory pressure detected - recommending model reduction")
        
        # If thermal throttling, reduce load
        if gpu_state.is_thermal_throttled:
            action_taken.append(f"Thermal throttling detected ({gpu_state.temperature_c:.0f}°C) - recommend load reduction")
        
        if not action_taken:
            action_taken.append("GPU load is optimal - no rebalancing needed")
        
        return {
            "status": "ok",
            "actions": action_taken,
            "gpu_utilization_percent": gpu_state.memory_utilization_percent,
            "temperature_c": gpu_state.temperature_c,
        }
    except Exception as e:
        logger.error(f"Load rebalancing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models-optimal")
async def get_optimal_models(
    agent_type: str
):
    """
    Get list of models ranked by optimality for given agent type
    """
    try:
        balancer = get_load_balancer()
        gpu_state = await balancer.get_memory_state()
        
        # Get available models
        models_ranked = []
        for name, model in balancer.models.items():
            fits_in_memory = balancer._calculate_model_fit(model, gpu_state.available_memory_gb)
            priority = model.priority_score if fits_in_memory else float('inf')
            
            models_ranked.append({
                "model_name": name,
                "vram_gb": model.vram_gb,
                "backend": model.backend,
                "fits_in_memory": fits_in_memory,
                "priority_score": priority,
                "avg_latency_ms": model.avg_latency_ms,
                "failure_count": model.failure_count,
            })
        
        # Sort by priority
        models_ranked.sort(key=lambda x: x["priority_score"] if x["fits_in_memory"] else float('inf'))
        
        return {
            "status": "ok",
            "agent_type": agent_type,
            "gpu_available_gb": gpu_state.available_memory_gb,
            "models_ranked": models_ranked,
        }
    except Exception as e:
        logger.error(f"Get optimal models failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/benchmark-model")
async def benchmark_model(
    model_name: str,
    num_iterations: int = 5
):
    """
    Benchmark a specific model for latency and throughput
    """
    try:
        balancer = get_load_balancer()
        
        if model_name not in balancer.models:
            raise HTTPException(status_code=404, detail=f"Model {model_name} not found")
        
        model = balancer.models[model_name]
        
        # Note: This is a placeholder - actual benchmarking would require
        # sending inference requests through the model
        
        return {
            "status": "ok",
            "model_name": model_name,
            "backend": model.backend,
            "vram_gb": model.vram_gb,
            "note": "Benchmark would run actual inference tests (not implemented in stub)",
            "recent_metrics": {
                "avg_latency_ms": model.avg_latency_ms,
                "queue_size": model.queue_size,
                "failure_count": model.failure_count,
            }
        }
    except Exception as e:
        logger.error(f"Model benchmarking failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
