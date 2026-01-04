# Medical AI Inference System - Architecture Overview

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          CLIENT APPLICATIONS                                │
│  (Web, Mobile, Healthcare Systems, Chatbots, etc.)                          │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      REVERSE PROXY / LOAD BALANCER                          │
│  (Nginx, HAProxy - SSL/TLS termination, rate limiting)                      │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                       │
                ┌──────────────────────┴──────────────────────┐
                │                                              │
                ▼                                              ▼
    ┌────────────────────────┐              ┌────────────────────────┐
    │  API GATEWAY INSTANCE  │              │  API GATEWAY INSTANCE  │
    │   (Uvicorn Worker 1)   │              │   (Uvicorn Worker 2)   │
    │   Port: 8000           │              │   Port: 8000           │
    └──────────┬─────────────┘              └──────────┬─────────────┘
               │                                       │
               └───────────────┬───────────────────────┘
                               │
        ┌──────────────────────┴──────────────────────┐
        │                                              │
        ▼                                              ▼
    ┌────────────────────┐              ┌────────────────────┐
    │ TASK QUEUE MANAGER │              │  ASYNC TASK QUEUE  │
    │  (FastAPI Routes)  │              │   (In-Memory)      │
    │  - /submit         │              │   - Priority queue │
    │  - /status         │              │   - Batching       │
    │  - /result         │              │   - Metrics        │
    └────────┬───────────┘              └────────┬───────────┘
             │                                    │
             └────────────────┬───────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │  GPU ORCHESTRATOR │
                    │ (SmartLoadBalancer)
                    │  - Monitors GPU   │
                    │  - Routes tasks   │
                    │  - Manages models │
                    │  - Thermal mgmt   │
                    └────────┬─────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
    ┌─────────┐         ┌─────────┐         ┌─────────┐
    │llama.cpp│         │llama.cpp│         │llama.cpp│
    │Port 8080│         │Port 8081│         │Port 8084│
    │Tiny-1.1B│         │BiMediX2 │         │OpenIns  │
    │2.3 GB   │         │6.5 GB   │         │7.8 GB   │
    └────┬────┘         └────┬────┘         └────┬────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             │
                ┌────────────┴────────────┐
                │                         │
                ▼                         ▼
        ┌──────────────────┐     ┌──────────────────┐
        │   GPU MEMORY     │     │ THERMAL SENSORS  │
        │   (RTX 3090)     │     │ (nvidia-smi)     │
        │   24 GB Total    │     │                  │
        │   ~12 GB Active  │     │ Monitoring       │
        └──────────────────┘     │ & Throttling     │
                                 └──────────────────┘
        ┌──────────────────┐
        │   POSTGRESQL     │
        │   DATABASE       │
        │  (Task tracking, │
        │   User mgmt)     │
        └──────────────────┘
        ┌──────────────────┐
        │   REDIS          │
        │  (Optional)      │
        │ (Task queue      │
        │  persistence)    │
        └──────────────────┘
        ┌──────────────────┐
        │   PROMETHEUS     │
        │   MONITORING     │
        │  (Metrics export)│
        └──────────────────┘
```

## Component Details

### 1. API Gateway Layer
**Purpose**: HTTP request handling, validation, authentication
- **Technology**: FastAPI + Uvicorn
- **Workers**: 4 parallel processes
- **Port**: 8000
- **Features**:
  - Request routing
  - JWT authentication
  - Rate limiting
  - CORS handling
  - OpenAPI documentation

**Endpoints Provided**:
- `/healthz` - Health check
- `/v1/chat/completions` - Chat inference
- `/v1/async/submit` - Task submission
- `/v1/async/status/{id}` - Status polling
- `/v1/gpu/status` - GPU monitoring
- `/metrics` - Prometheus metrics

### 2. Task Queue Manager
**Purpose**: Task ingestion and management
- **Technology**: Python asyncio + heapq (priority queue)
- **In-Memory**: Fast, volatile
- **Optional Redis**: Persistent, distributed
- **Features**:
  - Priority queuing (CRITICAL, HIGH, NORMAL, LOW)
  - Task deduplication
  - Batch collation
  - Result caching (300 sec TTL)
  - Performance tracking

**Queue Lifecycle**:
```
QUEUED → [BATCH_WAIT: max 100ms] → PROCESSING → COMPLETED
  ↓                                                    ↓
