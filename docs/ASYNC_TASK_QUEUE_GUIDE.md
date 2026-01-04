# Async Task Queue & Load Balancing Guide

## Overview

The inference system now has enterprise-grade asynchronous task handling with priority queuing, load balancing, and intelligent GPU resource management.

### Architecture

```
Client Requests
    ↓
[API Endpoint /v1/async/submit]
    ↓
[Priority Queue Manager]
    ├─ HIGH priority tasks (position 1)
    ├─ NORMAL priority tasks
    └─ LOW priority tasks
    ↓
[Batch Collation Engine]
    (Combines tasks with same agent_type)
    ↓
[GPU Load Balancer]
    (SmartLoadBalancer decides model + backend)
    ├─ llama.cpp (low latency, high precision)
    └─ vLLM (high throughput, streaming)
    ↓
[Model Inference]
    (3 models: tiny-llama-1b, bi-medix2, openins-llama3-8b)
    ↓
[Result Storage & Retrieval]
    (Task status polling via /v1/async/status/{task_id})
```

## Task Lifecycle

### 1. Task Submission
Submit a task to the queue with optional priority.

**Endpoint**: `POST /v1/async/submit`

**Request**:
```json
{
  "agent_type": "Chat",
  "messages": [
    {
      "role": "user",
      "content": "What are the symptoms of diabetes?"
    }
  ],
  "priority": "NORMAL",
  "timeout_seconds": 60,
  "max_tokens": 500,
  "temperature": 0.7
}
```

**Priority Levels**:
- `CRITICAL`: Emergency medical queries (process immediately)
- `HIGH`: Urgent medical questions (prioritized)
- `NORMAL`: Standard queries (default)
- `LOW`: Background processing, bulk operations

**Response**:
```json
{
  "status": "queued",
  "task_id": "1b5b899a-f14",
  "priority": "NORMAL",
  "position_in_queue": 3,
  "estimated_wait_ms": 2500,
  "queue_stats": {
    "total_tasks": 4,
    "queued": 4,
    "processing": 0,
    "completed": 0,
    "failed": 0
  }
}
```

### 2. Batch Submission
Submit multiple tasks atomically.

**Endpoint**: `POST /v1/async/submit-batch`

**Request**:
```json
{
  "requests": [
    {
      "agent_type": "Chat",
      "messages": [{"role": "user", "content": "Question 1?"}],
      "priority": "NORMAL"
    },
    {
      "agent_type": "Chat",
      "messages": [{"role": "user", "content": "Question 2?"}],
      "priority": "HIGH"
    },
    {
      "agent_type": "MedicalAnalyzer",
      "messages": [{"role": "user", "content": "Analyze: ..."}],
      "priority": "CRITICAL"
    }
  ],
  "timeout_seconds": 60,
  "process_in_parallel": true
}
```

**Response**:
```json
{
  "batch_id": "batch-abc123",
  "total_tasks": 3,
  "task_ids": [
    "task-1",
    "task-2",
    "task-3"
  ],
  "message": "Batch submitted successfully"
}
```

### 3. Task Status Polling
Check status of a specific task.

**Endpoint**: `GET /v1/async/status/{task_id}`

**Response States**:
- `queued`: Waiting in priority queue
- `batching`: Collected in batch, waiting for timeout or batch size
- `processing`: Currently executing inference
- `completed`: Finished successfully
- `failed`: Inference failed
- `cancelled`: User cancelled task

**Response**:
```json
{
  "task_id": "1b5b899a-f14",
  "status": "processing",
  "agent_type": "Chat",
  "priority": "NORMAL",
  "position_in_queue": 0,
  "created_at": "2026-01-04T13:05:30Z",
  "started_at": "2026-01-04T13:05:35Z",
  "completed_at": null,
  "progress_percent": 45,
  "model_selected": "tiny-llama-1b",
  "backend": "llama.cpp"
}
```

### 4. Result Retrieval
Get completed task result.

**Endpoint**: `GET /v1/async/result/{task_id}`

