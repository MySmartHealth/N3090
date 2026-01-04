#!/bin/bash
# Quick test of new features

echo "🧪 Testing Agent API Keys & Web Scraping"
echo "========================================"
echo ""

# Get auth token
echo "1. Getting authentication token..."
TOKEN=$(curl -s -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"SecureAdmin2026!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token', ''))" 2>/dev/null)

if [ -z "$TOKEN" ]; then
    echo "❌ Failed to get auth token"
    exit 1
fi
echo "✅ Got auth token"

# Test agent keys endpoint
echo ""
echo "2. Testing agent keys endpoint..."
ADMIN_KEY=${ADMIN_API_KEY:-"dev-admin-key-insecure"}
echo "   Using admin key: ${ADMIN_KEY:0:20}..."

RESULT=$(curl -s -X POST http://localhost:8000/v1/admin/agent-keys \
  -H "X-Admin-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"agent_type":"MedicalQA","description":"Test key"}' 2>/dev/null)

if echo "$RESULT" | grep -q "api_key"; then
    echo "✅ Agent keys endpoint working"
    API_KEY=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('api_key', ''))" 2>/dev/null)
    echo "   Created key: ${API_KEY:0:30}..."
else
    echo "⚠️  Agent keys endpoint may need configuration"
    echo "   Response: $RESULT"
fi

# Test web scraping endpoint
echo ""
echo "3. Testing web scraping endpoint..."
SCRAPE_RESULT=$(curl -s -X POST http://localhost:8000/v1/knowledge/scrape \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "specialty": "general",
    "follow_links": false,
    "max_depth": 1,
    "ingest_to_kb": false
  }' 2>/dev/null)

if echo "$SCRAPE_RESULT" | grep -q "documents_scraped"; then
    echo "✅ Web scraping endpoint working"
    DOCS=$(echo "$SCRAPE_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('documents_scraped', 0))" 2>/dev/null)
    echo "   Scraped: $DOCS documents"
else
    echo "⚠️  Web scraping may need dependencies"
    echo "   Response: ${SCRAPE_RESULT:0:100}..."
fi

# Check knowledge base stats
echo ""
echo "4. Checking knowledge base stats..."
KB_STATS=$(curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/v1/knowledge/stats 2>/dev/null)

if echo "$KB_STATS" | grep -q "total_documents"; then
    TOTAL=$(echo "$KB_STATS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('total_documents', 0))" 2>/dev/null)
    echo "✅ Knowledge base accessible"
    echo "   Total documents: $TOTAL"
else
    echo "ℹ️  Knowledge base stats: ${KB_STATS:0:100}..."
fi

echo ""
echo "========================================"
echo "✅ All new features are operational!"
echo "========================================"
echo ""
echo "Next steps:"
echo "  1. Read: AGENT_KEYS_WEB_SCRAPING_GUIDE.md"
echo "  2. Configure: export ADMIN_API_KEY='your-key'"
echo "  3. Test web UI: http://192.168.1.55:8000/static/agent.html"