[TIMEOUT]                                        [CACHE 5 min]
  ↓                                                    ↓
FAILED ←─────────────────────────────────────────→ EXPIRED
```

### 3. GPU Orchestrator
**Purpose**: Intelligent GPU resource management
- **Technology**: nvidia-smi monitoring + Python routing logic
- **Metrics Tracked**:
  - Memory usage (GB)
  - Temperature (°C)
  - Power draw (W)
  - Utilization (%)
  - Per-model latency (EMA)
  - Per-model failure rate

**Memory Pressure Management**:
```
Memory Level          0-50%        50-70%       70-85%      85-95%
├─ Name:             LOW         NORMAL        HIGH        CRITICAL
├─ Available Models:  All         All           Top 2       Only tiny
├─ Preferred Backend: vLLM        llama.cpp     llama.cpp   llama.cpp
├─ Batch Size:       8            6             4           1
├─ Concurrency:      4            2             1           0 (pause)
└─ Response:        Full          Throttle     Heavy       Emergency

Temperature Management:
├─ 0-65°C:    ✅ Normal (full capacity)
├─ 65-80°C:   ⚠️  Monitor (reduce load)
├─ 80-85°C:   🚨 Throttle (pause new)
└─ >85°C:     ❌ Critical (stop all)
```

### 4. Model Inference Servers
**Purpose**: Actual LLM inference execution
- **Technology**: llama.cpp (optimized for CPU+GPU hybrid)
- **3 Instances Running**:

  **Instance 1 - Port 8080 (tiny-llama-1.1b)**
  - Size: 2.3 GB
  - Latency: 50-100ms (ultra-fast)
  - Use: Quick responses, fallback, demo
  - Context: 2K tokens

  **Instance 2 - Port 8081 (BiMediX2-8B)**
  - Size: 6.5 GB
  - Latency: 500-1000ms (medical domain)
  - Use: General medical questions
  - Trained on: Medical literature
  - Context: 4K tokens

  **Instance 3 - Port 8084 (OpenInsurance-8B)**
  - Size: 7.8 GB
  - Latency: 600-1200ms (insurance claims)
  - Use: Insurance/claims analysis
  - Training: Insurance documents
  - Context: 8K tokens

### 5. Persistence Layer

**PostgreSQL Database**:
- **Purpose**: Task history, user management, audit logs
- **Connection**: asyncpg (async driver)
- **Key Tables**:
  - `tasks` - Task metadata and results
  - `users` - User accounts and permissions
  - `audit_logs` - Access audit trail
  - `model_metrics` - Performance tracking

**Redis (Optional)**:
- **Purpose**: Persistent queue, session caching
- **Use Cases**:
  - Task queue durability
  - Horizontal scaling
  - Multi-machine deployment
  - Result caching optimization

### 6. Monitoring & Observability

**Prometheus Metrics**:
- Queue depth by priority
- Task processing time (p50, p95, p99)
- Task success/failure rates
- GPU utilization and temperature
- Model-specific latency
- API response times

**Logging**:
- Structured JSON logs
- Log levels: DEBUG, INFO, WARNING, ERROR
- Centralized log aggregation (optional)

**Health Checks**:
- `/healthz` - Basic HTTP health
- `/v1/async/health` - Queue health
- `/v1/gpu/status` - GPU status
- Database connectivity tests

## Data Flow Examples

### Example 1: Single Inference Request

```
User Request
    ↓
POST /v1/async/submit {agent_type, messages, priority}
    ↓
[API Gateway validates request]
    ↓
[Create task, assign UUID, store in queue]
    ↓
Response: {status: "queued", task_id: "abc123", position: 1}
    ↓
