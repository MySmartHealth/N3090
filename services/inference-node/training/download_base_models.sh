#!/bin/bash
# Download base models in HuggingFace format for fine-tuning
# GGUF models cannot be fine-tuned - we need the original unquantized models

set -e

echo "=========================================="
echo "DOWNLOAD BASE MODELS FOR FINE-TUNING"
echo "=========================================="
echo ""
echo "Current models are GGUF format (for llama.cpp inference)"
echo "Fine-tuning requires HuggingFace format (unquantized PyTorch models)"
echo ""

# Check if git-lfs is installed
if ! command -v git-lfs &> /dev/null; then
    echo "📦 Installing git-lfs (required for large model files)..."
    sudo apt-get update -qq
    sudo apt-get install -y git-lfs
    git lfs install
fi

# Create models directory if it doesn't exist
mkdir -p models/hf

echo "Available models to download:"
echo ""
echo "1. BiMediX2-8B (BioMedical AI)"
echo "   Source: RajeshRGupta/BiMediX2-8B"
echo "   Size: ~16GB (FP16)"
echo "   Use for: Medical entity validation, clinical Q&A"
echo ""
echo "2. OpenInsurance Llama3-8B"
echo "   Source: starmpcc/openinsurancellm-llama3-8b"  
echo "   Size: ~16GB (FP16)"
echo "   Use for: Claims adjudication, insurance policy"
echo ""
echo "3. BioMistral-7B"
echo "   Source: BioMistral/BioMistral-7B"
echo "   Size: ~14GB (FP16)"
echo "   Use for: AI Scribe, clinical documentation"
echo ""

# Function to download model
download_model() {
    local model_id=$1
    local model_name=$2
    local model_dir="models/hf/${model_name}"
    
    if [ -d "$model_dir" ]; then
        echo "✅ Model already exists: $model_dir"
        return
    fi
    
    echo "📥 Downloading ${model_name}..."
    echo "   From: https://huggingface.co/${model_id}"
    echo "   To: $model_dir"
    echo ""
    
    # Clone the model repository
    git lfs install
    git clone https://huggingface.co/${model_id} ${model_dir}
    
    echo "✅ Downloaded: ${model_name}"
    echo ""
}

# Download BiMediX2-8B
echo "=========================================="
read -p "Download BiMediX2-8B? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    download_model "RajeshRGupta/BiMediX2-8B" "BiMediX2-8B"
fi

# Download OpenInsurance Llama3-8B
echo "=========================================="
read -p "Download OpenInsurance-Llama3-8B? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    download_model "starmpcc/openinsurancellm-llama3-8b" "openinsurancellm-llama3-8b"
fi

# Download BioMistral-7B
echo "=========================================="
read -p "Download BioMistral-7B? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    download_model "BioMistral/BioMistral-7B" "BioMistral-7B"
fi

echo ""
echo "=========================================="
echo "✅ MODEL DOWNLOAD COMPLETE"
echo "=========================================="
echo ""
echo "📁 HuggingFace models saved to: models/hf/"
echo ""
echo "🎯 Next steps for fine-tuning:"
echo ""
echo "1. Prepare training data:"
echo "   python training/prepare_data.py --claims_csv YOUR_DATA.csv --split"
echo ""
echo "2. Fine-tune BiMediX:"
echo "   python training/finetune_lora.py \\"
echo "     --base_model models/hf/BiMediX2-8B \\"
echo "     --dataset data/training/bimedix_medical_analysis_train.jsonl \\"
echo "     --output_dir models/bimedix-claims-lora \\"
echo "     --epochs 3 --batch_size 4"
echo ""
echo "3. Fine-tune OpenInsurance:"
echo "   python training/finetune_lora.py \\"
echo "     --base_model models/hf/openinsurancellm-llama3-8b \\"
echo "     --dataset data/training/openins_adjudication_train.jsonl \\"
echo "     --output_dir models/openins-adjudication-lora \\"
echo "     --epochs 3 --batch_size 4"
echo ""
echo "💡 Tip: Use --use_4bit flag if you have limited GPU memory (enables QLoRA)"
