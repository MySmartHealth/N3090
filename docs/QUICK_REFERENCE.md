# Medical AI Inference System - Quick Reference Card

## System Status Commands

| Command | Purpose | Expected Output |
|---------|---------|-----------------|
| `curl http://localhost:8000/healthz` | API health | `{"status":"ok"}` |
| `curl http://localhost:8000/v1/async/stats \| jq` | Queue status | 4 queued, 0 processing |
| `curl http://localhost:8000/v1/gpu/status \| jq` | GPU status | Memory 50%, Temp 49°C |
| `nvidia-smi` | GPU details | RTX 3090 24GB, 49°C |
| `tail -f /tmp/api.log` | Application logs | No ERROR entries |
| `ps aux \| grep uvicorn` | API process | 4 workers running |

## Task Submission Examples

### Single Task
```bash
curl -X POST http://localhost:8000/v1/async/submit \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "Chat",
    "messages": [{"role": "user", "content": "Your question here"}],
    "priority": "NORMAL"
  }' | jq .
```

### Batch Submission (5 tasks)
```bash
curl -X POST http://localhost:8000/v1/async/submit-batch \
  -H "Content-Type: application/json" \
  -d '{
    "requests": [
      {"agent_type":"Chat","messages":[{"role":"user","content":"Q1"}]},
      {"agent_type":"Chat","messages":[{"role":"user","content":"Q2"}]},
      {"agent_type":"Chat","messages":[{"role":"user","content":"Q3"}]},
      {"agent_type":"Chat","messages":[{"role":"user","content":"Q4"}]},
      {"agent_type":"Chat","messages":[{"role":"user","content":"Q5"}]}
    ]
  }' | jq .
```

### Check Status
```bash
# Replace TASK_ID with actual task ID
curl http://localhost:8000/v1/async/status/TASK_ID | jq .status
```

### Get Result
```bash
curl http://localhost:8000/v1/async/result/TASK_ID | jq .result.content
```

### Monitor Queue
```bash
# Real-time queue monitoring
watch -n 1 'curl -s http://localhost:8000/v1/async/stats | jq .queue'
```

## Performance Monitoring

### Key Metrics
```bash
# Throughput (tasks per minute)
curl http://localhost:8000/v1/async/stats | jq '.performance.throughput_tasks_per_minute'

# Average processing time (ms)
curl http://localhost:8000/v1/async/stats | jq '.performance.avg_processing_time_ms'

# Average wait time (ms)
curl http://localhost:8000/v1/async/stats | jq '.performance.avg_wait_time_ms'

# GPU memory utilization
curl http://localhost:8000/v1/gpu/status | jq '.gpu.utilization_percent'

# GPU temperature
curl http://localhost:8000/v1/gpu/status | jq '.gpu.temperature_c'
```

### Health Indicators

| Metric | Healthy | Warning | Critical |
|--------|---------|---------|----------|
| Queue Depth | <100 | 100-500 | >500 |
| Avg Latency | <2000ms | 2-5s | >5s |
| Failure Rate | <1% | 1-5% | >5% |
| GPU Temp | <70°C | 70-80°C | >80°C |
| GPU Memory | <85% | 85-95% | >95% |
| Success Rate | >99% | 95-99% | <95% |

## Troubleshooting Flowchart

```
Problem: API not responding

1. Check if API is running:
   ps aux | grep uvicorn
   
   - Not running → Start API (see Startup section)
   - Running → Continue to step 2

2. Check API logs:
   tail -f /tmp/api.log | grep ERROR
   
   - Database error → Verify DATABASE_URL and connection
   - Model error → Verify model servers running on ports 8080, 8081, 8084
   - No errors → Continue to step 3

3. Check system resources:
   free -h           # RAM usage
   nvidia-smi        # GPU status
   df -h /           # Disk space
   
   - Low resources → Scale down or restart services
   - Good → Check network connectivity

4. Test endpoints:
   curl http://localhost:8000/healthz
   curl http://localhost:8000/v1/async/stats
   curl http://localhost:8000/v1/gpu/status
   
   - Some work, some don't → Problem with specific component
   - None work → Network or port binding issue
```

## Startup Checklist

```bash
# 1. Activate virtual environment
source /home/dgs/N3090/services/inference-node/.venv/bin/activate

# 2. Verify environment variables
echo $DATABASE_URL
echo $JWT_SECRET_KEY

# 3. Start model servers (background)
cd /home/dgs/N3090/services/inference-node
./bin/manage_vllm.sh start 2>&1 &

# 4. Wait for model servers
sleep 10
curl http://localhost:8080/health  # Should work

# 5. Start API
cd /home/dgs/N3090/services/inference-node
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4 > /tmp/api.log 2>&1 &

# 6. Wait for API
sleep 5
curl http://localhost:8000/healthz

# 7. Verify system
curl http://localhost:8000/v1/async/stats | jq .
curl http://localhost:8000/v1/gpu/status | jq .gpu
```

## Emergency Procedures

### Queue Overload (>1000 tasks)
```bash
# 1. Stop accepting new requests
curl -X POST http://localhost:8000/v1/admin/pause-queue \
  -H "Authorization: Bearer $JWT_TOKEN"

# 2. Monitor queue drain
watch -n 5 'curl -s http://localhost:8000/v1/async/stats | jq .queue.total_tasks'

# 3. Once drained, resume
curl -X POST http://localhost:8000/v1/admin/resume-queue \
  -H "Authorization: Bearer $JWT_TOKEN"
```