**Response** (only after completion):
```json
{
  "task_id": "1b5b899a-f14",
  "status": "completed",
  "result": {
    "content": "Diabetes is a chronic medical condition...",
    "stop_reason": "end_of_sequence"
  },
  "model_used": "tiny-llama-1b",
  "backend": "llama.cpp",
  "inference_time_ms": 1250,
  "tokens_generated": 142,
  "queue_wait_time_ms": 2500,
  "total_time_ms": 3750
}
```

### 5. Batch Status Tracking
Monitor batch progress.

**Endpoint**: `GET /v1/async/batch-status/{batch_id}`

**Response**:
```json
{
  "batch_id": "batch-abc123",
  "total_tasks": 3,
  "completed_tasks": 2,
  "failed_tasks": 0,
  "processing_tasks": 1,
  "queued_tasks": 0,
  "progress_percent": 67,
  "estimated_completion_ms": 1500,
  "task_statuses": {
    "task-1": "completed",
    "task-2": "completed",
    "task-3": "processing"
  }
}
```

### 6. Queue Health Monitoring
Real-time queue metrics.

**Endpoint**: `GET /v1/async/stats`

**Response**:
```json
{
  "timestamp": "2026-01-04T13:05:36Z",
  "queue": {
    "total_tasks": 4,
    "queued": 4,
    "processing": 0,
    "completed": 0,
    "failed": 0,
    "by_priority": {
      "CRITICAL": 0,
      "HIGH": 2,
      "NORMAL": 2,
      "LOW": 0
    }
  },
  "performance": {
    "avg_processing_time_ms": 1250,
    "throughput_tasks_per_minute": 48,
    "avg_wait_time_ms": 2500
  },
  "cache": {
    "cached_responses": 15,
    "cache_ttl_seconds": 300
  }
}
```

### 7. Task Cancellation
Cancel a queued task.

**Endpoint**: `DELETE /v1/async/cancel/{task_id}`

**Response**:
```json
{
  "task_id": "1b5b899a-f14",
  "status": "cancelled",
  "message": "Task cancelled successfully"
}
```

Note: Can only cancel tasks in `queued` or `batching` state. Processing tasks cannot be cancelled.

## GPU Load Balancing

### Memory Pressure Levels

The GPU orchestrator monitors and responds to memory pressure:

**Level 0 - Low** (0-50% memory used)
- All models available
- vLLM enabled (high throughput)
- Batch size: 8
- No throttling

**Level 1 - Normal** (50-70% memory used)
- All models available
- Prefer llama.cpp for new requests
- Batch size: 6
- Monitor temperature

**Level 2 - High** (70-85% memory used)
- Largest models deprioritized
- Only llama.cpp mode
- Batch size: 4
- Reduce concurrency

**Level 3 - Critical** (85-95% memory used)
- Only smallest model (tiny-llama-1b)
- Sequential processing (no batching)
- Pause new requests if >95%
- Emergency memory recovery mode

### Thermal Management

**Temperature < 65°C**: Normal operation, full capacity

**Temperature 65-80°C**: Monitoring mode, reduce load gradually

**Temperature > 80°C**: Throttle mode, reduce concurrency by 50%

**Temperature > 85°C**: Critical, pause inference, let cool

### Model Selection Algorithm

For each task, the system:
1. Gets current GPU metrics (memory, temp)
2. Classifies memory pressure level
3. Filters models that fit in available memory
4. Ranks by: preferred backend, latency history, failure rate
5. Selects best match

```python
# Example decision logic
if memory_pressure == "CRITICAL":
    # Only use tiny-llama-1b
    selected_model = "tiny-llama-1b"
    backend = "llama.cpp"
    max_concurrency = 1
elif memory_pressure == "HIGH":
    # Prefer tiny-llama-1b, fallback to bi-medix2
    if available_memory >= 6.5:
        selected_model = "bi-medix2-8b"
    else:
        selected_model = "tiny-llama-1b"
    backend = "llama.cpp"
    max_concurrency = 2
else:
    # All models available
    selected_model = best_by_latency(available_models)
    backend = "vllm" if memory_pressure == "LOW" else "llama.cpp"
    max_concurrency = 4 if memory_pressure == "LOW" else 2
```

## Real-World Usage Examples

### Example 1: Single Medical Question

