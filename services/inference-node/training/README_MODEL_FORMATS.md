# Fine-Tuning Setup - Important Model Format Notes

## ⚠️ Model Format Issue

**Problem:** Your current models are in **GGUF format** (quantized for llama.cpp inference), but fine-tuning requires **HuggingFace format** (unquantized PyTorch models).

### Current Models (Inference Only)
```
models/
├── BiMediX2-8B-hf.i1-Q6_K.gguf          ❌ GGUF - Cannot fine-tune
├── openinsurancellm-llama3-8b.Q5_K_M.gguf  ❌ GGUF - Cannot fine-tune
├── BioMistral-Clinical-7B.Q8_0.gguf     ❌ GGUF - Cannot fine-tune
├── biomistral-7b-fp16/                  ✅ HuggingFace - Can fine-tune!
└── mixtral-8x7b-awq/                    ⚠️  AWQ quantized - Limited support
```

## Solution Options

### Option 1: Use BioMistral (Available Now) ✅

You already have BioMistral-7B in HuggingFace format! Use it for fine-tuning:

```bash
# Fine-tune BioMistral for AI Scribe
python training/finetune_lora.py \
  --base_model models/biomistral-7b-fp16 \
  --dataset data/training/scribe_clinical_docs_train.jsonl \
  --output_dir models/biomistral-scribe-lora \
  --epochs 3 --batch_size 4
```

**Note:** BioMistral is excellent for clinical documentation but not specialized for:
- Medical entity validation (BiMediX strength)
- Insurance claims adjudication (OpenInsurance strength)

### Option 2: Download HuggingFace Format Models

Download the original unquantized models for fine-tuning:

```bash
# Run the download script
./training/download_base_models.sh

# Models will be saved to models/hf/
# - BiMediX2-8B (~16GB)
# - openinsurancellm-llama3-8b (~16GB)  
# - BioMistral-7B (~14GB)
```

**Storage Required:** ~46GB for all three models

### Option 3: Convert GGUF to HuggingFace (Advanced)

GGUF models can be converted back to HuggingFace format, but this is lossy (quantization cannot be reversed):

```bash
# Not recommended - use Option 2 instead
# GGUF → HF conversion loses precision from quantization
```

## Recommended Workflow

### For Claims OCR Agent (BiMediX + OpenInsurance)

**Step 1: Download Base Models**
```bash
./training/download_base_models.sh
# Select: BiMediX2-8B and OpenInsurance-Llama3-8B
```

**Step 2: Prepare Training Data**
```bash
python training/prepare_data.py \
  --claims_csv YOUR_HISTORICAL_CLAIMS.csv \
  --output_dir data/training \
  --split
```

**Step 3: Fine-tune BiMediX (Medical Analysis)**
```bash
python training/finetune_lora.py \
  --base_model models/hf/BiMediX2-8B \
  --dataset data/training/bimedix_medical_analysis_train.jsonl \
  --output_dir models/bimedix-claims-lora \
  --epochs 3 \
  --batch_size 4 \
  --use_4bit  # Use QLoRA if limited memory
```

**Step 4: Fine-tune OpenInsurance (Adjudication)**
```bash
python training/finetune_lora.py \
  --base_model models/hf/openinsurancellm-llama3-8b \
  --dataset data/training/openins_adjudication_train.jsonl \
  --output_dir models/openins-adjudication-lora \
  --epochs 3 \
  --batch_size 4 \
  --use_4bit
```

### For AI Scribe Agent (BioMistral) - Works Now! ✅

**Step 1: Prepare Clinical Documents**
```bash
python training/prepare_data.py \
  --documents_csv YOUR_CLINICAL_DOCS.csv \
  --output_dir data/training \
  --split
```

**Step 2: Fine-tune BioMistral**
```bash
python training/finetune_lora.py \
  --base_model models/biomistral-7b-fp16 \
  --dataset data/training/scribe_clinical_docs_train.jsonl \
  --output_dir models/biomistral-scribe-lora \
  --epochs 3 \
  --batch_size 4
```

