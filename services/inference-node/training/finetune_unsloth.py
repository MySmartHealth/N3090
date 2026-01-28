#!/usr/bin/env python3
"""
Fine-tune BiMediX2 on medical documents using Unsloth
Outputs GGUF format for llama.cpp
"""
import torch
from unsloth import FastLanguageModel
from datasets import load_dataset, Dataset
from trl import SFTTrainer
from transformers import TrainingArguments
import json

# Configuration
MAX_SEQ_LENGTH = 512
DTYPE = None  # Auto-detect
LOAD_IN_4BIT = True

print("=" * 60)
print("BIMEDIX2 MEDICAL FINE-TUNING")
print("=" * 60)

# Load training data
print("\n📚 Loading training data...")
training_file = "/home/dgs/N3090/services/inference-node/training/medical_training_data.jsonl"
with open(training_file) as f:
    data = [json.loads(line) for line in f]

# Convert to dataset format
def format_prompt(example):
    return f"""### Instruction:
{example['instruction']}

### Response:
{example['output']}"""

formatted_data = [{"text": format_prompt(d)} for d in data]
dataset = Dataset.from_list(formatted_data)
print(f"✅ Loaded {len(dataset)} training examples")

# Load model - using Llama 3.1 8B as base (BiMediX2 is based on this)
print("\n🔄 Loading model...")
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = "unsloth/Meta-Llama-3.1-8B-Instruct-bnb-4bit",
    max_seq_length = MAX_SEQ_LENGTH,
    dtype = DTYPE,
    load_in_4bit = LOAD_IN_4BIT,
)

# Add LoRA adapters
print("\n🧬 Adding LoRA adapters...")
model = FastLanguageModel.get_peft_model(
    model,
    r = 16,  # LoRA rank
    target_modules = ["q_proj", "k_proj", "v_proj", "o_proj",
                      "gate_proj", "up_proj", "down_proj"],
    lora_alpha = 16,
    lora_dropout = 0,
    bias = "none",
    use_gradient_checkpointing = "unsloth",
    random_state = 42,
)

# Training arguments
print("\n⚙️ Setting up training...")
training_args = TrainingArguments(
    output_dir = "/home/dgs/N3090/services/inference-node/models/bimedix-lora-trained",
    per_device_train_batch_size = 2,
    gradient_accumulation_steps = 4,
    warmup_steps = 5,
    max_steps = 60,  # Quick training on small dataset
    learning_rate = 2e-4,
    fp16 = not torch.cuda.is_bf16_supported(),
    bf16 = torch.cuda.is_bf16_supported(),
    logging_steps = 5,
    optim = "adamw_8bit",
    weight_decay = 0.01,
    lr_scheduler_type = "linear",
    seed = 42,
)

# Create trainer
trainer = SFTTrainer(
    model = model,
    tokenizer = tokenizer,
    train_dataset = dataset,
    dataset_text_field = "text",
    max_seq_length = MAX_SEQ_LENGTH,
    dataset_num_proc = 2,
    packing = False,
    args = training_args,
)

# Train
print("\n🚀 Starting training...")
print("-" * 40)
trainer_stats = trainer.train()
print("-" * 40)
print(f"\n✅ Training complete!")
print(f"   Loss: {trainer_stats.training_loss:.4f}")

# Save LoRA adapter
print("\n💾 Saving LoRA adapter...")
model.save_pretrained("/home/dgs/N3090/services/inference-node/models/bimedix-lora-trained")
tokenizer.save_pretrained("/home/dgs/N3090/services/inference-node/models/bimedix-lora-trained")

# Export to GGUF
print("\n📦 Exporting to GGUF format...")
model.save_pretrained_gguf(
    "/home/dgs/N3090/services/inference-node/models/bimedix-medical-finetuned",
    tokenizer,
    quantization_method = "q4_k_m"
)

print("\n" + "=" * 60)
print("🎉 FINE-TUNING COMPLETE!")
print("=" * 60)
print(f"\nGGUF model saved to:")
print(f"  /home/dgs/N3090/services/inference-node/models/bimedix-medical-finetuned")