```bash
# Submit medical question
TASK_ID=$(curl -s -X POST http://localhost:8000/v1/async/submit \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "Chat",
    "messages": [{"role": "user", "content": "Explain type 2 diabetes management"}],
    "priority": "NORMAL",
    "timeout_seconds": 30
  }' | jq -r '.task_id')

echo "Task submitted: $TASK_ID"

# Poll for result
while true; do
  STATUS=$(curl -s http://localhost:8000/v1/async/status/$TASK_ID | jq -r '.status')
  echo "Status: $STATUS"
  
  if [ "$STATUS" = "completed" ]; then
    curl -s http://localhost:8000/v1/async/result/$TASK_ID | jq '.result.content'
    break
  elif [ "$STATUS" = "failed" ]; then
    echo "Task failed"
    break
  fi
  
  sleep 1
done
```

### Example 2: Batch Medical Analysis

```bash
# Submit 5 related medical analyses
curl -X POST http://localhost:8000/v1/async/submit-batch \
  -H "Content-Type: application/json" \
  -d '{
    "requests": [
      {
        "agent_type": "MedicalAnalyzer",
        "messages": [{"role": "user", "content": "Patient A: hypertension, obesity"}],
        "priority": "HIGH"
      },
      {
        "agent_type": "MedicalAnalyzer",
        "messages": [{"role": "user", "content": "Patient B: diabetes, neuropathy"}],
        "priority": "HIGH"
      },
      {
        "agent_type": "MedicalAnalyzer",
        "messages": [{"role": "user", "content": "Patient C: cardiovascular disease"}],
        "priority": "HIGH"
      },
      {
        "agent_type": "MedicalAnalyzer",
        "messages": [{"role": "user", "content": "Patient D: respiratory issues"}],
        "priority": "NORMAL"
      },
      {
        "agent_type": "MedicalAnalyzer",
        "messages": [{"role": "user", "content": "Patient E: neurological concerns"}],
        "priority": "NORMAL"
      }
    ],
    "timeout_seconds": 120,
    "process_in_parallel": true
  }' | jq .

# Monitor batch progress
BATCH_ID="batch-abc123"
while true; do
  curl -s http://localhost:8000/v1/async/batch-status/$BATCH_ID | jq .
  sleep 2
done
```

### Example 3: Load Testing with 100 Concurrent Requests

```bash
#!/bin/bash
# Load test script

echo "Submitting 100 concurrent requests..."
TASK_IDS=()

for i in {1..100}; do
  PRIORITY="NORMAL"
  if [ $((i % 10)) -eq 0 ]; then
    PRIORITY="HIGH"
  fi
  
  TASK_ID=$(curl -s -X POST http://localhost:8000/v1/async/submit \
    -H "Content-Type: application/json" \
    -d "{
      \"agent_type\": \"Chat\",
      \"messages\": [{\"role\": \"user\", \"content\": \"Query $i\"}],
      \"priority\": \"$PRIORITY\",
      \"timeout_seconds\": 60
    }" | jq -r '.task_id') &
  
  TASK_IDS+=($TASK_ID)
  
  # Rate limit: 10 submissions per second
  if [ $((i % 10)) -eq 0 ]; then
    wait
  fi
done

wait

echo "All tasks submitted. Monitoring..."

# Monitor queue
COMPLETED=0
while [ $COMPLETED -lt 100 ]; do
  STATS=$(curl -s http://localhost:8000/v1/async/stats)
  COMPLETED=$(echo $STATS | jq '.queue.completed')
  TOTAL=$(echo $STATS | jq '.queue.total_tasks')
  THROUGHPUT=$(echo $STATS | jq '.performance.throughput_tasks_per_minute')
  
  echo "Progress: $COMPLETED / $TOTAL completed, $THROUGHPUT tasks/min"
  sleep 5
done

echo "All tasks completed!"
```

## Monitoring & Observability

### Prometheus Metrics

The task queue exposes metrics to Prometheus:

```
# Queue depth
task_queue_depth{priority="high"} 2
task_queue_depth{priority="normal"} 4
task_queue_depth{priority="low"} 0

# Processing
tasks_processing{model="tiny-llama-1b"} 1
tasks_processing{model="bi-medix2-8b"} 0

# Performance
task_processing_time_ms{percentile="p50"} 1250
task_processing_time_ms{percentile="p95"} 3500
task_processing_time_ms{percentile="p99"} 5000

# Throughput
tasks_per_minute 48
task_completion_rate 0.98

# GPU
gpu_memory_used_percent 50
gpu_temperature_celsius 49
```