**This will work immediately since you already have BioMistral in HF format!**

## Model Format Comparison

| Format | Use Case | Fine-tuning | Inference Speed | File Size |
|--------|----------|-------------|-----------------|-----------|
| **HuggingFace (FP16)** | Training & Fine-tuning | ✅ Yes | Slower | Large (~16GB) |
| **GGUF (Quantized)** | Fast inference | ❌ No | Fast | Smaller (~5-8GB) |
| **AWQ (Quantized)** | GPU inference | ⚠️ Limited | Fast | Smaller (~4-5GB) |

## Storage Considerations

**Current Setup:**
- GGUF models: ~30GB (inference)
- HF BioMistral: ~14GB (can fine-tune)
- Total: ~44GB

**After Downloading HF Models:**
- GGUF models: ~30GB (keep for production inference)
- HF models: ~46GB (for fine-tuning)
- Fine-tuned LoRA adapters: ~500MB each
- Total: ~77GB

**Optimization:**
- Delete GGUF models after downloading HF versions (save 30GB)
- Keep HF models for future fine-tuning
- Convert fine-tuned models back to GGUF for production

## Quick Start (Using Available Models)

**Immediate Option - Fine-tune BioMistral for Scribe:**

```bash
# 1. Create sample clinical documents data
cat > sample_clinical_docs.csv << 'EOF'
dictation,document_type,final_document
"Patient is 45 year old male with hypertension BP 150/95. Start lisinopril 10mg daily.",prescription,"**PRESCRIPTION**\n\nPatient: 45-year-old male\nDiagnosis: Hypertension (I10)\n\nMedication: Lisinopril\nDosage: 10 mg\nRoute: Oral\nFrequency: Once daily\nQuantity: 30 tablets\nRefills: 3\n\nSpecial Instructions: Take with water in the morning. Monitor blood pressure regularly.\n\nPrescriber: _______________\nDate: _______________"
EOF

# 2. Prepare training data
python training/prepare_data.py \
  --documents_csv sample_clinical_docs.csv \
  --output_dir data/training \
  --split

# 3. Fine-tune BioMistral (WORKS NOW!)
python training/finetune_lora.py \
  --base_model models/biomistral-7b-fp16 \
  --dataset data/training/scribe_clinical_docs_train.jsonl \
  --output_dir models/biomistral-scribe-lora \
  --epochs 3 \
  --batch_size 4 \
  --learning_rate 2e-4

# 4. Monitor training
tensorboard --logdir models/biomistral-scribe-lora/logs
```

## Common Errors & Solutions

### Error: "models/BiMediX2-8B-hf is not a local folder"
**Cause:** Trying to fine-tune a GGUF model  
**Solution:** Download HuggingFace version or use biomistral-7b-fp16

### Error: "CUDA out of memory"
**Cause:** Model too large for GPU  
**Solution:** Use `--use_4bit` flag for QLoRA (4-bit quantization)

### Error: "Repository Not Found"
**Cause:** Model name doesn't exist on HuggingFace  
**Solution:** Use local path (models/biomistral-7b-fp16) or download first

## Summary

**What You Can Do Right Now:**
✅ Fine-tune BioMistral for AI Scribe (you have this in HF format)

**What Requires Download:**
⏳ Fine-tune BiMediX for medical entity validation (~16GB download)
⏳ Fine-tune OpenInsurance for claims adjudication (~16GB download)

**Recommended Path:**
1. Test fine-tuning with BioMistral first (works immediately)
2. Download BiMediX and OpenInsurance if you need Claims OCR fine-tuning
3. Keep GGUF models for production inference (fast)
4. Use HF models only for training (slow inference but trainable)

---

Run `./training/download_base_models.sh` to get the missing HuggingFace models.
