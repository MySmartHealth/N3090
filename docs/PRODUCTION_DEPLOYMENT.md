# Production Deployment Playbook

## Pre-Deployment Checklist

### 1. Environment Configuration

```bash
# Create production .env file
cat > .env.production << 'EOF'
# Database
DATABASE_URL=postgresql+asyncpg://postgres:YOUR_STRONG_PASSWORD@your-db-host:5432/medical_ai_prod
DB_ECHO=false
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10
DB_POOL_RECYCLE=3600

# Security
JWT_SECRET_KEY=YOUR_STRONG_SECRET_KEY_MIN_32_CHARS
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24
ALLOW_INSECURE_DEV=false

# API Configuration
API_WORKERS=4
API_HOST=0.0.0.0
API_PORT=8000
API_TIMEOUT=60
CORS_ORIGINS=["https://your-frontend-domain.com"]

# Model Configuration
PREFERRED_BACKEND=llama.cpp
VLLM_ENABLED=true
VLLM_TENSOR_PARALLEL=1
LLAMA_CPP_INSTANCES=3
DEFAULT_MODEL=tiny-llama-1b

# Async Task Queue
QUEUE_MAX_SIZE=1000
QUEUE_BATCH_SIZE=8
QUEUE_BATCH_TIMEOUT_MS=100
QUEUE_RESULT_TTL_SECONDS=300
TASK_DEFAULT_TIMEOUT_SECONDS=60

# Redis (Optional but recommended)
REDIS_URL=redis://your-redis-host:6379/0
REDIS_PASSWORD=YOUR_REDIS_PASSWORD
REDIS_DB=0

# Monitoring
PROMETHEUS_ENABLED=true
LOG_LEVEL=INFO
LOG_FORMAT=json
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id

# Maintenance
ENABLE_MAINTENANCE_MODE=false
MAINTENANCE_MESSAGE="System undergoing maintenance"
EOF
```

### 2. Database Setup

```bash
# Run migrations
./scripts/migrate_database.sh

# Verify database connection
psql postgresql://postgres:PASSWORD@your-db-host:5432/medical_ai_prod -c "SELECT version();"

# Create indexing for task queue
psql postgresql://postgres:PASSWORD@your-db-host:5432/medical_ai_prod << 'EOF'
CREATE INDEX idx_tasks_status ON tasks(status) WHERE status IN ('queued', 'processing');
CREATE INDEX idx_tasks_priority ON tasks(priority) WHERE status = 'queued';
CREATE INDEX idx_tasks_created_at ON tasks(created_at);
CREATE INDEX idx_tasks_agent_type ON tasks(agent_type);
EOF
```

### 3. GPU Driver Verification

```bash
# Verify NVIDIA GPU drivers
nvidia-smi

# Expected output:
# - NVIDIA-SMI 535.x or higher
# - CUDA Capability: RTX 3090 (compute 8.6)
# - Memory: 24 GB

# Install/update drivers if needed
# Ubuntu/Debian:
sudo apt update
sudo apt install -y nvidia-driver-535
sudo reboot

# Verify CUDA toolkit
nvcc --version
```

### 4. Model Download & Caching

```bash
# Pre-download all models before deployment
cd services/inference-node

# Download tiny-llama (2.3 GB)
python bin/download_models.py --model tiny-llama-1.1b-chat-medical

# Download bi-medix2 (6.5 GB)
python bin/download_models.py --model BiMediX2-8B-hf

# Download openinsurance (7.8 GB)
python bin/download_models.py --model openinsurancellm-llama3-8b

# Verify downloaded models
ls -lh models/ | grep -E '\.gguf|\.safetensors'

# Expected space: ~16.6 GB
du -sh models/
```

### 5. Dependency Installation

```bash
# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# Install production dependencies
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# Install additional production tools
pip install gunicorn gevent-websocket redis celery

# Verify critical packages
python -c "import fastapi, sqlalchemy, asyncpg; print('✓ Core packages OK')"
```

### 6. SSL/TLS Certificates

```bash
# Option 1: Use Let's Encrypt (recommended)
sudo certbot certonly --standalone -d your-api-domain.com

# Option 2: Use self-signed (development only)
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes

# Verify certificate
openssl x509 -in /etc/letsencrypt/live/your-api-domain.com/fullchain.pem -text -noout
```

### 7. Redis Setup (Optional but Recommended)

```bash
# Install Redis
sudo apt install -y redis-server

# Configure for production
sudo cp /etc/redis/redis.conf /etc/redis/redis.conf.backup
sudo tee /etc/redis/redis.conf > /dev/null << 'EOF'
# Redis Production Configuration
port 6379
bind 0.0.0.0
protected-mode yes
timeout 0
tcp-backlog 511

# Persistence
save 900 1
save 300 10
save 60 10000
appendonly yes
appendfilename "appendonly.aof"

# Memory management
maxmemory 4gb
maxmemory-policy allkeys-lru

# Slow log
slowlog-log-slower-than 10000
slowlog-max-len 128

# Logging
loglevel notice
EOF

# Start Redis
sudo systemctl restart redis-server
sudo systemctl enable redis-server

# Verify Redis
redis-cli ping
# Expected: PONG

# Check memory
redis-cli info memory
```

