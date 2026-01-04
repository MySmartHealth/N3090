"""
LoRA Fine-tuning script for medical AI models
Supports BiMediX, OpenInsurance, BioMistral, and other models
"""
import os
import torch
import argparse
from pathlib import Path
from typing import Optional
from datetime import datetime

from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training, TaskType
from datasets import load_dataset
import bitsandbytes as bnb


def find_all_linear_names(model):
    """Find all linear layer names for LoRA target modules"""
    cls = bnb.nn.Linear4bit
    lora_module_names = set()
    
    for name, module in model.named_modules():
        if isinstance(module, cls):
            names = name.split('.')
            lora_module_names.add(names[0] if len(names) == 1 else names[-1])
    
    if 'lm_head' in lora_module_names:
        lora_module_names.remove('lm_head')
    
    return list(lora_module_names)


def create_prompt(instruction: str, output: str, system_prompt: Optional[str] = None) -> str:
    """Create training prompt with instruction format"""
    
    if system_prompt:
        prompt = f"""<|system|>
{system_prompt}
<|user|>
{instruction}
<|assistant|>
{output}"""
    else:
        prompt = f"""### Instruction:
{instruction}

### Response:
{output}"""
    
    return prompt


def finetune_lora(
    base_model: str,
    dataset_path: str,
    output_dir: str,
    lora_rank: int = 16,
    lora_alpha: int = 32,
    lora_dropout: float = 0.05,
    num_epochs: int = 3,
    batch_size: int = 4,
    gradient_accumulation_steps: int = 4,
    learning_rate: float = 2e-4,
    max_length: int = 2048,
    use_4bit: bool = False,
    warmup_steps: int = 100,
    logging_steps: int = 10,
    save_steps: int = 100,
    eval_steps: Optional[int] = None,
    system_prompt: Optional[str] = None
):
    """
    Fine-tune a model using LoRA (Low-Rank Adaptation)
    
    Args:
        base_model: Path to base model (HuggingFace format)
        dataset_path: Path to training dataset (JSONL with instruction/output)
        output_dir: Directory to save fine-tuned model
        lora_rank: LoRA rank parameter (lower = fewer params, faster)
        lora_alpha: LoRA alpha parameter
        lora_dropout: Dropout for LoRA layers
        num_epochs: Number of training epochs
        batch_size: Per-device batch size
        gradient_accumulation_steps: Gradient accumulation steps
        learning_rate: Learning rate
        max_length: Maximum sequence length
        use_4bit: Use 4-bit quantization (QLoRA)
        warmup_steps: Warmup steps
        logging_steps: Log every N steps
        save_steps: Save checkpoint every N steps
        eval_steps: Evaluate every N steps (if validation set provided)
        system_prompt: Optional system prompt for chat models
    """
    
    print("=" * 80)
    print("LORA FINE-TUNING")
    print("=" * 80)
    print(f"Base Model: {base_model}")
    print(f"Dataset: {dataset_path}")
    print(f"Output: {output_dir}")
    print(f"LoRA Rank: {lora_rank}, Alpha: {lora_alpha}")
    print(f"Epochs: {num_epochs}, Batch Size: {batch_size}")
    print(f"Learning Rate: {learning_rate}")
    print(f"4-bit Quantization: {use_4bit}")
    print("=" * 80)
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Load tokenizer
    print("\n📚 Loading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
    
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        tokenizer.pad_token_id = tokenizer.eos_token_id
    
    # Load model
    print("\n🤖 Loading base model...")
    
    if use_4bit:
        # QLoRA: 4-bit quantization
        from transformers import BitsAndBytesConfig
        
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16
        )
        
        model = AutoModelForCausalLM.from_pretrained(
            base_model,
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True
        )
        
        model = prepare_model_for_kbit_training(model)
        print("   ✅ Loaded with 4-bit quantization (QLoRA)")
    
    else:
        # Standard LoRA: FP16
        model = AutoModelForCausalLM.from_pretrained(
            base_model,
            torch_dtype=torch.float16,
            device_map="auto",
            trust_remote_code=True
        )
        print("   ✅ Loaded with FP16")
    
    # Configure LoRA
    print("\n🔧 Configuring LoRA...")
    
    # Find target modules
    target_modules = find_all_linear_names(model) if use_4bit else ["q_proj", "v_proj", "k_proj", "o_proj"]
    
    lora_config = LoraConfig(
        r=lora_rank,
        lora_alpha=lora_alpha,
        target_modules=target_modules,
        lora_dropout=lora_dropout,
        bias="none",
        task_type=TaskType.CAUSAL_LM
    )
    
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()
    
    # Load dataset
    print("\n📊 Loading dataset...")
    dataset = load_dataset('json', data_files=dataset_path, split='train')
    print(f"   Loaded {len(dataset)} training examples")
    
    # Check for validation set
    test_path = dataset_path.replace('.jsonl', '_test.jsonl')
    eval_dataset = None
    if os.path.exists(test_path):
        eval_dataset = load_dataset('json', data_files=test_path, split='train')
        print(f"   Loaded {len(eval_dataset)} validation examples")
    
    # Tokenize dataset
    def tokenize_function(examples):
        prompts = []
        for inst, out in zip(examples['instruction'], examples['output']):
            prompt = create_prompt(inst, out, system_prompt)
            prompts.append(prompt)
        
        # Tokenize
        result = tokenizer(
            prompts,
            truncation=True,
            max_length=max_length,
            padding='max_length',
            return_tensors=None
        )
        
        # Labels are same as input_ids for causal LM
        result['labels'] = result['input_ids'].copy()
        
        return result
    
    print("\n🔄 Tokenizing dataset...")
    tokenized_dataset = dataset.map(
        tokenize_function,
        batched=True,
        remove_columns=dataset.column_names,
        desc="Tokenizing training data"
    )
    
    if eval_dataset:
        tokenized_eval = eval_dataset.map(
            tokenize_function,
            batched=True,
            remove_columns=eval_dataset.column_names,
            desc="Tokenizing validation data"
        )
    else:
        tokenized_eval = None
    
    # Training arguments
    print("\n⚙️  Configuring training...")
    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=num_epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size if eval_dataset else None,
        gradient_accumulation_steps=gradient_accumulation_steps,
        learning_rate=learning_rate,
        fp16=True,
        logging_dir=f"{output_dir}/logs",
        logging_steps=logging_steps,
        save_steps=save_steps,
        save_total_limit=3,
        evaluation_strategy="steps" if eval_dataset else "no",
        eval_steps=eval_steps if eval_steps and eval_dataset else None,
        warmup_steps=warmup_steps,
        lr_scheduler_type="cosine",
        optim="paged_adamw_8bit" if use_4bit else "adamw_torch",
        report_to="tensorboard",
        load_best_model_at_end=True if eval_dataset else False,
        metric_for_best_model="eval_loss" if eval_dataset else None,
        greater_is_better=False,
        push_to_hub=False
    )
    
    # Data collator
    data_collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer,
        mlm=False
    )
    
    # Create trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset,
        eval_dataset=tokenized_eval,
        data_collator=data_collator,
        tokenizer=tokenizer
    )
    
    # Train!
    print("\n🚀 Starting training...")
    print("=" * 80)
    
    start_time = datetime.now()
    trainer.train()
    end_time = datetime.now()
    
    print("=" * 80)
    print(f"✅ Training complete! Duration: {end_time - start_time}")
    
    # Save model
    print(f"\n💾 Saving LoRA adapter to {output_dir}...")
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    
    # Save training info
    training_info = {
        "base_model": base_model,
        "lora_rank": lora_rank,
        "lora_alpha": lora_alpha,
        "num_epochs": num_epochs,
        "learning_rate": learning_rate,
        "batch_size": batch_size,
        "gradient_accumulation_steps": gradient_accumulation_steps,
        "training_examples": len(dataset),
        "validation_examples": len(eval_dataset) if eval_dataset else 0,
        "training_duration": str(end_time - start_time),
        "timestamp": datetime.now().isoformat()
    }
    
    import json
    with open(f"{output_dir}/training_info.json", 'w') as f:
        json.dump(training_info, f, indent=2)
    
    print("\n" + "=" * 80)
    print("🎉 FINE-TUNING COMPLETE!")
    print("=" * 80)
    print(f"\n📁 LoRA adapter saved to: {output_dir}")
    print(f"📊 Training info: {output_dir}/training_info.json")
    print(f"📈 TensorBoard logs: {output_dir}/logs")
    print("\nTo view training progress:")
    print(f"  tensorboard --logdir {output_dir}/logs")
    print("\nTo use the fine-tuned model:")
    print(f"  1. Load base model: {base_model}")
    print(f"  2. Load LoRA adapter from: {output_dir}")
    print(f"  3. Merge or use with PEFT")
    
    return output_dir


