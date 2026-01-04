#!/bin/bash
# Setup Agent API Keys and Web Scraping Features
# Run this script to configure the new features

set -e

echo "================================================"
echo "Agent API Keys & Web Scraping Setup"
echo "================================================"
echo ""

# Check if running from correct directory
if [ ! -f "ecosystem.config.js" ]; then
    echo "❌ Error: Run this script from services/inference-node/"
    exit 1
fi

# Step 1: Install dependencies
echo "📦 Installing dependencies..."
pip install beautifulsoup4==4.12.3 PyPDF2==3.0.1 aiohttp==3.11.11

# Step 2: Configure admin API key
echo ""
echo "🔑 Configuring Admin API Key..."
if [ -z "$ADMIN_API_KEY" ]; then
    echo "⚠️  ADMIN_API_KEY not set in environment"
    echo "   Please set it:"
    echo "   export ADMIN_API_KEY='your-super-secret-admin-key-here'"
    echo ""
    read -p "Press Enter to continue with default dev key (NOT for production)..."
    export ADMIN_API_KEY="dev-admin-key-insecure"
fi

# Add to .env file if doesn't exist
if [ ! -f ".env" ]; then
    echo "ADMIN_API_KEY=$ADMIN_API_KEY" > .env
    echo "✅ Created .env file with ADMIN_API_KEY"
else
    if ! grep -q "ADMIN_API_KEY" .env; then
        echo "ADMIN_API_KEY=$ADMIN_API_KEY" >> .env
        echo "✅ Added ADMIN_API_KEY to .env"
    else
        echo "ℹ️  ADMIN_API_KEY already in .env"
    fi
fi

# Step 3: Restart API gateway
echo ""
echo "🔄 Restarting API gateway..."
pm2 restart api-gateway --update-env
sleep 3

# Step 4: Check API health
echo ""
echo "🏥 Checking API health..."
HEALTH=$(curl -s http://localhost:8000/healthz | python3 -c "import sys,json; print(json.load(sys.stdin).get('status', 'error'))" 2>/dev/null || echo "error")

if [ "$HEALTH" = "ok" ]; then
    echo "✅ API is healthy"
else
    echo "❌ API health check failed"
    pm2 logs api-gateway --lines 20 --nostream
    exit 1
fi

# Step 5: Create sample agent API keys
echo ""
echo "🔐 Creating sample agent API keys..."
echo "   (Using admin key: ${ADMIN_API_KEY:0:20}...)"
echo ""

TOKEN=$(curl -s -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"SecureAdmin2026!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null || echo "")

if [ -z "$TOKEN" ]; then
    echo "⚠️  Could not get auth token. Skipping agent key creation."
    echo "   You can create keys manually later."
else
    # Create agent keys for common agents
    AGENTS=("Claims" "MedicalQA" "Clinical")
    
    for AGENT in "${AGENTS[@]}"; do
        echo "Creating key for $AGENT agent..."
        RESULT=$(curl -s -X POST http://localhost:8000/v1/admin/agent-keys \
          -H "X-Admin-Key: $ADMIN_API_KEY" \
          -H "Content-Type: application/json" \
          -d "{\"agent_type\":\"$AGENT\",\"description\":\"API key for $AGENT agent\"}" 2>/dev/null || echo "")
        
        if [ -n "$RESULT" ]; then
            API_KEY=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('api_key', ''))" 2>/dev/null || echo "")
            if [ -n "$API_KEY" ]; then
                echo "✅ $AGENT: ${API_KEY:0:30}..."
                # Save to file for reference
                echo "$AGENT=$API_KEY" >> .agent_keys
            else
                echo "⚠️  Failed to create key for $AGENT"
            fi
        fi
    done
    
    if [ -f ".agent_keys" ]; then
        echo ""
        echo "📝 Agent keys saved to .agent_keys"
        echo "   Keep this file secure!"
    fi
fi

# Step 6: Test web scraping
echo ""
echo "🌐 Testing web scraping (optional)..."
read -p "Test web scraping? (y/N): " TEST_SCRAPE

if [ "$TEST_SCRAPE" = "y" ] || [ "$TEST_SCRAPE" = "Y" ]; then
    echo "Scraping sample URL..."
    
    SCRAPE_RESULT=$(curl -s -X POST http://localhost:8000/v1/knowledge/scrape \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d '{
        "url": "https://www.cdc.gov/diabetes/basics/index.html",
        "specialty": "endocrinology",
        "doc_type": "guideline",
        "follow_links": false,
        "max_depth": 1,
        "ingest_to_kb": true
      }' 2>/dev/null || echo "")
    
    if [ -n "$SCRAPE_RESULT" ]; then
        SCRAPED=$(echo "$SCRAPE_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('documents_scraped', 0))" 2>/dev/null || echo "0")
        INGESTED=$(echo "$SCRAPE_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('documents_ingested', 0))" 2>/dev/null || echo "0")
        
        echo "✅ Scraped: $SCRAPED documents"
        echo "✅ Ingested: $INGESTED documents"
    else
        echo "⚠️  Scraping test failed"
    fi
else
    echo "ℹ️  Skipping web scraping test"
fi

# Summary
echo ""
echo "================================================"
echo "✅ Setup Complete!"
echo "================================================"
echo ""
echo "New Features Available:"
echo ""
echo "1. 🔐 Agent API Keys:"
echo "   - Create: POST /v1/admin/agent-keys"
echo "   - List: GET /v1/admin/agent-keys"
echo "   - Delete: DELETE /v1/admin/agent-keys/{agent_type}"
echo ""
echo "2. 🌐 Web Scraping:"
echo "   - Single URL: POST /v1/knowledge/scrape"
echo "   - Multiple URLs: POST /v1/knowledge/scrape-multi"
echo "   - Medical guidelines: POST /v1/knowledge/scrape-medical-guidelines"
echo ""
echo "3. 📚 Documentation:"
echo "   - Guide: AGENT_KEYS_WEB_SCRAPING_GUIDE.md"
echo "   - Examples: See guide for full usage examples"
echo ""
echo "Admin API Key: ${ADMIN_API_KEY:0:30}..."
echo ""
if [ -f ".agent_keys" ]; then
    echo "Agent Keys: Saved in .agent_keys file"
    echo ""
fi
echo "Next Steps:"
echo "  1. Read AGENT_KEYS_WEB_SCRAPING_GUIDE.md"
echo "  2. Configure agent keys for production"
echo "  3. Scrape medical content for knowledge base"
echo "  4. Test agentic interface: http://192.168.1.55:8000/static/agent.html"
echo ""
echo "================================================"