## Deployment Steps

### Step 1: Health Pre-checks

```bash
#!/bin/bash
# pre-deploy-checks.sh

echo "=== Pre-Deployment Health Checks ==="

# Check database connectivity
echo "Checking database..."
psql $DATABASE_URL -c "SELECT 1;" || exit 1
echo "✓ Database connected"

# Check GPU availability
echo "Checking GPU..."
nvidia-smi -L || exit 1
echo "✓ GPU available"

# Check disk space (need 50GB free)
DISK_SPACE=$(df /home | awk '{print $4}' | tail -1)
if [ $DISK_SPACE -lt 52428800 ]; then
  echo "✗ Insufficient disk space: ${DISK_SPACE}KB available"
  exit 1
fi
echo "✓ Disk space adequate"

# Check models are downloaded
if [ ! -f models/tiny-llama-1.1b-chat-medical.fp16.gguf ]; then
  echo "✗ Models not downloaded"
  exit 1
fi
echo "✓ Models present"

echo "=== All pre-checks passed ==="
```

### Step 2: Start Services

```bash
#!/bin/bash
# start-production.sh

set -e

cd /home/dgs/N3090/services/inference-node
source .venv/bin/activate

echo "=== Starting Model Servers ==="

# Start llama.cpp servers in background
for PORT in 8080 8081 8084; do
  MODEL=""
  case $PORT in
    8080) MODEL="models/tiny-llama-1.1b-chat-medical.fp16.gguf" ;;
    8081) MODEL="models/BiMediX2-8B-hf" ;;
    8084) MODEL="models/openinsurancellm-llama3-8b.Q5_K_M.gguf" ;;
  esac
  
  nohup ./bin/llama-server -m $MODEL -p $PORT > /tmp/llama-$PORT.log 2>&1 &
  echo "Started llama.cpp on port $PORT (PID: $!)"
done

# Wait for servers to start
sleep 5

# Verify servers are responding
for PORT in 8080 8081 8084; do
  for i in {1..10}; do
    if curl -s http://localhost:$PORT/health > /dev/null; then
      echo "✓ Server on port $PORT is healthy"
      break
    fi
    sleep 1
  done
done

echo "=== Starting FastAPI Application ==="

# Start main application with 4 workers
nohup uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --timeout-keep-alive 75 \
  --timeout-notify 30 \
  --log-config logging.json \
  > /tmp/api.log 2>&1 &

API_PID=$!
echo "Started FastAPI (PID: $API_PID)"

# Wait for API to start
sleep 3

# Health check
for i in {1..10}; do
  if curl -s http://localhost:8000/healthz > /dev/null; then
    echo "✓ API is healthy"
    break
  fi
  sleep 1
done

echo "=== Deployment Complete ==="
echo "API running on: http://0.0.0.0:8000"
echo "Metrics available at: http://0.0.0.0:8000/metrics"
echo "Task queue API: http://0.0.0.0:8000/v1/async/*"
echo "GPU monitoring: http://0.0.0.0:8000/v1/gpu/*"
```

### Step 3: Reverse Proxy Configuration (Nginx)

```nginx
# /etc/nginx/sites-available/medical-api

upstream api {
    least_conn;
    server localhost:8000 max_fails=3 fail_timeout=30s;
}

upstream metrics {
    server localhost:8000;
}

server {
    listen 443 ssl http2;
    server_name your-api-domain.com;
    
    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/your-api-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-api-domain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    
    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-XSS-Protection "1; mode=block" always;
    
    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
    limit_req_zone $http_x_api_key zone=key_limit:10m rate=100r/s;
    
    location / {
        limit_req zone=api_limit burst=20 nodelay;
        
        proxy_pass http://api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # Buffering
        proxy_buffering off;
        proxy_request_buffering off;
    }
    
    # Metrics endpoint (internal only)
    location /metrics {
        allow 10.0.0.0/8;
        allow 172.16.0.0/12;
        allow 192.168.0.0/16;
        deny all;
        
        proxy_pass http://metrics;
    }
    
    # Health check endpoint
    location /healthz {
        access_log off;
        proxy_pass http://api;
    }
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name your-api-domain.com;
    return 301 https://$server_name$request_uri;
}
```

### Step 4: Monitoring Setup

```yaml
# prometheus.yml - Prometheus configuration

global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'medical-api'
    static_configs:
      - targets: ['localhost:8000']
    scrape_interval: 10s
    
  - job_name: 'node-exporter'
    static_configs:
      - targets: ['localhost:9100']
    
  - job_name: 'gpu-metrics'
    static_configs:
      - targets: ['localhost:9445']

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['localhost:9093']
```

