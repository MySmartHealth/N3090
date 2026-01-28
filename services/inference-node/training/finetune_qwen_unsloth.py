#!/usr/bin/env python3
"""
Fine-tune Qwen 0.6B medical model using Unsloth
Then export to GGUF format
"""
import json
import torch
from datasets import Dataset

# Check if unsloth available
try:
    from unsloth import FastLanguageModel
    UNSLOTH_AVAILABLE = True
except ImportError:
    UNSLOTH_AVAILABLE = False
    print("Unsloth not available, using transformers")

from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments, Trainer
from peft import LoraConfig, get_peft_model

# Config
MODEL_NAME = "Qwen/Qwen2.5-0.5B-Instruct"  # Base model from HF
OUTPUT_DIR = "../models/qwen-medical-finetuned"
LORA_OUTPUT = "../models/qwen-medical-lora"

def load_training_data(path):
    """Load JSONL training data"""
    data = []
    with open(path, 'r') as f:
        for line in f:
            item = json.loads(line.strip())
            # Format as chat
            text = f"""<|im_start|>user
{item['instruction']}<|im_end|>
<|im_start|>assistant
{item['output']}<|im_end|>"""
            data.append({"text": text})
    return Dataset.from_list(data)

def main():
    print("=" * 60)
    print("QWEN MEDICAL FINE-TUNING")
    print("=" * 60)
    
    # Load training data
    print("📚 Loading training data...")
    dataset = load_training_data("medical_training_data.jsonl")
    print(f"   Loaded {len(dataset)} examples")
    
    if UNSLOTH_AVAILABLE:
        print("🚀 Using Unsloth for 2x faster training")
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=MODEL_NAME,
            max_seq_length=512,
            dtype=torch.float16,
            load_in_4bit=True,
        )
        
        model = FastLanguageModel.get_peft_model(
            model,
            r=16,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                          "gate_proj", "up_proj", "down_proj"],
            lora_alpha=16,
            lora_dropout=0,
            bias="none",
            use_gradient_checkpointing="unsloth",
        )
    else:
        print("📦 Using transformers + PEFT")
        tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_NAME,
            torch_dtype=torch.float16,
            device_map="auto",
            trust_remote_code=True
        )
        
        lora_config = LoraConfig(
            r=16,
            lora_alpha=32,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
            lora_dropout=0.05,
            bias="none",
            task_type="CAUSAL_LM"
        )
        model = get_peft_model(model, lora_config)
    
    model.print_trainable_parameters()
    
    # Tokenize with labels for causal LM
    def tokenize(example):
        result = tokenizer(example["text"], truncation=True, max_length=512, padding="max_length")
        result["labels"] = result["input_ids"].copy()  # For causal LM, labels = input_ids
        return result
    
    tokenized = dataset.map(tokenize, batched=True, remove_columns=["text"])
    
    # Training args
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        num_train_epochs=2,
        per_device_train_batch_size=4,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        fp16=True,
        logging_steps=5,
        save_steps=50,
        warmup_steps=10,
        optim="adamw_8bit" if UNSLOTH_AVAILABLE else "adamw_torch",
    )
    
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized,
        tokenizer=tokenizer,
    )
    
    print("\n🏋️ Starting training...")
    trainer.train()
    
    # Save
    print("\n💾 Saving model...")
    model.save_pretrained(LORA_OUTPUT)
    tokenizer.save_pretrained(LORA_OUTPUT)
    
    # Export to GGUF if unsloth
    if UNSLOTH_AVAILABLE:
        print("\n📦 Exporting to GGUF...")
        model.save_pretrained_gguf(
            "../models/qwen-medical-finetuned",
            tokenizer,
            quantization_method="f16"
        )
    
    print("\n✅ Fine-tuning complete!")
    print(f"   LoRA adapter: {LORA_OUTPUT}")
    print(f"   Full model: {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
