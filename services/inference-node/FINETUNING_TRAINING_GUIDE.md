# Fine-Tuning & Training Guide - Medical AI Agents

## Current State: Zero-Shot Pre-trained Models

**Current Setup:**
- ✅ Using off-the-shelf pre-trained models
- ✅ No domain-specific fine-tuning yet
- ✅ Relying on general medical/insurance knowledge
- ⏳ **Opportunity:** Fine-tune on your specific data for 10-50% accuracy improvement

## Why Fine-Tune?

### 1. **Claims OCR Agent** (BiMediX + OpenInsurance)
**Current:** Generic medical/insurance knowledge  
**After Fine-tuning:** 
- Learns your specific policy rules
- Adapts to your claim formats
- Understands your coding patterns
- Reduces false positives/negatives by 30-50%

### 2. **AI Scribe Agent** (BioMistral)
**Current:** Generic clinical documentation  
**After Fine-tuning:**
- Matches your hospital's documentation style
- Uses your preferred medical terminology
- Follows your template formats
- Reduces editing time by 40-60%

### 3. **All Agents**
- Better accuracy on your specific use cases
- Faster inference (smaller, specialized models)
- Lower hallucination rates
- Compliance with your workflows

## Training Data Requirements

### For Claims OCR Agent

#### 1. Historical Claims Data
```
Required Data (Minimum):
- 1,000+ processed claims (approved/denied)
- OCR text + structured entities
- Adjudication decisions with reasoning
- Policy ID and coverage details

Ideal Data (Optimal):
- 10,000+ claims across multiple years
- Mix of approved (70%), denied (20%), pending (10%)
- Multiple policy types and coverage tiers
- Adjudicator notes and reasoning
```

**Example Training Sample:**
```json
{
  "claim_id": "CLM-2024-12345",
  "ocr_text": "Patient John Doe... [full OCR text]",
  "extracted_entities": {
    "diagnosis_codes": ["E11.9", "I10"],
    "procedure_codes": ["99213"],
    "claim_amount": "150.00"
  },
  "medical_analysis_label": "ICD-10 codes valid. CPT 99213 appropriate for managing chronic conditions. Medical necessity confirmed.",
  "adjudication_label": "APPROVED",
  "adjudication_reasoning": "Covered benefit, routine office visit, within policy limits, no prior auth required.",
  "policy_id": "POL-12345",
  "adjudicator_notes": "Standard approval for chronic disease management"
}
```

#### 2. Policy Documentation
```
Required:
- All active insurance policy documents
- Coverage rules and exclusion lists
- Prior authorization requirements
- Fee schedules and limits
- Network provider lists
```

#### 3. Medical Coding Resources
```
Required:
- ICD-10 code database with descriptions
- CPT code database with descriptions
- Common diagnosis-procedure pairings
- Your organization's coding guidelines
```

### For AI Scribe Agent

#### 1. Clinical Documentation Examples
```
Required Data:
- 500+ prescription examples (actual, de-identified)
- 500+ discharge summary examples
- 500+ SOAP note examples
- 500+ procedure note examples

Format:
{
  "dictation": "Patient 45 year old male with hypertension...",
  "document_type": "prescription",
  "final_document": "**PRESCRIPTION**\nPatient: ...",
  "physician_edits": ["Changed dosage from 5mg to 10mg"],
  "quality_score": 4.5
}
```

#### 2. Template Library
- Standardized templates for each document type
- Preferred formatting guidelines
- Required sections and fields
- Compliance requirements

## Fine-Tuning Strategies

### Strategy 1: LoRA (Low-Rank Adaptation) ⭐ RECOMMENDED

**Best for:** Quick fine-tuning with limited data and resources

**Advantages:**
- ✅ Requires only 1-5% of parameters to train
- ✅ Fast training (hours vs days)
- ✅ Low GPU memory (<12GB for 8B models)
- ✅ Can switch between tasks easily
- ✅ Preserves base model knowledge

