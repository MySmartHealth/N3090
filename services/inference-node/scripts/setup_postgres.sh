#!/bin/bash
# PostgreSQL + pgvector setup for medical AI platform

set -e

echo "🗄️  Setting up PostgreSQL with pgvector for RAG..."

# Install PostgreSQL if not present
if ! command -v psql &> /dev/null; then
    echo "Installing PostgreSQL..."
    sudo apt update
    sudo apt install -y postgresql postgresql-contrib postgresql-server-dev-all
fi

# Start PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Install pgvector extension
echo "Installing pgvector extension..."
if [ ! -d "/tmp/pgvector" ]; then
    cd /tmp
    git clone --branch v0.7.4 https://github.com/pgvector/pgvector.git
    cd pgvector
    make
    sudo make install
fi

# Create database and user
echo "Creating database and user..."
sudo -u postgres psql -c "CREATE DATABASE medical_ai;" 2>/dev/null || echo "Database already exists"
sudo -u postgres psql -c "CREATE USER medical_ai WITH PASSWORD 'medical_ai_pass';" 2>/dev/null || echo "User already exists"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE medical_ai TO medical_ai;"
sudo -u postgres psql -d medical_ai -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Configure PostgreSQL for performance
echo "Configuring PostgreSQL for vector workloads..."
PG_CONF="/etc/postgresql/$(psql --version | grep -oP '\d+' | head -1)/main/postgresql.conf"

sudo tee -a "$PG_CONF" > /dev/null <<EOF

# Performance tuning for vector search
shared_buffers = 4GB
effective_cache_size = 12GB
maintenance_work_mem = 2GB
work_mem = 256MB
max_connections = 100
EOF

# Restart PostgreSQL
sudo systemctl restart postgresql

echo "✅ PostgreSQL with pgvector installed successfully!"
echo ""
echo "📝 Connection Details:"
echo "   Database: medical_ai"
echo "   User: medical_ai"
echo "   Password: medical_ai_pass"
echo "   URL: postgresql+asyncpg://medical_ai:medical_ai_pass@localhost:5432/medical_ai"
echo ""
echo "🔧 Next steps:"
echo "   1. Update DATABASE_URL in .env.production"
echo "   2. Run: python -c 'from app.database import init_db; import asyncio; asyncio.run(init_db())'"
echo "   3. Create admin user: python scripts/create_admin.py"