```yaml
# alerts.yml - Alerting rules

groups:
  - name: medical-api
    rules:
      - alert: HighQueueDepth
        expr: task_queue_depth > 500
        for: 5m
        annotations:
          summary: "Queue depth exceeds 500 tasks"
          
      - alert: HighGPUTemperature
        expr: gpu_temperature_celsius > 80
        for: 2m
        annotations:
          summary: "GPU temperature exceeds 80°C"
          
      - alert: HighTaskFailureRate
        expr: task_failure_rate > 0.05
        for: 10m
        annotations:
          summary: "Task failure rate exceeds 5%"
          
      - alert: APIDown
        expr: up{job="medical-api"} == 0
        for: 1m
        annotations:
          summary: "Medical API is down"
```

## Load Testing

```bash
#!/bin/bash
# load-test.sh

# Load test with Apache Bench
ab -n 1000 -c 10 http://localhost:8000/healthz

# Load test task queue with 500 concurrent submissions
cat > load_test_tasks.py << 'EOF'
import asyncio
import httpx
import time
from statistics import mean, stdev

async def submit_task(client, task_num):
    payload = {
        "agent_type": "Chat",
        "messages": [{"role": "user", "content": f"Load test query {task_num}"}],
        "priority": "NORMAL" if task_num % 5 != 0 else "HIGH",
        "timeout_seconds": 60
    }
    
    start = time.time()
    response = await client.post(
        "http://localhost:8000/v1/async/submit",
        json=payload
    )
    latency = (time.time() - start) * 1000
    
    return {
        "task_id": response.json().get("task_id"),
        "status": response.status_code,
        "latency_ms": latency
    }

async def main():
    async with httpx.AsyncClient(timeout=30) as client:
        tasks = [submit_task(client, i) for i in range(500)]
        results = await asyncio.gather(*tasks)
    
    latencies = [r["latency_ms"] for r in results]
    success = sum(1 for r in results if r["status"] == 200)
    
    print(f"Submitted: 500")
    print(f"Successful: {success}")
    print(f"Success Rate: {success/500*100:.1f}%")
    print(f"Avg Latency: {mean(latencies):.1f}ms")
    print(f"P95 Latency: {sorted(latencies)[int(len(latencies)*0.95)]:.1f}ms")
    print(f"P99 Latency: {sorted(latencies)[int(len(latencies)*0.99)]:.1f}ms")

asyncio.run(main())
EOF

python load_test_tasks.py
```

## Monitoring Commands

```bash
# Watch queue status in real-time
watch -n 1 'curl -s http://localhost:8000/v1/async/stats | jq .queue'

# Watch GPU status
watch -n 1 'curl -s http://localhost:8000/v1/gpu/status | jq .gpu'

# Monitor API logs
tail -f /tmp/api.log | grep -E "ERROR|WARNING|CRITICAL"

# Check system resources
watch -n 1 'free -h && echo "---" && nvidia-smi --query-gpu=memory.used,memory.total,temperature.gpu --format=csv,noheader'

# Analyze performance
curl http://localhost:8000/metrics | grep 'task_processing_time_ms'
```

## Graceful Shutdown

```bash
#!/bin/bash
# graceful-shutdown.sh

echo "Initiating graceful shutdown..."

# Signal API to stop accepting new tasks
curl -X POST http://localhost:8000/admin/maintenance \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -d '{"maintenance_mode": true}'

# Wait for in-flight requests to complete
echo "Waiting for in-flight requests (timeout: 30s)..."
sleep 30

# Kill API process
pkill -f "uvicorn app.main"

# Kill model servers
pkill -f "llama-server"

echo "Shutdown complete"
```

## Rollback Procedure

```bash
#!/bin/bash
# rollback.sh

# Stop current version
./graceful-shutdown.sh

# Restore previous database backup
pg_restore -d medical_ai_prod /backup/database-backup-$(date -d "1 day ago" +%Y%m%d).sql

# Restore previous code version
git checkout previous-stable-tag
source .venv/bin/activate
pip install -r requirements.txt

# Restart services
./start-production.sh

echo "Rollback complete"
```

## Maintenance Tasks

### Daily
- Monitor queue depth and failure rate
- Check GPU temperature trends
- Review error logs for anomalies

### Weekly
- Run database VACUUM ANALYZE
- Clean up old completed tasks (>7 days)
- Test backup and restore procedures

### Monthly
- Review performance metrics
- Update models if newer versions available
- Conduct security audit
- Review and rotate API keys

---

For issues during deployment, check:
1. `/tmp/api.log` - Application logs
2. `/tmp/llama-*.log` - Model server logs
3. System resources: `free -h`, `nvidia-smi`
4. Network connectivity: `curl http://localhost:8000/healthz`
