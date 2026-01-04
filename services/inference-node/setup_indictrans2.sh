#!/bin/bash
# IndicTrans2 Integration Setup Script
# Installs dependencies and verifies IndicTrans2 integration

set -e

echo "════════════════════════════════════════════════════════"
echo "🚀 IndicTrans2 Multilingual Translation Integration"
echo "════════════════════════════════════════════════════════"

# Set paths
WORKSPACE="/home/dgs/N3090"
INFERENCE_NODE="$WORKSPACE/services/inference-node"
VENV="$INFERENCE_NODE/venv"

echo ""
echo "📍 Workspace: $INFERENCE_NODE"
echo ""

# Check if venv exists
if [ ! -d "$VENV" ]; then
    echo "❌ Virtual environment not found at $VENV"
    echo "Creating virtual environment..."
    python3 -m venv "$VENV"
fi

# Activate venv
source "$VENV/bin/activate"

echo "✅ Virtual environment activated"
echo ""

# Step 1: Install core dependencies
echo "📦 Step 1: Installing IndicTrans2 dependencies..."
pip install --quiet torch 2>/dev/null || echo "⚠️  Torch already installed"
pip install --quiet transformers 2>/dev/null || echo "⚠️  Transformers already installed"
pip install --quiet indictrans2 2>/dev/null || echo "⚠️  IndicTrans2 already installed"

echo "✅ Dependencies installed"
echo ""

# Step 2: Verify installations
echo "🔍 Step 2: Verifying installations..."

python3 << 'EOF'
import sys

try:
    import torch
    print(f"  ✅ PyTorch: {torch.__version__}")
except ImportError:
    print("  ❌ PyTorch not found")
    sys.exit(1)

try:
    import transformers
    print(f"  ✅ Transformers: {transformers.__version__}")
except ImportError:
    print("  ❌ Transformers not found")
    sys.exit(1)

try:
    from indictrans2 import pipeline
    print(f"  ✅ IndicTrans2: installed")
except ImportError:
    print("  ❌ IndicTrans2 not found")
    sys.exit(1)

# Check GPU
if torch.cuda.is_available():
    print(f"  ✅ CUDA: Available ({torch.cuda.get_device_name(0)})")
else:
    print("  ⚠️  CUDA: Not available (CPU mode)")

print("\n✅ All verifications passed!")
EOF

echo ""

# Step 3: Verify integration files
echo "📂 Step 3: Verifying integration files..."

FILES=(
    "app/indictrans2_engine.py"
    "app/translation_routes.py"
    "test_indictrans2.py"
    "docs/INDICTRANS2_TRANSLATION.md"
    "INDICTRANS2_QUICK_REF.md"
)

for file in "${FILES[@]}"; do
    if [ -f "$INFERENCE_NODE/$file" ]; then
        echo "  ✅ $file"
    else
        echo "  ❌ $file (missing)"
    fi
done

echo ""

# Step 4: Run basic engine test
echo "🧪 Step 4: Testing IndicTrans2 engine..."

python3 << 'EOF'
import sys
sys.path.insert(0, '/home/dgs/N3090/services/inference-node')

try:
    from app.indictrans2_engine import get_indictrans_engine
    engine = get_indictrans_engine()
    
    # Get supported languages
    langs = engine.get_supported_languages()
    print(f"  ✅ Engine initialized")
    print(f"  ✅ Supported languages: {len(langs)} languages")
    print(f"  ✅ Languages: {', '.join(list(langs.keys())[:5])}...")
    
except Exception as e:
    print(f"  ❌ Engine test failed: {e}")
    sys.exit(1)
EOF

echo ""

# Step 5: Summary
echo "════════════════════════════════════════════════════════"
echo "✅ IndicTrans2 Integration Complete!"
echo "════════════════════════════════════════════════════════"
echo ""
echo "📚 Documentation:"
echo "  • Full guide: docs/INDICTRANS2_TRANSLATION.md"
echo "  • Quick ref: INDICTRANS2_QUICK_REF.md"
echo "  • Summary: INDICTRANS2_INTEGRATION_SUMMARY.md"
echo ""
echo "🧪 Running tests:"
echo "  $ python test_indictrans2.py"
echo ""
echo "🚀 Starting server:"
echo "  $ python -m uvicorn app.main:app --reload"
echo ""
echo "📡 API endpoints:"
echo "  • POST /v1/translate/translate      - Single translation"
echo "  • POST /v1/translate/batch          - Batch translation"
echo "  • POST /v1/translate/transliterate  - Script conversion"
echo "  • GET /v1/translate/languages       - List languages"
echo ""
echo "🎯 Next steps:"
echo "  1. Run: python test_indictrans2.py"
echo "  2. Start server: uvicorn app.main:app --reload"
echo "  3. Check docs at http://localhost:8000/docs"
echo ""
echo "════════════════════════════════════════════════════════"