[Async worker picks task from priority queue]
    ↓
[GPU Orchestrator selects optimal model]
    ↓
[Send to selected server (8080/8081/8084)]
    ↓
[Model inference executes]
    ↓
[Result cached in queue manager]
    ↓
GET /v1/async/result/abc123
    ↓
Response: {status: "completed", result: {...}, inference_time_ms: 750}
```

### Example 2: Batch Processing with Priority

```
POST /v1/async/submit-batch [5 requests]
├─ Request 1: priority=HIGH   → queue position 1
├─ Request 2: priority=NORMAL → queue position 4
├─ Request 3: priority=HIGH   → queue position 2
├─ Request 4: priority=NORMAL → queue position 5
└─ Request 5: priority=NORMAL → queue position 6

[After 100ms timeout or 8 tasks, batch collation occurs]
    ↓
[HIGH priority requests processed first]
    ↓
[Then NORMAL priority]
    ↓
GET /v1/async/batch-status/batch-id
    ↓
Response: {
  batch_id: "batch-123",
  total: 5,
  completed: 3,
  processing: 1,
  queued: 1,
  progress_percent: 60
}
```

### Example 3: Adaptive Load Balancing

```
High Load Scenario (GPU Memory 85%):
    ↓
[GPU Orchestrator detects CRITICAL memory pressure]
    ↓
[Filter: Only models fitting in remaining 3.6GB]
    ↓
[Only tiny-llama-1.1b (2.3GB) fits]
    ↓
[Route ALL incoming tasks to port 8080]
    ↓
[Reduce batch size from 8 to 1]
    ↓
[Process sequentially, one at a time]
    ↓
[As memory is freed, gradually:
 - Increase batch size
 - Unlock larger models
 - Return to normal operation
]
```

## Performance Characteristics

### Latency Breakdown (per request)

```
Total Latency = Queue Wait + Inference + Data Transfer

Queue Wait Time:
├─ If queued: 0-5000ms (depends on queue depth)
└─ If no queue: 0ms (immediate)

Inference Time (by model):
├─ tiny-llama-1.1b: 50-100ms (100 tokens)
├─ BiMediX2-8B: 500-1000ms (100 tokens)
└─ OpenInsurance-8B: 600-1200ms (100 tokens)

Data Transfer: <10ms (local network)

TOTAL: 50ms (best case) → 6200ms (worst case)
```

### Throughput Capacity

```
Memory Configuration:
├─ Free GPU RAM: 24GB total
├─ Models loaded: 3 × ~7GB = ~16.6GB
├─ Available for batch: ~7.4GB
└─ Effective working: ~6GB (reserve 1.4GB)

Batch Capacity:
├─ tiny-llama: 4 requests/batch
├─ BiMediX2: 1 request/batch
└─ OpenInsurance: 1 request/batch

Theoretical Throughput:
├─ All tiny-llama: 480 req/min (8 per 100ms batch)
├─ All BiMediX2: 60 req/min (1 per 1000ms)
└─ Mixed workload: 100-200 req/min
```

## Failure Modes & Recovery

### Failure Mode 1: Model Server Crash
```
Detection: GPU Orchestrator gets connection timeout
Recovery:
  1. Mark model as unavailable
  2. Route to remaining healthy models
  3. Log incident
  4. Attempt auto-restart (configurable)
  5. Alert operations team
Impact: Graceful degradation (reduced throughput)
```

### Failure Mode 2: GPU Out of Memory
```
Detection: Model server OOM error
Recovery:
  1. Pause new task acceptance
  2. Drain existing queue
  3. Kill largest model (free 7.8GB)
  4. Restart remaining models
  5. Resume with smaller batch size
Impact: <30 sec downtime, reduced capacity
```

### Failure Mode 3: Database Unavailable
```
Detection: Connection pool exhaustion
Recovery:
  1. Queue tasks in-memory (loss if restart)
  2. Continue serving cached results
  3. Block task submission (API returns 503)
  4. Reconnect when DB available
  5. Sync pending tasks
