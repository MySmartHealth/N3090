#!/bin/bash

# ═══════════════════════════════════════════════════════════════════════════════
# Production Startup Script
# ═══════════════════════════════════════════════════════════════════════════════
# Comprehensive script to start the Medical AI inference node in production

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}════════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Medical AI Inference Node - Production Startup${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════════════════════${NC}"
echo ""

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
APP_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="/var/log/medical_ai"
PID_FILE="/var/run/medical_ai/inference.pid"

# Ensure required directories exist
mkdir -p "$LOG_DIR"
mkdir -p "/var/run/medical_ai"
mkdir -p "/tmp/translation_logs"
chmod 755 "$LOG_DIR"
chmod 755 "/var/run/medical_ai"
chmod 755 "/tmp/translation_logs"

# ═══════════════════════════════════════════════════════════════════════════════
# Load Environment
# ═══════════════════════════════════════════════════════════════════════════════

echo -e "${BLUE}1️⃣  Loading environment configuration...${NC}"

if [ -f "$APP_DIR/.env.production" ]; then
    set -o allexport
    source "$APP_DIR/.env.production"
    set +o allexport
    echo -e "${GREEN}✅ Production environment loaded${NC}"
else
    echo -e "${RED}❌ .env.production not found${NC}"
    echo "   Create it from .env.production.example:"
    echo "   cp .env.production.example .env.production"
    exit 1
fi

# Verify critical environment variables
if [ -z "$DATABASE_URL" ]; then
    echo -e "${RED}❌ DATABASE_URL not set${NC}"
    exit 1
fi

if [ -z "$JWT_SECRET" ]; then
    echo -e "${RED}❌ JWT_SECRET not set${NC}"
    exit 1
fi

echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# Health Checks
# ═══════════════════════════════════════════════════════════════════════════════

echo -e "${BLUE}2️⃣  Running pre-startup checks...${NC}"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 not found${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Python 3 available${NC}"

# Check virtual environment
if [ -z "$VIRTUAL_ENV" ] && [ -d "$APP_DIR/.venv" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment not activated${NC}"
    echo "   Activating: source $APP_DIR/.venv/bin/activate"
    source "$APP_DIR/.venv/bin/activate"
fi

# Check database connectivity
echo -n "   Testing database connection... "
python3 << EOF
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine

async def test_db():
    try:
        engine = create_async_engine(os.getenv('DATABASE_URL'), echo=False)
        async with engine.begin() as conn:
            await conn.execute(__import__('sqlalchemy').text("SELECT 1"))
        print("OK")
    except Exception as e:
        print(f"FAILED: {e}")
        exit(1)

asyncio.run(test_db())
EOF

echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# Database Migration
# ═══════════════════════════════════════════════════════════════════════════════

echo -e "${BLUE}3️⃣  Running database migrations...${NC}"

# Check if migration script exists
if [ -f "$SCRIPT_DIR/migrate_database.sh" ]; then
    echo "   Running schema migration..."
    bash "$SCRIPT_DIR/migrate_database.sh" || true
else
    echo -e "${YELLOW}⚠️  Migration script not found${NC}"
fi

echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# Create Admin User (if first run)
# ═══════════════════════════════════════════════════════════════════════════════

echo -e "${BLUE}4️⃣  Checking admin user...${NC}"

python3 << EOF
import asyncio
import os

async def check_admin():
    try:
        from app.database import AsyncSessionLocal, User, create_admin_user
        from sqlalchemy import select
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(User).where(User.is_admin == True))
            admin = result.scalar_one_or_none()
            
            if admin:
                print(f"✅ Admin user exists: {admin.username}")
            else:
                print("⚠️  No admin user found")
                print("   Create one after startup with:")
                print("   psql -c \"UPDATE users SET is_admin=true WHERE username='your_user'\"")
                
    except Exception as e:
        print(f"⚠️  Admin check skipped: {e}")

asyncio.run(check_admin())
EOF

echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# Start Application
# ═══════════════════════════════════════════════════════════════════════════════

echo -e "${BLUE}5️⃣  Starting Medical AI Inference Node...${NC}"
echo ""

# Set default values if not set
: ${WORKERS:=4}
: ${HOST:=0.0.0.0}
: ${PORT:=8000}
: ${LOG_LEVEL:=INFO}

echo "Configuration:"
echo "  Host: $HOST"
echo "  Port: $PORT"
echo "  Workers: $WORKERS"
echo "  Environment: $ENVIRONMENT"
echo "  Log Level: $LOG_LEVEL"
echo "  Logs: $LOG_DIR/inference.log"
echo ""

# Save PID
echo $$ > "$PID_FILE"

# Start application with proper logging
cd "$APP_DIR"

# Use gunicorn for production (if available) or uvicorn
if command -v gunicorn &> /dev/null; then
    echo -e "${GREEN}Starting with Gunicorn...${NC}"
    exec gunicorn \
        --workers $WORKERS \
        --worker-class uvicorn.workers.UvicornWorker \
        --bind $HOST:$PORT \
        --access-logfile "$LOG_DIR/access.log" \
        --error-logfile "$LOG_DIR/error.log" \
        --log-level ${LOG_LEVEL,,} \
        --timeout 120 \
        app.main:app
else
    echo -e "${GREEN}Starting with Uvicorn...${NC}"
    exec python3 -m uvicorn \
        --host $HOST \
        --port $PORT \
        --workers $WORKERS \
        --log-level ${LOG_LEVEL,,} \
        app.main:app
fi

# Cleanup
rm -f "$PID_FILE"
