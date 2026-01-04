#!/bin/bash
# Production Deployment Verification Checklist
# Run this script before deploying to production

set -e

echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║   PRODUCTION DEPLOYMENT VERIFICATION CHECKLIST                     ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""

PASSED=0
FAILED=0
WARNINGS=0

check_pass() {
    echo "  ✓ PASS: $1"
    ((PASSED++))
}

check_fail() {
    echo "  ✗ FAIL: $1"
    ((FAILED++))
}

check_warn() {
    echo "  ⚠ WARN: $1"
    ((WARNINGS++))
}

# ========================================================================
# 1. API Service Checks
# ========================================================================
echo "1️⃣  API SERVICE CHECKS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if curl -s http://localhost:8000/healthz > /dev/null 2>&1; then
    check_pass "API health endpoint responding"
else
    check_fail "API not responding on port 8000"
fi

if ps aux | grep -q "uvicorn app.main:app" | grep -v grep; then
    check_pass "API process running"
else
    check_fail "API process not running"
fi

# ========================================================================
# 2. Model Server Checks
# ========================================================================
echo ""
echo "2️⃣  MODEL SERVER CHECKS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

for PORT in 8080 8081 8084; do
    if curl -s http://localhost:$PORT/health > /dev/null 2>&1; then
        check_pass "Model server on port $PORT responding"
    else
        check_fail "Model server on port $PORT not responding"
    fi
done

# ========================================================================
# 3. Async Queue Checks
# ========================================================================
echo ""
echo "3️⃣  ASYNC QUEUE CHECKS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

QUEUE_RESPONSE=$(curl -s http://localhost:8000/v1/async/stats 2>/dev/null)
if echo "$QUEUE_RESPONSE" | grep -q "queue"; then
    check_pass "Async queue API responding"
else
    check_fail "Async queue API not responding"
fi

# ========================================================================
# 4. GPU Checks
# ========================================================================
echo ""
echo "4️⃣  GPU CHECKS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if command -v nvidia-smi &> /dev/null; then
    check_pass "NVIDIA GPU drivers installed"
    
    TEMP=$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader | head -1)
    if [ "$TEMP" -lt 70 ]; then
        check_pass "GPU temperature normal ($TEMP°C)"
    elif [ "$TEMP" -lt 80 ]; then
        check_warn "GPU temperature elevated ($TEMP°C)"
    else
        check_fail "GPU temperature critical ($TEMP°C)"
    fi
else
    check_fail "NVIDIA GPU drivers not installed"
fi

GPU_STATUS=$(curl -s http://localhost:8000/v1/gpu/status 2>/dev/null)
if echo "$GPU_STATUS" | grep -q "gpu"; then
    check_pass "GPU monitoring endpoint responding"
else
    check_fail "GPU monitoring endpoint not responding"
fi

# ========================================================================
# 5. Database Checks (Optional)
# ========================================================================
echo ""
echo "5️⃣  DATABASE CHECKS (OPTIONAL)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -z "$DATABASE_URL" ]; then
    check_warn "DATABASE_URL not set (optional - API works without it)"
else
    if psql -c "SELECT 1;" > /dev/null 2>&1; then
        check_pass "Database connection working"
    else
        check_warn "Database connection failed (optional)"
    fi
fi

# ========================================================================
# 6. Security Checks
# ========================================================================
echo ""
echo "6️⃣  SECURITY CHECKS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if grep -q "ALLOW_INSECURE_DEV=false" /home/dgs/N3090/services/inference-node/.env.production; then
    check_pass "ALLOW_INSECURE_DEV set to false"
else
    check_fail "ALLOW_INSECURE_DEV not set to false"
fi

JWT_SECRET=$(grep "JWT_SECRET_KEY" /home/dgs/N3090/services/inference-node/.env.production | cut -d= -f2)
if [ ${#JWT_SECRET} -gt 32 ]; then
    check_pass "JWT_SECRET_KEY is strong (${#JWT_SECRET} chars)"
else
    check_fail "JWT_SECRET_KEY is too short"
fi

# ========================================================================
# 7. System Resource Checks
# ========================================================================
echo ""
echo "7️⃣  SYSTEM RESOURCE CHECKS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

FREE_MEM=$(free -h | awk '/^Mem:/ {print $7}')
check_pass "Free memory: $FREE_MEM"

DISK_USAGE=$(df -h / | awk '/\/$/ {print $5}')
if [ "${DISK_USAGE%\%}" -lt 90 ]; then
    check_pass "Disk usage: $DISK_USAGE"
else
    check_fail "Disk usage critical: $DISK_USAGE"
fi

# ========================================================================
# 8. Load Test
# ========================================================================
echo ""
echo "8️⃣  LOAD TEST (10 CONCURRENT TASKS)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

LOAD_TEST_RESULT=$(curl -s -X POST http://localhost:8000/v1/async/submit \
  -H "Content-Type: application/json" \
  -d '{"agent_type":"Chat","messages":[{"role":"user","content":"Test"}],"priority":"NORMAL"}' 2>/dev/null)

if echo "$LOAD_TEST_RESULT" | grep -q "task_id"; then
    check_pass "Task submission working"
else
    check_fail "Task submission failed"
fi

# ========================================================================
# 9. Documentation Checks
# ========================================================================
echo ""
echo "9️⃣  DOCUMENTATION CHECKS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

for doc in "ASYNC_TASK_QUEUE_GUIDE.md" "PRODUCTION_DEPLOYMENT.md" "QUICK_REFERENCE.md"; do
    if [ -f "/home/dgs/N3090/docs/$doc" ]; then
        check_pass "Documentation exists: $doc"
    else
        check_fail "Documentation missing: $doc"
    fi
done

# ========================================================================
# SUMMARY
# ========================================================================
echo ""
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║   VERIFICATION SUMMARY                                             ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""
echo "  ✓ Passed:  $PASSED"
echo "  ✗ Failed:  $FAILED"
echo "  ⚠ Warnings: $WARNINGS"
echo ""

if [ $FAILED -eq 0 ]; then
    echo "✅ SYSTEM READY FOR PRODUCTION DEPLOYMENT"
    echo ""
    echo "Next steps:"
    echo "  1. Review Nginx configuration: /home/dgs/N3090/docs/nginx.conf"
    echo "  2. Setup reverse proxy with SSL"
    echo "  3. Configure Prometheus: /home/dgs/N3090/docs/prometheus.yml"
    echo "  4. Setup Grafana dashboards"
    echo "  5. Load test with 100+ concurrent tasks"
    echo "  6. Monitor system for 24 hours before full rollout"
    exit 0
else
    echo "❌ SYSTEM NOT READY FOR PRODUCTION"
    echo "Fix the above failures before deploying."
    exit 1
fi