**Implementation:**
```bash
# Install training dependencies
pip install peft transformers datasets accelerate bitsandbytes

# Fine-tune BiMediX for claims medical analysis
python scripts/finetune_lora.py \
  --base_model "BiMediX2-8B" \
  --dataset "claims_medical_analysis.jsonl" \
  --task "medical_entity_validation" \
  --lora_rank 16 \
  --lora_alpha 32 \
  --epochs 3 \
  --batch_size 4 \
  --learning_rate 2e-4 \
  --output_dir "models/bimedix-claims-lora"

# Fine-tune OpenInsurance for adjudication
python scripts/finetune_lora.py \
  --base_model "OpenInsurance-Llama3-8B" \
  --dataset "claims_adjudication.jsonl" \
  --task "claims_decision" \
  --lora_rank 16 \
  --lora_alpha 32 \
  --epochs 3 \
  --output_dir "models/openins-adjudication-lora"
```

**Training Time:**
- BiMediX (8B): ~4-6 hours on RTX 3090
- OpenInsurance (8B): ~4-6 hours on RTX 3060
- BioMistral (7B): ~3-5 hours on RTX 3060

**GPU Memory:**
- 8B model with LoRA: ~10-12GB VRAM
- Can fit on RTX 3060 (12GB) or RTX 3090 (24GB)

### Strategy 2: Full Fine-Tuning

**Best for:** Maximum performance with large datasets (10k+ examples)

**Advantages:**
- ✅ Highest accuracy potential
- ✅ Complete model adaptation
- ✅ Best for critical production use

**Disadvantages:**
- ❌ Requires more data (10k+ examples)
- ❌ Longer training time (days)
- ❌ Higher GPU memory (24GB+)
- ❌ Risk of catastrophic forgetting

**Implementation:**
```bash
# Full fine-tuning (requires more resources)
python scripts/finetune_full.py \
  --base_model "BiMediX2-8B" \
  --dataset "claims_medical_large.jsonl" \
  --epochs 5 \
  --batch_size 2 \
  --gradient_accumulation 8 \
  --learning_rate 1e-5 \
  --output_dir "models/bimedix-claims-full"
```

**Training Time:**
- 8B model: ~2-3 days on RTX 3090
- Requires gradient checkpointing for 24GB GPU

### Strategy 3: QLoRA (Quantized LoRA)

**Best for:** Training larger models on limited GPU memory

**Advantages:**
- ✅ Train 13B/14B models on 12GB GPU
- ✅ 4-bit quantization during training
- ✅ Nearly LoRA-quality results
- ✅ Extremely memory efficient

**Implementation:**
```bash
# QLoRA training for larger models
python scripts/finetune_qlora.py \
  --base_model "Qwen2.5-14B" \
  --load_in_4bit \
  --dataset "documentation.jsonl" \
  --lora_rank 64 \
  --epochs 3 \
  --output_dir "models/qwen-docs-qlora"
```

### Strategy 4: Continued Pre-training

**Best for:** Domain adaptation on large unlabeled corpora

**Use Case:**
- Adapt models to your medical specialty (oncology, cardiology, etc.)
- Learn your organization's terminology
- Improve general medical knowledge

**Implementation:**
```bash
# Continued pre-training on medical corpus
python scripts/pretrain_continue.py \
  --base_model "BioMistral-7B" \
  --corpus "cardiology_notes.txt" \  # 100MB+ text
  --epochs 1 \
  --output_dir "models/biomistral-cardio"
```

## Practical Implementation

### Step 1: Data Preparation

Create training datasets from your historical data:

