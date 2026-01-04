#!/bin/bash
# Quick start script for fine-tuning Claims OCR agent
# This script demonstrates the complete workflow from data to trained model

set -e  # Exit on error

echo "=========================================="
echo "CLAIMS OCR AGENT - FINE-TUNING QUICKSTART"
echo "=========================================="
echo ""

# Check if we're in the right directory
if [ ! -f "training/finetune_lora.py" ]; then
    echo "❌ Error: Run this script from the inference-node directory"
    exit 1
fi

# Check for HuggingFace format models
echo "🔍 Checking for HuggingFace format models..."
BIMEDIX_HF="models/hf/BiMediX2-8B"
OPENINS_HF="models/hf/openinsurancellm-llama3-8b"
BIOMISTRAL_HF="models/biomistral-7b-fp16"

if [ ! -d "$BIMEDIX_HF" ] && [ ! -d "$OPENINS_HF" ]; then
    echo ""
    echo "⚠️  WARNING: HuggingFace format models not found!"
    echo ""
    echo "Your current models are GGUF format (for inference only)."
    echo "Fine-tuning requires HuggingFace format (PyTorch) models."
    echo ""
    echo "Options:"
    echo "  1. Download HuggingFace models: ./training/download_base_models.sh"
    echo "  2. Use BioMistral (already available): $BIOMISTRAL_HF"
    echo ""
    read -p "Download required models now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        ./training/download_base_models.sh
    else
        echo "Exiting. Run ./training/download_base_models.sh when ready."
        exit 0
    fi
fi

echo "✅ HuggingFace models found or downloaded"
echo ""

# Step 1: Install dependencies
echo "📦 Step 1: Installing training dependencies..."
pip install -q -r training/requirements.txt
echo "   ✅ Dependencies installed"
echo ""

# Step 2: Prepare sample data (or use your own)
echo "📊 Step 2: Preparing training data..."

if [ -f "training/sample_claims_data.csv" ]; then
    python training/prepare_data.py \
        --claims_csv training/sample_claims_data.csv \
        --output_dir data/training \
        --split
    echo "   ✅ Training data prepared"
else
    echo "   ⚠️  No sample data found. Using your claims CSV..."
    echo "   Please provide --claims_csv path to your historical claims data"
fi
echo ""

# Step 3: Fine-tune BiMediX (medical analysis)
echo "🩺 Step 3: Fine-tuning BiMediX for medical entity validation..."

# Determine which BiMediX path to use
if [ -d "$BIMEDIX_HF" ]; then
    BIMEDIX_PATH="$BIMEDIX_HF"
    echo "   Using: $BIMEDIX_PATH"
else
    echo "   ⚠️  BiMediX HF model not found, skipping..."
    BIMEDIX_PATH=""
fi

if [ -n "$BIMEDIX_PATH" ]; then
    echo "   Model: BiMediX2-8B"
    echo "   GPU: RTX 3090 (24GB)"
    echo "   Time: ~4-5 hours for 1000 examples"
    echo ""

    read -p "Start BiMediX training? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        python training/finetune_lora.py \
            --base_model "$BIMEDIX_PATH" \
            --dataset "data/training/bimedix_medical_analysis_train.jsonl" \
            --output_dir "models/bimedix-claims-lora" \
            --lora_rank 16 \
            --lora_alpha 32 \
            --epochs 3 \
            --batch_size 4 \
            --learning_rate 2e-4 \
            --logging_steps 10 \
            --save_steps 50
        
        echo "   ✅ BiMediX fine-tuning complete!"
    fi
fi
echo ""

# Step 4: Fine-tune OpenInsurance (claims adjudication)
echo "📋 Step 4: Fine-tuning OpenInsurance for claims adjudication..."

# Determine which OpenInsurance path to use
if [ -d "$OPENINS_HF" ]; then
    OPENINS_PATH="$OPENINS_HF"
    echo "   Using: $OPENINS_PATH"
else
    echo "   ⚠️  OpenInsurance HF model not found, skipping..."
    OPENINS_PATH=""
fi

if [ -n "$OPENINS_PATH" ]; then
    echo "   Model: OpenInsurance-Llama3-8B"
    echo "   GPU: RTX 3060 (12GB) or RTX 3090 (24GB)"
    echo "   Time: ~5-6 hours for 1000 examples"
    echo ""

    read -p "Start OpenInsurance training? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        python training/finetune_lora.py \
            --base_model "$OPENINS_PATH" \
            --dataset "data/training/openins_adjudication_train.jsonl" \
            --output_dir "models/openins-adjudication-lora" \
            --lora_rank 16 \
            --lora_alpha 32 \
            --epochs 3 \
            --batch_size 4 \
            --learning_rate 2e-4 \
            --logging_steps 10 \
            --save_steps 50
        
        echo "   ✅ OpenInsurance fine-tuning complete!"
    fi
fi
echo ""

# Step 5: View training progress
echo "=========================================="
echo "✅ FINE-TUNING COMPLETE!"
echo "=========================================="
echo ""
echo "📁 Fine-tuned models saved to:"
echo "   - models/bimedix-claims-lora/"
echo "   - models/openins-adjudication-lora/"
echo ""
echo "📈 View training progress:"
echo "   tensorboard --logdir models/bimedix-claims-lora/logs"
echo "   tensorboard --logdir models/openins-adjudication-lora/logs"
echo ""
echo "🧪 Next steps:"
echo "   1. Evaluate models on test set"
echo "   2. Convert to GGUF for llama.cpp deployment"
echo "   3. Update model_router.py to use fine-tuned models"
echo "   4. A/B test vs baseline models"
echo ""
echo "🚀 Ready to deploy fine-tuned Claims OCR agent!"