def main():
    parser = argparse.ArgumentParser(description="Fine-tune medical AI models with LoRA")
    
    # Model arguments
    parser.add_argument("--base_model", required=True, help="Path to base model (HuggingFace)")
    parser.add_argument("--dataset", required=True, help="Path to training dataset (JSONL)")
    parser.add_argument("--output_dir", required=True, help="Output directory for fine-tuned model")
    
    # LoRA arguments
    parser.add_argument("--lora_rank", type=int, default=16, help="LoRA rank (default: 16)")
    parser.add_argument("--lora_alpha", type=int, default=32, help="LoRA alpha (default: 32)")
    parser.add_argument("--lora_dropout", type=float, default=0.05, help="LoRA dropout (default: 0.05)")
    
    # Training arguments
    parser.add_argument("--epochs", type=int, default=3, help="Number of epochs (default: 3)")
    parser.add_argument("--batch_size", type=int, default=4, help="Per-device batch size (default: 4)")
    parser.add_argument("--gradient_accumulation", type=int, default=4, help="Gradient accumulation steps (default: 4)")
    parser.add_argument("--learning_rate", type=float, default=2e-4, help="Learning rate (default: 2e-4)")
    parser.add_argument("--max_length", type=int, default=2048, help="Maximum sequence length (default: 2048)")
    parser.add_argument("--warmup_steps", type=int, default=100, help="Warmup steps (default: 100)")
    
    # Other arguments
    parser.add_argument("--use_4bit", action="store_true", help="Use 4-bit quantization (QLoRA)")
    parser.add_argument("--logging_steps", type=int, default=10, help="Logging frequency (default: 10)")
    parser.add_argument("--save_steps", type=int, default=100, help="Save checkpoint frequency (default: 100)")
    parser.add_argument("--eval_steps", type=int, default=None, help="Evaluation frequency")
    parser.add_argument("--system_prompt", type=str, default=None, help="System prompt for chat models")
    
    args = parser.parse_args()
    
    # Run fine-tuning
    finetune_lora(
        base_model=args.base_model,
        dataset_path=args.dataset,
        output_dir=args.output_dir,
        lora_rank=args.lora_rank,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        num_epochs=args.epochs,
        batch_size=args.batch_size,
        gradient_accumulation_steps=args.gradient_accumulation,
        learning_rate=args.learning_rate,
        max_length=args.max_length,
        use_4bit=args.use_4bit,
        warmup_steps=args.warmup_steps,
        logging_steps=args.logging_steps,
        save_steps=args.save_steps,
        eval_steps=args.eval_steps,
        system_prompt=args.system_prompt
    )


if __name__ == "__main__":
    main()