```python
# scripts/prepare_claims_training_data.py
import json
import pandas as pd
from pathlib import Path

def prepare_medical_analysis_dataset(claims_csv):
    """Prepare BiMediX training data for medical entity validation"""
    
    df = pd.read_csv(claims_csv)
    training_data = []
    
    for _, row in df.iterrows():
        # Build instruction-response pairs
        instruction = f"""Analyze these medical entities for clinical accuracy:

Diagnosis Codes (ICD-10): {row['diagnosis_codes']}
Procedure Codes (CPT): {row['procedure_codes']}
Service Date: {row['service_date']}

Assess:
1. Are ICD-10 codes clinically appropriate?
2. Do CPT codes match diagnoses?
3. Is treatment medically necessary?
4. Any coding concerns?
"""
        
        response = row['medical_analysis_expert']  # From expert adjudicator
        
        training_data.append({
            "instruction": instruction,
            "output": response,
            "metadata": {
                "claim_id": row['claim_id'],
                "decision": row['final_decision']
            }
        })
    
    # Save as JSONL for training
    with open('data/bimedix_medical_analysis.jsonl', 'w') as f:
        for item in training_data:
            f.write(json.dumps(item) + '\n')
    
    print(f"Created {len(training_data)} training examples for BiMediX")

def prepare_adjudication_dataset(claims_csv):
    """Prepare OpenInsurance training data for claims decisions"""
    
    df = pd.read_csv(claims_csv)
    training_data = []
    
    for _, row in df.iterrows():
        instruction = f"""Review this insurance claim for admissibility.

Claim Information:
- Policy: {row['policy_id']}
- Diagnosis: {row['diagnosis_codes']}
- Procedure: {row['procedure_codes']}
- Amount: ${row['claim_amount']}
- Service Date: {row['service_date']}

Medical Analysis: {row['medical_analysis_expert']}

Determine: APPROVED / DENIED / PENDING
Provide detailed reasoning.
"""
        
        response = row['adjudication_decision_expert']  # Expert decision + reasoning
        
        training_data.append({
            "instruction": instruction,
            "output": response,
            "metadata": {
                "claim_id": row['claim_id'],
                "decision": row['final_decision']
            }
        })
    
    with open('data/openins_adjudication.jsonl', 'w') as f:
        for item in training_data:
            f.write(json.dumps(item) + '\n')
    
    print(f"Created {len(training_data)} training examples for OpenInsurance")

# Run data preparation
prepare_medical_analysis_dataset('historical_claims.csv')
prepare_adjudication_dataset('historical_claims.csv')
```

### Step 2: LoRA Fine-Tuning Script

```python
# scripts/finetune_lora.py
import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from datasets import load_dataset

def finetune_lora(
    base_model_path: str,
    dataset_path: str,
    output_dir: str,
    lora_rank: int = 16,
    lora_alpha: int = 32,
    epochs: int = 3,
    batch_size: int = 4,
    learning_rate: float = 2e-4
):
    """Fine-tune model with LoRA"""
    
    # Load base model and tokenizer
    print(f"Loading base model: {base_model_path}")
    model = AutoModelForCausalLM.from_pretrained(
        base_model_path,
        torch_dtype=torch.float16,
        device_map="auto"
    )
    tokenizer = AutoTokenizer.from_pretrained(base_model_path)
    
    # Configure LoRA
    lora_config = LoraConfig(
        r=lora_rank,
        lora_alpha=lora_alpha,
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM"
    )
    
    # Prepare model for training
    model = prepare_model_for_kbit_training(model)
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()  # Show how many params we're training
    
    # Load training dataset
    print(f"Loading dataset: {dataset_path}")
    dataset = load_dataset('json', data_files=dataset_path, split='train')
    
    # Tokenize dataset
    def tokenize_function(examples):
        prompts = [f"### Instruction:\n{inst}\n\n### Response:\n{out}" 
                   for inst, out in zip(examples['instruction'], examples['output'])]
        return tokenizer(prompts, truncation=True, max_length=2048, padding='max_length')
    
    tokenized_dataset = dataset.map(tokenize_function, batched=True)
    
    # Training arguments
    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=4,
        learning_rate=learning_rate,
        fp16=True,
        logging_steps=10,
        save_strategy="epoch",
        evaluation_strategy="no",
        warmup_steps=100,
        lr_scheduler_type="cosine",
        report_to="tensorboard"
    )
    
    # Create trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset,
        tokenizer=tokenizer
    )
    
    # Train!
    print("Starting training...")
    trainer.train()
    
    # Save LoRA adapter
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    
    print(f"✅ Training complete! LoRA adapter saved to {output_dir}")
    print(f"   To use: Load base model + merge LoRA adapter")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--base_model", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--lora_rank", type=int, default=16)
    parser.add_argument("--lora_alpha", type=int, default=32)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch_size", type=int, default=4)
    parser.add_argument("--learning_rate", type=float, default=2e-4)
    
    args = parser.parse_args()
    finetune_lora(**vars(args))
```