Access at: `http://localhost:8000/metrics`

### Health Checks

**Endpoint**: `GET /v1/async/health`

```json
{
  "status": "ok",
  "health": "healthy",
  "queue_depth": 4,
  "processing": 1,
  "failed_rate_percent": 0.2,
  "avg_latency_ms": 1250
}
```

Health status:
- `healthy`: All systems normal
- `degraded`: Queue backing up or high failure rate
- `unhealthy`: Queue not processing or repeated failures

## Configuration

### Queue Settings

```python
# In app/task_queue.py

# Maximum batch size
MAX_BATCH_SIZE = 8  # Combine up to 8 tasks

# Batch timeout
BATCH_TIMEOUT_MS = 100  # Wait up to 100ms for batch to fill

# Task timeout
DEFAULT_TASK_TIMEOUT_S = 60  # Kill task after 60s

# Result TTL
RESULT_TTL_SECONDS = 300  # Keep results for 5 minutes

# Queue capacity
MAX_QUEUE_SIZE = 1000  # Maximum tasks in queue
```

### Priority Queue Weights

```python
PRIORITY_WEIGHTS = {
    "CRITICAL": 0,  # Process first
    "HIGH": 10,
    "NORMAL": 20,
    "LOW": 30,
}
```

## Troubleshooting

### Tasks Not Processing

**Check queue health**:
```bash
curl http://localhost:8000/v1/async/stats | jq .queue
```

**Check GPU status**:
```bash
curl http://localhost:8000/v1/gpu/status | jq .gpu
```

**Check for errors**:
```bash
tail -f /tmp/api.log | grep -i "error\|failed\|exception"
```

### High Latency

**Check memory pressure**:
```bash
curl http://localhost:8000/v1/gpu/memory-forecast | jq .
```

If memory pressure is HIGH/CRITICAL, scale down batch size or reduce concurrent models.

**Check GPU temperature**:
```bash
nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader
```

If > 80°C, let GPU cool before submitting more tasks.

### Task Timeouts

Increase `timeout_seconds` in request or change default in config:

```json
{
  "agent_type": "Chat",
  "messages": [...],
  "timeout_seconds": 120  # Increase from default 60
}
```

### Memory Issues

**Free memory**:
```bash
curl -X POST http://localhost:8000/v1/async/cleanup \
  -H "Content-Type: application/json" \
  -d '{"max_age_seconds": 300}'
```

This removes completed tasks older than 5 minutes.

## Production Deployment Checklist

- [ ] Load test with 1000+ concurrent tasks
- [ ] Verify GPU doesn't exceed 85°C under sustained load
- [ ] Set `ALLOW_INSECURE_DEV=false`
- [ ] Generate strong JWT secret
- [ ] Configure Redis persistence (optional but recommended)
- [ ] Setup Prometheus scraping for metrics
- [ ] Create Grafana dashboards
- [ ] Set up alerting rules:
  - Queue depth > 500 tasks
  - Task failure rate > 5%
  - GPU temperature > 80°C
  - Average latency > 5000ms
- [ ] Document API for consumers
- [ ] Setup log aggregation (ELK, Datadog, etc.)
- [ ] Test graceful shutdown and recovery
- [ ] Implement dead-letter queue for failed tasks
- [ ] Add task retry logic with exponential backoff

## Next Steps

1. **Redis Persistence**: Replace in-memory queue with Redis for durability
2. **Celery Workers**: Distribute processing across multiple machines
3. **Result Caching**: Cache identical responses to reduce inference overhead
4. **Custom Batching**: Support custom batch strategies by agent type
5. **Priority Preemption**: Allow critical tasks to interrupt normal processing
6. **Distributed Tracing**: Add OpenTelemetry for request tracing
7. **Cost Tracking**: Track inference costs per model/agent
8. **SLA Monitoring**: Monitor and alert on SLA violations

---

For more information on GPU load balancing, see [GPU_LOAD_BALANCING.md](./GPU_LOAD_BALANCING.md)
