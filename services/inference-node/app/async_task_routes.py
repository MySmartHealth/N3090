"""
Async Task Queue API Routes
Handles concurrent inference requests with queuing, batching, and polling
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from loguru import logger
from datetime import datetime
import uuid

from .task_queue import (
    get_task_queue, InferenceTask, TaskPriority, TaskStatus,
    BatchProcessor
)


class InferenceRequest(BaseModel):
    """Async inference request"""
    agent_type: str
    messages: List[Dict[str, str]]
    priority: str = "normal"
    model_preference: Optional[str] = None
    timeout_seconds: int = 300
    max_tokens: int = 512
    temperature: float = 0.7


class BatchInferenceRequest(BaseModel):
    """Batch inference request"""
    agent_type: str
    messages_list: List[List[Dict[str, str]]]
    priority: str = "normal"
    model_preference: Optional[str] = None


router = APIRouter(prefix="/v1/async", tags=["Async Task Queue"])


@router.post("/submit")
async def submit_inference_task(req: InferenceRequest) -> Dict[str, Any]:
    """
    Submit an inference request to async queue
    Returns immediately with task_id for polling
    """
    try:
        queue = get_task_queue()
        
        # Parse priority
        try:
            task_priority = TaskPriority[req.priority.upper()]
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Invalid priority: {req.priority}")
        
        # Check cache first (avoid unnecessary queuing)
        test_task = InferenceTask(
            task_id="",
            agent_type=req.agent_type,
            messages=req.messages,
            model_preference=req.model_preference,
        )
        
        cached_result = queue.check_cache(test_task)
        if cached_result:
            return {
                "status": "cached",
                "result": cached_result,
                "cached": True,
            }
        
        # Create task
        task = InferenceTask(
            task_id=str(uuid.uuid4())[:12],
            agent_type=req.agent_type,
            messages=req.messages,
            priority=task_priority,
            model_preference=req.model_preference,
            timeout_seconds=req.timeout_seconds,
            max_tokens=req.max_tokens,
            temperature=req.temperature,
        )
        
        # Add to queue
        task_id = queue.add_task(task)
        
        # Estimate wait time based on queue stats
        stats = queue.get_stats()
        estimated_wait_ms = (
            stats.queue_depth * (stats.avg_processing_time_ms or 1000)
            if stats.avg_processing_time_ms > 0
            else 1000
        )
        
        return {
            "status": "queued",
            "task_id": task_id,
            "priority": req.priority,
            "position_in_queue": queue.queue_depth,
            "estimated_wait_ms": estimated_wait_ms,
            "queue_stats": {
                "total_queued": stats.queued_tasks,
                "processing": stats.processing_tasks,
                "completed": stats.completed_tasks,
            }
        }
    
    except Exception as e:
        logger.error(f"Task submission failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{task_id}")
async def get_task_status(task_id: str) -> Dict[str, Any]:
    """
    Get status of a submitted task
    
    Returns:
        Task status, progress, and result when ready
    """
    try:
        queue = get_task_queue()
        task = queue.get_task(task_id)
        
        if not task:
            raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
        
        response = {
            "task_id": task_id,
            "status": task.status.value,
            "priority": task.priority.name,
            "agent_type": task.agent_type,
            "created_at": task.created_at.isoformat(),
            "elapsed_seconds": task.elapsed_seconds,
        }
        
        if task.status == TaskStatus.COMPLETED:
            response["result"] = task.result
            response["processing_time_ms"] = task.processing_time_ms
        elif task.status in (TaskStatus.FAILED, TaskStatus.TIMEOUT):
            response["error"] = task.error
            response["retries_left"] = task.retries_left
        elif task.status == TaskStatus.PROCESSING:
            response["started_at"] = task.started_at.isoformat() if task.started_at else None
        elif task.status == TaskStatus.QUEUED:
            # Estimate wait time
            stats = queue.get_stats()
            response["position_in_queue"] = queue.queue_depth
            response["estimated_wait_ms"] = stats.avg_processing_time_ms or 1000
        
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/batch-status/{batch_id}")
async def get_batch_status(batch_id: str) -> Dict[str, Any]:
    """Get status of all tasks in a batch"""
    try:
        queue = get_task_queue()
        results = queue.get_batch_results(batch_id)
        
        if not results:
            raise HTTPException(status_code=404, detail=f"Batch not found: {batch_id}")
        
        # Aggregate status
        statuses = {
            "completed": 0,
            "processing": 0,
            "failed": 0,
            "pending": 0,
        }
        total_time_ms = 0
        
        for task_result in results.values():
            status = task_result["status"]
            if status == "completed":
                statuses["completed"] += 1
                if task_result.get("processing_time_ms"):
                    total_time_ms += task_result["processing_time_ms"]
            elif status == "processing":
                statuses["processing"] += 1
            elif status in ("failed", "timeout"):
                statuses["failed"] += 1
            else:
                statuses["pending"] += 1
        
        return {
            "batch_id": batch_id,
            "total_tasks": len(results),
            "status_summary": statuses,
            "avg_processing_time_ms": total_time_ms / statuses["completed"] if statuses["completed"] > 0 else None,
            "tasks": results,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch status check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/submit-batch")
async def submit_batch(req: BatchInferenceRequest) -> Dict[str, Any]:
    """
    Submit multiple inference requests as a batch
    More efficient than submitting individually
    """
    try:
        queue = get_task_queue()
        
        if not req.messages_list or len(req.messages_list) == 0:
            raise HTTPException(status_code=400, detail="Empty batch")
        
        if len(req.messages_list) > 1000:
            raise HTTPException(status_code=400, detail="Batch too large (max 1000)")
        
        # Parse priority
        try:
            task_priority = TaskPriority[req.priority.upper()]
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Invalid priority: {req.priority}")
        
        # Create tasks
        task_ids = []
        for messages in req.messages_list:
            task = InferenceTask(
                task_id=str(uuid.uuid4())[:12],
                agent_type=req.agent_type,
                messages=messages,
                priority=task_priority,
                model_preference=req.model_preference,
            )
            task_id = queue.add_task(task)
            task_ids.append(task_id)
        
        # Create batch
        batch_id = queue.create_batch(
            [queue.tasks[tid] for tid in task_ids],
            req.model_preference or req.agent_type
        )
        
        stats = queue.get_stats()
        
        return {
            "status": "queued",
            "batch_id": batch_id,
            "task_ids": task_ids,
            "batch_size": len(task_ids),
            "estimated_wait_ms": (stats.queue_depth * stats.avg_processing_time_ms) if stats.avg_processing_time_ms > 0 else 0,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch submission failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_queue_stats() -> Dict[str, Any]:
    """Get queue statistics and performance metrics"""
    try:
        queue = get_task_queue()
        stats = queue.get_stats()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "queue": {
                "total_tasks": stats.total_tasks,
                "queued": stats.queued_tasks,
                "processing": stats.processing_tasks,
                "completed": stats.completed_tasks,
                "failed": stats.failed_tasks,
                "by_priority": stats.queue_depth_by_priority,
            },
            "performance": {
                "avg_processing_time_ms": stats.avg_processing_time_ms,
                "throughput_tasks_per_minute": stats.throughput_per_minute,
                "avg_wait_time_ms": stats.avg_wait_time_ms,
            },
            "cache": {
                "cached_responses": len(queue.response_cache),
                "cache_ttl_seconds": queue.cache_ttl_seconds,
            }
        }
    
    except Exception as e:
        logger.error(f"Stats retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cancel/{task_id}")
async def cancel_task(task_id: str) -> Dict[str, Any]:
    """Cancel a queued task (cannot cancel processing tasks)"""
    try:
        queue = get_task_queue()
        task = queue.get_task(task_id)
        
        if not task:
            raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
        
        if task.status == TaskStatus.PROCESSING:
            raise HTTPException(status_code=400, detail="Cannot cancel processing task")
        
        if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            raise HTTPException(status_code=400, detail=f"Task already {task.status.value}")
        
        # Remove from queue
        if task.priority in queue.queues:
            queue.queues[task.priority] = [
                t for t in queue.queues[task.priority] if t.task_id != task_id
            ]
        
        task.status = TaskStatus.FAILED
        task.error = "Cancelled by user"
        
        return {
            "status": "cancelled",
            "task_id": task_id,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Task cancellation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup")
async def cleanup_completed_tasks(max_age_seconds: int = 3600) -> Dict[str, Any]:
    """Remove old completed tasks to free memory"""
    try:
        queue = get_task_queue()
        initial_count = len(queue.tasks)
        
        queue.cleanup_old_tasks(max_age_seconds)
        
        final_count = len(queue.tasks)
        cleaned = initial_count - final_count
        
        return {
            "status": "success",
            "tasks_before": initial_count,
            "tasks_after": final_count,
            "cleaned_up": cleaned,
            "max_age_seconds": max_age_seconds,
        }
    
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def queue_health() -> Dict[str, Any]:
    """Check queue health"""
    try:
        queue = get_task_queue()
        stats = queue.get_stats()
        
        # Determine health status
        if stats.queued_tasks > 100:
            health = "warning"  # Queue building up
        elif stats.failed_tasks > stats.completed_tasks * 0.1:
            health = "degraded"  # >10% failure rate
        else:
            health = "healthy"
        
        return {
            "status": "ok",
            "health": health,
            "queue_depth": stats.queued_tasks,
            "processing": stats.processing_tasks,
            "failed_rate_percent": (stats.failed_tasks / stats.total_tasks * 100) if stats.total_tasks > 0 else 0,
            "avg_latency_ms": stats.avg_processing_time_ms,
        }
    
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "error",
            "health": "unhealthy",
            "error": str(e),
        }