### Step 3: Model Deployment

After training, deploy the fine-tuned model:

```python
# app/load_finetuned_model.py
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

def load_finetuned_lora(base_model_path: str, lora_adapter_path: str):
    """Load base model and merge LoRA adapter"""
    
    # Load base model
    model = AutoModelForCausalLM.from_pretrained(
        base_model_path,
        torch_dtype=torch.float16,
        device_map="auto"
    )
    
    # Load and merge LoRA adapter
    model = PeftModel.from_pretrained(model, lora_adapter_path)
    model = model.merge_and_unload()  # Merge LoRA weights into base model
    
    tokenizer = AutoTokenizer.from_pretrained(base_model_path)
    
    return model, tokenizer

# Usage in model_router.py
if os.path.exists("models/bimedix-claims-lora"):
    print("Loading fine-tuned BiMediX for claims...")
    bimedix_model, bimedix_tokenizer = load_finetuned_lora(
        "BiMediX2-8B-hf",
        "models/bimedix-claims-lora"
    )
```

## Training Pipeline

### End-to-End Workflow

```bash
# 1. Collect historical data
python scripts/extract_historical_claims.py \
  --database "claims_db" \
  --output "historical_claims.csv" \
  --date_range "2023-01-01,2024-12-31"

# 2. Prepare training datasets
python scripts/prepare_claims_training_data.py \
  --input "historical_claims.csv" \
  --output_dir "data/"

# 3. Fine-tune BiMediX (medical analysis)
python scripts/finetune_lora.py \
  --base_model "models/BiMediX2-8B-hf" \
  --dataset "data/bimedix_medical_analysis.jsonl" \
  --output_dir "models/bimedix-claims-lora" \
  --epochs 3 \
  --batch_size 4

# 4. Fine-tune OpenInsurance (adjudication)
python scripts/finetune_lora.py \
  --base_model "models/openinsurancellm-llama3-8b" \
  --dataset "data/openins_adjudication.jsonl" \
  --output_dir "models/openins-adjudication-lora" \
  --epochs 3 \
  --batch_size 4

# 5. Evaluate on test set
python scripts/evaluate_models.py \
  --test_data "data/claims_test.jsonl" \
  --models "bimedix-claims-lora,openins-adjudication-lora"

# 6. Convert to GGUF for llama.cpp (optional)
python scripts/convert_to_gguf.py \
  --model "models/bimedix-claims-lora" \
  --output "models/bimedix-claims-Q6_K.gguf"

# 7. Deploy fine-tuned models
pm2 restart inference-node
```

## Evaluation Metrics

### For Claims OCR Agent

**Metrics to Track:**

1. **Medical Analysis Accuracy**
   - ICD-10 validation accuracy
   - CPT code appropriateness
   - Medical necessity assessment accuracy

2. **Adjudication Accuracy**
   - Precision: % of approvals that were correct
   - Recall: % of should-approve claims that were approved
   - F1 Score: Harmonic mean of precision/recall
   - False positive rate: Incorrect approvals
   - False negative rate: Incorrect denials