Impact: Write operations blocked, reads cached
```

### Failure Mode 4: Queue Overflow
```
Detection: Queue size > 1000 tasks
Recovery:
  1. Pause task submission (return 429)
  2. Increase worker concurrency
  3. Scale to secondary GPU (if available)
  4. Activate emergency mode:
     - Only HIGH/CRITICAL priority
     - Increase batch size
     - Reduce inference timeout
Impact: Fair queueing, no OOM
```

## Security Architecture

### Authentication & Authorization
```
┌─────────────────────┐
│  Request comes in   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Extract JWT token   │
│ from Authorization  │
│ header              │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Verify signature    │
│ (HS256)             │
│ with secret key     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Check claims:       │
│ - exp (expiry)      │
│ - sub (subject)     │
│ - scope (permissions)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Check role/scope    │
│ against endpoint    │
│ requirements        │
└──────────┬──────────┘
           │
           ├─ Valid → Allow request
           │
           └─ Invalid → Return 403 Forbidden
```

### API Key Management
- Keys stored in `.env.production` (never in code)
- Rotated every 90 days
- Rate limited per key
- Logged and audited

### Data Protection
- TLS/SSL for all traffic (encrypted in transit)
- No sensitive data in logs
- Database credentials encrypted
- Model outputs not stored permanently

## Deployment Topologies

### Single Machine (Current)
```
┌─────────────────────────────┐
│  Single 4x GPU Server       │
│  RTX 3090, 256GB RAM        │
├─────────────────────────────┤
│ - FastAPI (4 workers)       │
│ - 3x llama.cpp instances    │
│ - PostgreSQL                │
│ - Prometheus                │
└─────────────────────────────┘
```

### Multi-GPU (Future)
```
┌──────────────────────┐   ┌──────────────────────┐
│  GPU Machine 1       │   │  GPU Machine 2       │
│  RTX 3090, 256GB     │   │  RTX 3090, 256GB     │
├──────────────────────┤   ├──────────────────────┤
│ - FastAPI x4 workers │   │ - Task workers       │
│ - llama.cpp x3       │   │ - llama.cpp x3       │
│ - Load balancer      │   │ - Cache sync         │
└──────┬───────────────┘   └──────┬───────────────┘
       │                          │
       └──────────────┬───────────┘
                      │
                 ┌────▼────┐
                 │ Shared   │
                 │ Redis QQ │
                 │ Database │
                 └──────────┘
```

### Kubernetes (Enterprise)
```
Namespace: medical-ai
├─ API Deployment (3 replicas)
├─ Worker Deployment (2 replicas)
├─ StatefulSet: PostgreSQL
├─ ConfigMap: Configuration
├─ Secret: Credentials
├─ PVC: Model storage
├─ Service: LoadBalancer
└─ Ingress: TLS termination
```

## Next Steps for Production

1. ✅ **Code Complete** - All components implemented
2. ✅ **Testing** - Single-machine load testing (8-10 tasks)
3. ⏳ **Scale Testing** - 100-1000 concurrent tasks
4. ⏳ **Production Config** - Set ALLOW_INSECURE_DEV=false
5. ⏳ **Secrets Management** - Use Vault/K8s secrets
6. ⏳ **Monitoring Deployment** - Full Prometheus/Grafana setup
7. ⏳ **Backup Strategy** - Database snapshots, model caching
8. ⏳ **Disaster Recovery** - RTO <5min, RPO <1hour
9. ⏳ **Documentation** - Complete runbooks
10. ⏳ **Team Training** - Operations team training

---

See also:
- [ASYNC_TASK_QUEUE_GUIDE.md](./ASYNC_TASK_QUEUE_GUIDE.md) - Detailed queue documentation
- [PRODUCTION_DEPLOYMENT.md](./PRODUCTION_DEPLOYMENT.md) - Deployment procedures
- [QUICK_REFERENCE.md](./QUICK_REFERENCE.md) - Operations quick reference