### GPU Temperature Critical (>85°C)
```bash
# 1. Pause inference
curl -X POST http://localhost:8000/v1/admin/pause-inference \
  -H "Authorization: Bearer $JWT_TOKEN"

# 2. Stop model servers
pkill -f "llama-server"
pkill -f "vllm"

# 3. Monitor temperature
watch -n 2 nvidia-smi

# 4. Once cooled (<70°C), restart
# (Wait ~5-10 minutes for full cool down)

# 5. Restart model servers
./bin/manage_vllm.sh start

# 6. Resume inference
curl -X POST http://localhost:8000/v1/admin/resume-inference \
  -H "Authorization: Bearer $JWT_TOKEN"
```

### Out of Memory Error
```bash
# 1. Check memory usage
curl http://localhost:8000/v1/gpu/status | jq '.gpu.memory_used_gb'

# 2. Clean up old task results
curl -X POST "http://localhost:8000/v1/async/cleanup?max_age_seconds=300" \
  -H "Authorization: Bearer $JWT_TOKEN"

# 3. Kill smallest model server (free 2.3GB)
pkill -f "llama-server.*8080"

# 4. Monitor memory recovery
watch -n 2 'nvidia-smi'

# 5. Restart model if needed
./bin/manage_vllm.sh start --only-tiny
```

### Database Connection Lost
```bash
# 1. Check connection string
echo $DATABASE_URL

# 2. Test database directly
psql $DATABASE_URL -c "SELECT 1;"

# 3. If connection fails:
#    - Verify PostgreSQL is running
#    - Check network connectivity to DB host
#    - Verify credentials
#    - Check firewall rules

# 4. Restart API once DB is accessible
pkill -f "uvicorn app.main"
sleep 5
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/api.log 2>&1 &
```

## Performance Tuning

### For Higher Throughput
```bash
# Increase batch size (more tasks processed together)
# In .env.production:
QUEUE_BATCH_SIZE=12  # From default 8

# Reduce batch timeout (less waiting)
QUEUE_BATCH_TIMEOUT_MS=50   # From default 100

# Increase workers (more parallel processing)
# When starting API:
uvicorn app.main:app --workers 8  # From default 4
```

### For Lower Latency
```bash
# Reduce batch size (process tasks faster)
QUEUE_BATCH_SIZE=4   # From default 8

# Increase batch timeout (wait less)
QUEUE_BATCH_TIMEOUT_MS=100  # Unchanged

# Use llama.cpp exclusively (lower latency)
PREFERRED_BACKEND=llama.cpp

# Use smaller models
DEFAULT_MODEL=tiny-llama-1b
```

### For Lower Memory Usage
```bash
# Reduce concurrent models
LLAMA_CPP_INSTANCES=2  # From default 3

# Reduce batch size
QUEUE_BATCH_SIZE=4     # From default 8

# Kill largest models
pkill -f "llama-server.*8084"  # OpenInsurance 8B
```

## API Rate Limits

| Endpoint | Limit | Window |
|----------|-------|--------|
| `/v1/async/submit` | 100 req/s | 1 second |
| `/v1/async/submit-batch` | 50 req/s | 1 second |
| `/v1/async/status/*` | 200 req/s | 1 second |
| `/v1/gpu/*` | 100 req/s | 1 second |

## Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| `Task not found` | Task expired (>5min old) | Results kept 5 min by default |
| `Queue full` | >1000 tasks queued | Wait or scale up |
| `GPU out of memory` | Models exceed 24GB | Restart, kill largest model |
| `Task timeout` | Inference took >60s | Increase timeout_seconds |
| `Model not found` | Model server not running | Check `./bin/manage_vllm.sh status` |
| `Database connection error` | DB unreachable | Check DATABASE_URL and network |

## Log File Locations

| Service | Log File | Command |
|---------|----------|---------|
| API | `/tmp/api.log` | `tail -f /tmp/api.log` |
| Model Server 8080 | `/tmp/llama-8080.log` | `tail -f /tmp/llama-8080.log` |
| Model Server 8081 | `/tmp/llama-8081.log` | `tail -f /tmp/llama-8081.log` |
| Model Server 8084 | `/tmp/llama-8084.log` | `tail -f /tmp/llama-8084.log` |
| System | `/var/log/syslog` | `tail -f /var/log/syslog` |

## Useful Aliases (Add to ~/.bashrc)

```bash
# API monitoring
alias api-status='curl -s http://localhost:8000/healthz | jq'
alias api-logs='tail -f /tmp/api.log'
alias queue-depth='curl -s http://localhost:8000/v1/async/stats | jq .queue.total_tasks'
alias gpu-status='curl -s http://localhost:8000/v1/gpu/status | jq .gpu'

# Model server management
alias models-status='ps aux | grep llama-server | grep -v grep'
alias models-restart='pkill -f llama-server; sleep 5; ./bin/manage_vllm.sh start'

# System monitoring
alias sys-status='free -h && echo "---" && nvidia-smi && echo "---" && df -h /'
```

---

**For detailed documentation, see:**
- [ASYNC_TASK_QUEUE_GUIDE.md](./ASYNC_TASK_QUEUE_GUIDE.md) - Full async queue documentation
- [PRODUCTION_DEPLOYMENT.md](./PRODUCTION_DEPLOYMENT.md) - Production deployment guide
- [GPU_LOAD_BALANCING.md](./GPU_LOAD_BALANCING.md) - GPU load balancing details

**Support:** Contact your DevOps team or check logs first.