3. **Business Metrics**
   - Agreement with human adjudicators (target: >90%)
   - Time saved per claim
   - Claims requiring human review (target: <20%)

**Evaluation Script:**
```python
# scripts/evaluate_models.py
from sklearn.metrics import classification_report, confusion_matrix
import json

def evaluate_claims_model(test_data, model_predictions):
    """Evaluate claims adjudication performance"""
    
    y_true = [item['ground_truth_decision'] for item in test_data]
    y_pred = [pred['predicted_decision'] for pred in model_predictions]
    
    # Classification report
    print("Classification Report:")
    print(classification_report(y_true, y_pred, 
                                labels=['APPROVED', 'DENIED', 'PENDING']))
    
    # Confusion matrix
    print("\nConfusion Matrix:")
    print(confusion_matrix(y_true, y_pred, 
                          labels=['APPROVED', 'DENIED', 'PENDING']))
    
    # Business metrics
    total_claims = len(test_data)
    auto_approved = sum(1 for p in y_pred if p == 'APPROVED')
    human_review_needed = sum(1 for p in y_pred if p == 'PENDING')
    
    print(f"\nBusiness Metrics:")
    print(f"  Total claims: {total_claims}")
    print(f"  Auto-approved: {auto_approved} ({auto_approved/total_claims*100:.1f}%)")
    print(f"  Auto-denied: {sum(1 for p in y_pred if p == 'DENIED')}")
    print(f"  Human review: {human_review_needed} ({human_review_needed/total_claims*100:.1f}%)")
```

## Continuous Learning

### Active Learning Pipeline

**Concept:** Use model predictions to identify cases for expert review, then retrain

```python
# scripts/active_learning.py
def identify_low_confidence_claims(predictions, threshold=0.7):
    """Find claims where model is uncertain"""
    
    uncertain_claims = [
        pred for pred in predictions 
        if pred['confidence'] < threshold
    ]
    
    # Send to human expert for review
    for claim in uncertain_claims:
        send_to_expert_queue(claim)
    
    return uncertain_claims

def retrain_with_expert_labels(expert_reviewed_claims):
    """Periodically retrain with expert-labeled data"""
    
    # Add expert reviews to training dataset
    append_to_dataset(expert_reviewed_claims, "data/bimedix_medical_analysis.jsonl")
    
    # Trigger retraining (weekly/monthly)
    trigger_training_job("bimedix-claims-lora", incremental=True)
```

### Model Versioning

```bash
# Track model versions
models/
├── bimedix-claims-lora-v1.0/      # Initial fine-tuning
├── bimedix-claims-lora-v1.1/      # After 1000 expert reviews
├── bimedix-claims-lora-v1.2/      # After policy updates
└── bimedix-claims-lora-v2.0/      # Major retraining
```

## Hardware Requirements

### Training Hardware

| Model Size | LoRA Training | Full Fine-tuning | Inference (GGUF) |
|------------|---------------|------------------|------------------|
| 7B-8B | RTX 3060 (12GB) | RTX 3090 (24GB) | RTX 3060 (6GB) |
| 13B-14B | RTX 3090 (24GB) QLoRA | A100 (40GB) | RTX 3090 (12GB) |
| 70B+ | Multi-GPU | Not feasible | Multi-GPU |

**Your Setup (Perfect for Fine-tuning):**
- RTX 3090 (24GB) - Train 8B models with LoRA/QLoRA
- RTX 3060 (12GB) - Train 7B models with LoRA
- Can train both BiMediX and OpenInsurance simultaneously!

### Training Time Estimates

**LoRA Fine-tuning (1000 examples, 3 epochs):**
- BiMediX2-8B on RTX 3090: ~4-5 hours
- OpenInsurance-8B on RTX 3060: ~5-6 hours
- BioMistral-7B on RTX 3060: ~3-4 hours

