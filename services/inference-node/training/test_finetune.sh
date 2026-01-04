#!/bin/bash
# Test fine-tuning with BioMistral (already in HuggingFace format)
# This will work immediately without downloading additional models

set -e

echo "=========================================="
echo "TEST FINE-TUNING WITH BIOMISTRAL"
echo "=========================================="
echo ""
echo "This script demonstrates fine-tuning using BioMistral-7B"
echo "which you already have in HuggingFace format."
echo ""

# Check if BioMistral exists
if [ ! -d "models/biomistral-7b-fp16" ]; then
    echo "❌ Error: BioMistral model not found at models/biomistral-7b-fp16"
    exit 1
fi

echo "✅ Found BioMistral model: models/biomistral-7b-fp16"
echo ""

# Create minimal sample data for testing
echo "📝 Creating sample training data..."
mkdir -p data/training

cat > data/training/test_sample.jsonl << 'EOF'
{"instruction": "Analyze these medical entities for clinical accuracy:\n\n**Extracted Medical Data:**\n- Diagnosis Codes (ICD-10): E11.9, I10\n- Procedure Codes (CPT): 99213\n- Service Date: 12/01/2024\n\n**Assess:** Are these codes clinically appropriate for a routine office visit?", "output": "Clinical Assessment: E11.9 (Type 2 diabetes without complications) and I10 (Essential hypertension) are valid diagnoses. CPT 99213 (Office visit, established patient, moderate complexity) is appropriate for managing these chronic conditions. Medical necessity is confirmed for routine monitoring.", "metadata": {"claim_id": "TEST-001", "final_decision": "APPROVED"}}
{"instruction": "Analyze these medical entities for clinical accuracy:\n\n**Extracted Medical Data:**\n- Diagnosis Codes (ICD-10): J45.909\n- Procedure Codes (CPT): 99214\n- Service Date: 12/02/2024\n\n**Assess:** Are these codes clinically appropriate?", "output": "Clinical Assessment: J45.909 (Unspecified asthma, uncomplicated) is a valid diagnosis. CPT 99214 (Office visit, detailed) is appropriate for asthma management. Medical necessity confirmed for asthma control assessment. Coding is appropriate.", "metadata": {"claim_id": "TEST-002", "final_decision": "APPROVED"}}
EOF

echo "✅ Created sample training data: data/training/test_sample.jsonl"
echo "   (2 training examples for quick testing)"
echo ""

# Show training parameters
echo "🔧 Training Configuration:"
echo "   Base Model: models/biomistral-7b-fp16"
echo "   Dataset: data/training/test_sample.jsonl"
echo "   Output: models/biomistral-test-lora"
echo "   Epochs: 1 (for quick testing)"
echo "   Batch Size: 1"
echo "   LoRA Rank: 8 (smaller for faster training)"
echo ""
echo "⏱️  Expected Time: ~2-3 minutes (minimal data for testing)"
echo ""

read -p "Start test fine-tuning? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Exiting..."
    exit 0
fi

echo ""
echo "🚀 Starting fine-tuning..."
echo "=========================================="

# Install dependencies if needed
if ! python -c "import peft" 2>/dev/null; then
    echo "📦 Installing training dependencies..."
    pip install -q peft transformers datasets accelerate bitsandbytes tensorboard
fi

# Run fine-tuning
python training/finetune_lora.py \
    --base_model models/biomistral-7b-fp16 \
    --dataset data/training/test_sample.jsonl \
    --output_dir models/biomistral-test-lora \
    --lora_rank 8 \
    --lora_alpha 16 \
    --epochs 1 \
    --batch_size 1 \
    --gradient_accumulation 2 \
    --learning_rate 2e-4 \
    --logging_steps 1 \
    --save_steps 2

echo ""
echo "=========================================="
echo "✅ TEST FINE-TUNING COMPLETE!"
echo "=========================================="
echo ""
echo "📁 LoRA adapter saved to: models/biomistral-test-lora/"
echo ""
echo "🔍 Verify the output:"
echo "   ls -lh models/biomistral-test-lora/"
echo ""
echo "📈 View training logs:"
echo "   tensorboard --logdir models/biomistral-test-lora/logs"
echo ""
echo "✨ Next steps:"
echo "   1. This proves fine-tuning works on your system"
echo "   2. Prepare real training data (100+ examples)"
echo "   3. Download BiMediX/OpenInsurance for Claims OCR:"
echo "      ./training/download_base_models.sh"
echo "   4. Run full fine-tuning with your actual data"
echo ""
echo "🎉 Your system is ready for production fine-tuning!"
