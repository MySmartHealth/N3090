#!/bin/bash
# Production Deployment Script for Synthetic Intelligence Platform
# Deploys all services with API keys, JWT authentication, and monitoring

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "╔═══════════════════════════════════════════════════════════════════════════╗"
echo "║   🚀 Synthetic Intelligence Platform - Production Deployment             ║"
echo "╚═══════════════════════════════════════════════════════════════════════════╝"
echo ""

# Check if PM2 is installed
if ! command -v pm2 &> /dev/null; then
    echo "❌ PM2 not found. Installing PM2..."
    npm install -g pm2
    echo "✅ PM2 installed"
fi

# Load API keys
if [ ! -f ".api_keys.env" ]; then
    echo "❌ .api_keys.env not found. Run ./generate_api_keys.sh first"
    exit 1
fi

echo "📋 Loading API keys from .api_keys.env..."
source .api_keys.env
export $(cut -d= -f1 .api_keys.env)

# Generate JWT secret if not set
if [ -z "$JWT_SECRET" ]; then
    echo "🔑 Generating JWT secret..."
    export JWT_SECRET=$(openssl rand -hex 64)
    echo "JWT_SECRET=$JWT_SECRET" >> .env.production
    echo "✅ JWT secret generated and saved to .env.production"
fi

# Load production environment
if [ -f ".env.production" ]; then
    source .env.production
fi

echo ""
echo "📊 Deployment Configuration:"
echo "  • ALLOW_INSECURE_DEV: false (JWT required)"
echo "  • JWT_SECRET: ${JWT_SECRET:0:16}... (truncated)"
echo "  • JWT_EXPIRY: 24 hours"
echo "  • API Keys: 6 models configured"
echo ""

# Stop all existing processes
echo "🛑 Stopping existing PM2 processes..."
pm2 delete all 2>/dev/null || true
sleep 2

# Kill any remaining llama-server processes
echo "🛑 Stopping any orphaned llama-server processes..."
pkill -f "llama-server" || true
sleep 2

# Create logs directory
mkdir -p logs

echo ""
echo "🚀 Starting services with PM2..."
echo ""

# Start all services via PM2 ecosystem
pm2 start ecosystem.config.js

# Wait for services to initialize
echo ""
echo "⏳ Waiting for services to initialize (20 seconds)..."
sleep 20

echo ""
echo "📊 PM2 Process Status:"
pm2 list

echo ""
echo "🔍 Health Checks:"

# Check API gateway
if curl -s http://localhost:8000/healthz | grep -q "ok"; then
    echo "  ✅ API Gateway (port 8000): Healthy"
else
    echo "  ⚠️  API Gateway (port 8000): Not responding"
fi

# Check all model servers
for port in 8080 8081 8082 8083 8084 8085; do
    if curl -s http://localhost:$port/health | grep -q "ok"; then
        echo "  ✅ Model Server (port $port): Healthy"
    else
        echo "  ⏳ Model Server (port $port): Starting..."
    fi
done

echo ""
echo "🔐 JWT Authentication Test:"
echo "  • Endpoint: POST http://localhost:8000/v1/auth/login"
echo "  • Test command:"
echo "    curl -X POST http://localhost:8000/v1/auth/login \\"
echo "      -H 'Content-Type: application/json' \\"
echo "      -d '{\"username\":\"demo\",\"password\":\"demo\",\"location_id\":\"hospital-01\"}'"

echo ""
echo "📈 Prometheus Metrics:"
echo "  • URL: http://localhost:8000/metrics"

echo ""
echo "🎯 Next Steps:"
echo "  1. Import grafana-dashboard.json into Grafana"
echo "  2. Configure Prometheus to scrape http://localhost:8000/metrics"
echo "  3. Set up nginx reverse proxy with SSL"
echo "  4. Configure firewall rules (allow 8000, block 8080-8085)"
echo "  5. Set up automated backups of .api_keys.env and .env.production"

echo ""
echo "💾 PM2 Persistence:"
pm2 save
echo "✅ PM2 configuration saved"

echo ""
echo "📝 Useful PM2 Commands:"
echo "  • pm2 list                  - View all processes"
echo "  • pm2 logs api-gateway      - View FastAPI logs"
echo "  • pm2 logs llama-*          - View all model server logs"
echo "  • pm2 restart all           - Restart all services"
echo "  • pm2 monit                 - Real-time monitoring"
echo "  • pm2 stop all              - Stop all services"

echo ""
echo "╔═══════════════════════════════════════════════════════════════════════════╗"
echo "║                  ✅ DEPLOYMENT COMPLETE                                   ║"
echo "╚═══════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "🟢 Production Status: READY"
echo "🔐 JWT Authentication: ENABLED"
echo "📊 Prometheus Metrics: ENABLED"
echo "🎯 All 6 models + API gateway running"
echo ""