**Full Fine-tuning (10k examples, 5 epochs):**
- 8B model on RTX 3090: ~2-3 days
- Requires gradient checkpointing + batch size 1-2

## Production Recommendations

### Phase 1: Baseline (Current) ✅ DONE
- Use pre-trained models off-the-shelf
- Collect production data (claims, decisions, expert reviews)
- **Duration:** 1-3 months

### Phase 2: LoRA Fine-tuning ⏭️ NEXT
- Fine-tune on 1000+ historical claims
- Train BiMediX for medical analysis
- Train OpenInsurance for adjudication
- **Duration:** 1 week for data prep + training

### Phase 3: Evaluation & Iteration
- A/B test fine-tuned vs base models
- Measure accuracy improvement
- Identify edge cases
- **Duration:** 2-4 weeks

### Phase 4: Continuous Learning
- Weekly retraining on new data
- Active learning from uncertain cases
- Model versioning and rollback capability
- **Duration:** Ongoing

## Quick Start: Fine-tune Claims OCR Agent

```bash
# 1. Install dependencies
pip install peft transformers datasets accelerate bitsandbytes tensorboard

# 2. Prepare your data (CSV with historical claims)
# Format: claim_id, diagnosis_codes, procedure_codes, medical_analysis_expert, 
#         adjudication_decision_expert, final_decision

# 3. Create training scripts directory
mkdir -p scripts data models

# 4. Run data preparation (see scripts above)
python scripts/prepare_claims_training_data.py

# 5. Fine-tune BiMediX (RTX 3090, 4-5 hours)
python scripts/finetune_lora.py \
  --base_model "models/BiMediX2-8B-hf" \
  --dataset "data/bimedix_medical_analysis.jsonl" \
  --output_dir "models/bimedix-claims-lora" \
  --lora_rank 16 \
  --epochs 3

# 6. Fine-tune OpenInsurance (RTX 3060, 5-6 hours)
python scripts/finetune_lora.py \
  --base_model "models/openinsurancellm-llama3-8b" \
  --dataset "data/openins_adjudication.jsonl" \
  --output_dir "models/openins-adjudication-lora" \
  --lora_rank 16 \
  --epochs 3

# 7. Evaluate models
python scripts/evaluate_models.py --test_data data/claims_test.jsonl

# 8. Deploy (update model_router.py to load fine-tuned models)
pm2 restart inference-node
```

## ROI Analysis

### Expected Improvements After Fine-tuning

**Accuracy:**
- Medical entity validation: +15-25% accuracy
- Claims adjudication: +20-35% accuracy
- False positive reduction: -30-50%
- Human review needed: -40-60%

**Speed:**
- No change (same inference speed)
- Or faster if you train smaller specialized models

**Business Value:**
- Reduced manual review time: 40-60%
- Fewer claim errors: 30-50%
- Better compliance: +20-30%
- Cost savings: $50k-500k/year (depending on volume)

### Investment Required

**Time:**
- Data preparation: 1-2 weeks
- Initial training: 1 week
- Evaluation: 1-2 weeks
- **Total:** 3-5 weeks for first iteration

**Cost:**
- GPU time: $0 (using existing RTX 3090/3060)
- Engineering time: 80-120 hours
- Data labeling (if needed): Variable

**Break-even:** Typically 2-6 months for high-volume claims processing

---

## Next Steps

1. **Start collecting data** - Export historical claims with expert decisions
2. **Set up training environment** - Install PEFT, transformers, datasets
3. **Prepare datasets** - Format claims data for training
4. **Run pilot training** - Fine-tune on small dataset first (100-500 examples)
5. **Evaluate & iterate** - Test on held-out data, measure improvements
6. **Deploy incrementally** - A/B test fine-tuned models in production
7. **Continuous improvement** - Weekly/monthly retraining with new data

**Ready to take your medical AI agents to the next level! 🚀**
