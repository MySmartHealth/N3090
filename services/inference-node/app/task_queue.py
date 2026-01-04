"""
Async Task Queue System with Redis Backend
Handles concurrent inference requests, batching, and priority queuing
"""
import asyncio
import json
import time
import uuid
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum
from datetime import datetime, timedelta
from loguru import logger


class TaskPriority(int, Enum):
    """Task priority levels (higher = process first)"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4  # Emergency medical requests


class TaskStatus(str, Enum):
    """Task lifecycle states"""
    QUEUED = "queued"
    BATCHED = "batched"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CACHED = "cached"


@dataclass
class InferenceTask:
    """Single inference request"""
    task_id: str
    agent_type: str
    messages: List[Dict[str, str]]
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.QUEUED
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    model_preference: Optional[str] = None
    timeout_seconds: int = 300  # 5 min default
    max_tokens: int = 512
    temperature: float = 0.7
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retries_left: int = 3
    batch_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for serialization"""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        data['started_at'] = self.started_at.isoformat() if self.started_at else None
        data['completed_at'] = self.completed_at.isoformat() if self.completed_at else None
        data['priority'] = self.priority.value
        data['status'] = self.status.value
        return data
    
    @property
    def elapsed_seconds(self) -> float:
        """Time since task creation"""
        return (datetime.now() - self.created_at).total_seconds()
    
    @property
    def is_expired(self) -> bool:
        """Check if task exceeded timeout"""
        return self.elapsed_seconds > self.timeout_seconds
    
    @property
    def processing_time_ms(self) -> Optional[float]:
        """Get processing time in milliseconds"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds() * 1000
        return None


@dataclass
class TaskBatch:
    """Group of tasks for batch processing"""
    batch_id: str
    task_ids: List[str]
    agent_type: str
    model_name: str
    created_at: datetime = field(default_factory=datetime.now)
    submitted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    @property
    def size(self) -> int:
        """Batch size"""
        return len(self.task_ids)
    
    @property
    def wait_time_ms(self) -> float:
        """How long batch has been waiting"""
        return (datetime.now() - self.created_at).total_seconds() * 1000


@dataclass
class QueueStats:
    """Queue statistics for monitoring"""
    total_tasks: int = 0
    queued_tasks: int = 0
    processing_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    avg_wait_time_ms: float = 0.0
    avg_processing_time_ms: float = 0.0
    queue_depth_by_priority: Dict[str, int] = field(default_factory=dict)
    throughput_per_minute: float = 0.0


class TaskQueue:
    """In-memory task queue with priority support and batching"""
    
    def __init__(
        self,
        batch_size: int = 4,
        batch_timeout_ms: float = 1000.0,
        max_queue_size: int = 10000,
    ):
        self.batch_size = batch_size
        self.batch_timeout_ms = batch_timeout_ms
        self.max_queue_size = max_queue_size
        
        # Priority queues (separate list per priority)
        self.queues: Dict[TaskPriority, List[InferenceTask]] = {
            p: [] for p in TaskPriority
        }
        
        # Task tracking
        self.tasks: Dict[str, InferenceTask] = {}  # All tasks by ID
        self.batches: Dict[str, TaskBatch] = {}  # Active batches
        
        # Metrics
        self.completed_count = 0
        self.failed_count = 0
        self.completed_times: List[float] = []  # Track last 100 completion times
        
        # Response caching (memoization)
        self.response_cache: Dict[str, Tuple[Dict, float]] = {}  # (result, timestamp)
        self.cache_ttl_seconds = 300  # 5 minutes
        
        logger.info(f"TaskQueue initialized: batch_size={batch_size}, batch_timeout={batch_timeout_ms}ms")
    
    def add_task(self, task: InferenceTask) -> str:
        """Add task to queue"""
        if len(self.tasks) >= self.max_queue_size:
            raise RuntimeError(f"Queue full ({self.max_queue_size} tasks)")
        
        if not task.task_id:
            task.task_id = str(uuid.uuid4())[:12]
        
        self.tasks[task.task_id] = task
        self.queues[task.priority].append(task)
        
        logger.info(
            f"Task queued: {task.task_id} | agent={task.agent_type} | "
            f"priority={task.priority.name} | queue_depth={self.queue_depth}"
        )
        
        return task.task_id
    
    def get_next_task(self) -> Optional[InferenceTask]:
        """Get highest priority task (FIFO within priority)"""
        # Check from highest to lowest priority
        for priority in sorted(TaskPriority, reverse=True):
            if self.queues[priority]:
                task = self.queues[priority].pop(0)
                task.status = TaskStatus.PROCESSING
                task.started_at = datetime.now()
                return task
        return None
    
    def get_tasks_for_batch(self, agent_type: str, count: int = None) -> List[InferenceTask]:
        """Get N tasks of same type for batching"""
        count = count or self.batch_size
        batch_tasks = []
        
        # Prioritize high-priority tasks
        for priority in sorted(TaskPriority, reverse=True):
            for i, task in enumerate(self.queues[priority]):
                if task.agent_type == agent_type and len(batch_tasks) < count:
                    # Skip expired tasks
                    if not task.is_expired:
                        batch_tasks.append(task)
                        self.queues[priority].pop(i)
                        task.status = TaskStatus.BATCHED
                        break  # Only take one per priority
        
        return batch_tasks
    
    def create_batch(self, tasks: List[InferenceTask], model_name: str) -> str:
        """Group tasks into a batch"""
        batch_id = str(uuid.uuid4())[:12]
        task_ids = [t.task_id for t in tasks]
        
        batch = TaskBatch(
            batch_id=batch_id,
            task_ids=task_ids,
            agent_type=tasks[0].agent_type if tasks else "unknown",
            model_name=model_name,
        )
        
        self.batches[batch_id] = batch
        for task in tasks:
            task.batch_id = batch_id
        
        logger.info(f"Batch created: {batch_id} | size={batch.size} | model={model_name}")
        return batch_id
    
    def complete_task(self, task_id: str, result: Dict[str, Any]):
        """Mark task as completed"""
        if task_id not in self.tasks:
            logger.warning(f"Task not found: {task_id}")
            return
        
        task = self.tasks[task_id]
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now()
        task.result = result
        
        # Update metrics
        self.completed_count += 1
        if task.processing_time_ms:
            self.completed_times.append(task.processing_time_ms)
            # Keep only last 100 for efficiency
            if len(self.completed_times) > 100:
                self.completed_times.pop(0)
        
        # Cache response if same request might come again
        self._cache_response(task)
        
        logger.info(
            f"Task completed: {task_id} | time={task.processing_time_ms:.0f}ms | "
            f"model={result.get('model', 'unknown')}"
        )
    
    def fail_task(self, task_id: str, error: str):
        """Mark task as failed with optional retry"""
        if task_id not in self.tasks:
            return
        
        task = self.tasks[task_id]
        task.error = error
        
        # Retry up to max retries
        if task.retries_left > 0:
            task.retries_left -= 1
            task.status = TaskStatus.QUEUED
            task.started_at = None
            # Re-queue with slightly lower priority
            self.queues[task.priority].append(task)
            logger.warning(f"Task retried: {task_id} | retries_left={task.retries_left}")
        else:
            task.status = TaskStatus.FAILED
            self.failed_count += 1
            logger.error(f"Task failed (no retries): {task_id} | error={error}")
    
    def timeout_task(self, task_id: str):
        """Mark task as timed out"""
        if task_id not in self.tasks:
            return
        
        task = self.tasks[task_id]
        task.status = TaskStatus.TIMEOUT
        task.error = "Request timeout"
        self.failed_count += 1
        logger.warning(f"Task timeout: {task_id} | elapsed={task.elapsed_seconds:.1f}s")
    
    def _cache_response(self, task: InferenceTask):
        """Cache successful response"""
        if not task.result:
            return
        
        # Create cache key from task inputs
        cache_key = self._make_cache_key(task)
        self.response_cache[cache_key] = (task.result, time.time())
    
    def check_cache(self, task: InferenceTask) -> Optional[Dict[str, Any]]:
        """Check if response is cached"""
        cache_key = self._make_cache_key(task)
        
        if cache_key in self.response_cache:
            result, timestamp = self.response_cache[cache_key]
            age_seconds = time.time() - timestamp
            
            if age_seconds < self.cache_ttl_seconds:
                logger.info(f"Cache hit: {cache_key} | age={age_seconds:.1f}s")
                return result
            else:
                # Expire old cache
                del self.response_cache[cache_key]
        
        return None
    
    def _make_cache_key(self, task: InferenceTask) -> str:
        """Create cache key from task"""
        # Hash the messages and model to create key
        msg_str = json.dumps(task.messages, sort_keys=True)
        return f"{task.agent_type}:{task.model_preference}:{hash(msg_str) % 100000}"
    
    @property
    def queue_depth(self) -> int:
        """Total tasks in queue (not processing/completed)"""
        return sum(len(q) for q in self.queues.values())
    
    @property
    def processing_count(self) -> int:
        """Tasks currently processing"""
        return sum(1 for t in self.tasks.values() if t.status == TaskStatus.PROCESSING)
    
    def get_stats(self) -> QueueStats:
        """Get queue statistics"""
        stats = QueueStats(
            total_tasks=len(self.tasks),
            queued_tasks=self.queue_depth,
            processing_tasks=self.processing_count,
            completed_tasks=self.completed_count,
            failed_tasks=self.failed_count,
        )
        
        # Calculate average times
        if self.completed_times:
            stats.avg_processing_time_ms = sum(self.completed_times) / len(self.completed_times)
        
        # Queue depth by priority
        stats.queue_depth_by_priority = {
            p.name: len(self.queues[p]) for p in TaskPriority
        }
        
        # Throughput (completed per minute)
        if self.completed_count > 0:
            avg_time_sec = stats.avg_processing_time_ms / 1000
            stats.throughput_per_minute = 60 / avg_time_sec if avg_time_sec > 0 else 0
        
        return stats
    
    def get_task(self, task_id: str) -> Optional[InferenceTask]:
        """Get task by ID"""
        return self.tasks.get(task_id)
    
    def get_batch_results(self, batch_id: str) -> Dict[str, Any]:
        """Get all results for a batch"""
        if batch_id not in self.batches:
            return {}
        
        batch = self.batches[batch_id]
        results = {}
        
        for task_id in batch.task_ids:
            task = self.tasks.get(task_id)
            if task:
                results[task_id] = {
                    "status": task.status.value,
                    "result": task.result,
                    "error": task.error,
                    "processing_time_ms": task.processing_time_ms,
                }
        
        return results
    
    def cleanup_old_tasks(self, max_age_seconds: int = 3600):
        """Remove completed tasks older than max_age"""
        cutoff = datetime.now() - timedelta(seconds=max_age_seconds)
        to_delete = []
        
        for task_id, task in self.tasks.items():
            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.TIMEOUT):
                if task.completed_at and task.completed_at < cutoff:
                    to_delete.append(task_id)
        
        for task_id in to_delete:
            del self.tasks[task_id]
        
        if to_delete:
            logger.info(f"Cleaned up {len(to_delete)} old tasks")


# Global task queue instance
_task_queue: Optional[TaskQueue] = None


def get_task_queue(batch_size: int = 4, batch_timeout_ms: float = 1000) -> TaskQueue:
    """Get or create global task queue"""
    global _task_queue
    if _task_queue is None:
        _task_queue = TaskQueue(batch_size=batch_size, batch_timeout_ms=batch_timeout_ms)
    return _task_queue


class BatchProcessor:
    """Process batches of tasks for efficient inference"""
    
    def __init__(self, queue: TaskQueue):
        self.queue = queue
        self.is_running = False
        self.processed_batches = 0
        self.processing_task = None
    
    async def process_batch(
        self,
        batch_id: str,
        inference_func,  # Async function that processes batch
    ) -> Dict[str, Any]:
        """Process a batch of tasks"""
        batch = self.queue.batches.get(batch_id)
        if not batch:
            raise ValueError(f"Batch not found: {batch_id}")
        
        batch.submitted_at = datetime.now()
        logger.info(f"Processing batch: {batch_id} | size={batch.size}")
        
        try:
            # Get all tasks in batch
            batch_tasks = [self.queue.tasks[tid] for tid in batch.task_ids]
            
            # Call inference function with batch
            results = await inference_func(batch_tasks)
            
            # Update individual task results
            for task_id, result in results.items():
                if task_id in self.queue.tasks:
                    self.queue.complete_task(task_id, result)
            
            batch.completed_at = datetime.now()
            self.processed_batches += 1
            
            elapsed = (batch.completed_at - batch.submitted_at).total_seconds()
            throughput = batch.size / elapsed if elapsed > 0 else 0
            
            logger.info(
                f"Batch completed: {batch_id} | "
                f"time={elapsed:.2f}s | throughput={throughput:.1f} tasks/sec"
            )
            
            return {
                "batch_id": batch_id,
                "size": batch.size,
                "processing_time_s": elapsed,
                "results": results,
            }
        
        except Exception as e:
            logger.error(f"Batch processing failed: {batch_id} | error={e}")
            # Fail all tasks in batch
            for task_id in batch.task_ids:
                self.queue.fail_task(task_id, str(e))
            raise
    
    async def process_queue_continuously(
        self,
        inference_func,
        poll_interval_ms: float = 100,
        max_batch_wait_ms: float = 1000,
    ):
        """Continuously process queued tasks in batches"""
        self.is_running = True
        logger.info(f"Starting batch processor: poll={poll_interval_ms}ms, max_wait={max_batch_wait_ms}ms")
        
        while self.is_running:
            try:
                # Get tasks for batching
                agent_types = {}  # Group by agent type
                for task in self.queue.tasks.values():
                    if task.status == TaskStatus.QUEUED:
                        if task.agent_type not in agent_types:
                            agent_types[task.agent_type] = []
                        agent_types[task.agent_type].append(task)
                
                # Process batches for each agent type
                for agent_type, tasks in agent_types.items():
                    if len(tasks) >= self.queue.batch_size:
                        # Enough for a full batch
                        batch_tasks = tasks[:self.queue.batch_size]
                        batch_id = self.queue.create_batch(batch_tasks, agent_type)
                        await self.process_batch(batch_id, inference_func)
                    elif tasks and tasks[0].elapsed_seconds > (max_batch_wait_ms / 1000):
                        # Wait timeout exceeded, process partial batch
                        batch_id = self.queue.create_batch(tasks, agent_type)
                        await self.process_batch(batch_id, inference_func)
                
                # Check for timeouts
                for task_id, task in list(self.queue.tasks.items()):
                    if task.is_expired:
                        self.queue.timeout_task(task_id)
                
                await asyncio.sleep(poll_interval_ms / 1000)
            
            except Exception as e:
                logger.error(f"Batch processor error: {e}")
                await asyncio.sleep(1)
    
    def stop(self):
        """Stop processing"""
        self.is_running = False
        logger.info(f"Batch processor stopped: processed={self.processed_batches} batches")
