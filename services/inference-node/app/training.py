"""
Model Fine-tuning and Training Infrastructure
Continuous learning from user interactions with LoRA/QLoRA fine-tuning.
"""
import os
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
from pathlib import Path
from loguru import logger

# Try importing training libraries
try:
    from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments
    from peft import LoraConfig, get_peft_model, TaskType, PeftModel
    from datasets import Dataset
    TRAINING_AVAILABLE = True
except ImportError:
    TRAINING_AVAILABLE = False
    logger.warning("Training libraries not installed (transformers, peft, datasets)")

try:
    from app.database import AsyncSessionLocal, ChatMessage, ChatSession
    from sqlalchemy import select, and_
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False


@dataclass
class TrainingExample:
    """Single training example from chat history."""
    input: str
    output: str
    agent_type: str
    model_used: str
    rating: Optional[float] = None  # User feedback rating
    created_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class LoRAConfig:
    """LoRA fine-tuning configuration."""
    r: int = 16  # LoRA rank
    lora_alpha: int = 32  # LoRA alpha scaling
    target_modules: List[str] = None  # Modules to apply LoRA (q_proj, v_proj, etc.)
    lora_dropout: float = 0.05
    bias: str = "none"
    task_type: str = "CAUSAL_LM"
    
    def __post_init__(self):
        if self.target_modules is None:
            # Default for LLaMA/Mistral models
            self.target_modules = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]


class TrainingDataCollector:
    """
    Collects training data from user interactions stored in PostgreSQL.
    Filters for high-quality examples based on user feedback and performance metrics.
    """
    
    def __init__(self, min_rating: float = 4.0, min_tokens: int = 10):
        """
        Initialize training data collector.
        
        Args:
            min_rating: Minimum user rating to include example (1-5 scale)
            min_tokens: Minimum token count for output
        """
        self.min_rating = min_rating
        self.min_tokens = min_tokens
    
    async def collect_training_data(
        self,
        agent_type: Optional[str] = None,
        model_name: Optional[str] = None,
        start_date: Optional[datetime] = None,
        limit: int = 10000
    ) -> List[TrainingExample]:
        """
        Collect training examples from chat history.
        
        Args:
            agent_type: Filter by agent type (e.g., "MedicalQA", "Documentation")
            model_name: Filter by model used
            start_date: Only collect data after this date
            limit: Maximum number of examples
            
        Returns:
            List of training examples
        """
        if not DB_AVAILABLE:
            logger.error("Database not available for training data collection")
            return []
        
        examples = []
        
        try:
            async with AsyncSessionLocal() as session:
                # Query chat messages with user-assistant pairs
                query = select(ChatMessage).order_by(ChatMessage.created_at.desc())
                
                if agent_type:
                    query = query.join(ChatSession).where(ChatSession.agent_type == agent_type)
                
                if model_name:
                    query = query.where(ChatMessage.model_used == model_name)
                
                if start_date:
                    query = query.where(ChatMessage.created_at >= start_date)
                
                query = query.limit(limit * 2)  # Get more to filter pairs
                
                result = await session.execute(query)
                messages = result.scalars().all()
                
                # Group into conversation pairs
                current_input = None
                for msg in messages:
                    if msg.role == "user":
                        current_input = msg.content
                    elif msg.role == "assistant" and current_input:
                        # Check quality filters
                        if msg.tokens_used and msg.tokens_used >= self.min_tokens:
                            # Get user feedback from metadata
                            rating = msg.metadata.get("user_rating") if msg.metadata else None
                            
                            if rating is None or rating >= self.min_rating:
                                examples.append(TrainingExample(
                                    input=current_input,
                                    output=msg.content,
                                    agent_type=agent_type or "unknown",
                                    model_used=msg.model_used or "unknown",
                                    rating=rating,
                                    created_at=msg.created_at,
                                    metadata=msg.metadata
                                ))
                        
                        current_input = None
                        
                        if len(examples) >= limit:
                            break
            
            logger.info(f"Collected {len(examples)} training examples")
            return examples
            
        except Exception as e:
            logger.error(f"Failed to collect training data: {e}")
            return []
    
    def export_to_jsonl(self, examples: List[TrainingExample], output_path: str):
        """
        Export training examples to JSONL format.
        
        Args:
            examples: Training examples to export
            output_path: Path to output JSONL file
        """
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w') as f:
            for example in examples:
                # Format as instruction-following example
                training_item = {
                    "instruction": example.input,
                    "output": example.output,
                    "agent_type": example.agent_type,
                    "model": example.model_used,
                    "rating": example.rating,
                    "timestamp": example.created_at.isoformat() if example.created_at else None
                }
                f.write(json.dumps(training_item) + '\n')
        
        logger.info(f"Exported {len(examples)} examples to {output_path}")


class ModelFineTuner:
    """
    Fine-tune models using LoRA/QLoRA for parameter-efficient training.
    Supports medical domain adaptation on collected user interactions.
    """
    
    def __init__(
        self,
        base_model_path: str,
        output_dir: str = "./fine-tuned-models",
        use_qlora: bool = True
    ):
        """
        Initialize fine-tuner.
        
        Args:
            base_model_path: Path to base model (HuggingFace format)
            output_dir: Directory to save fine-tuned models
            use_qlora: Use 4-bit quantization for QLoRA (memory efficient)
        """
        self.base_model_path = base_model_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.use_qlora = use_qlora
        
        if not TRAINING_AVAILABLE:
            raise ImportError(
                "Training libraries not installed. Install with: "
                "pip install transformers peft datasets bitsandbytes accelerate"
            )
    
    def prepare_dataset(self, examples: List[TrainingExample]) -> Dataset:
        """
        Prepare dataset from training examples.
        
        Args:
            examples: List of training examples
            
        Returns:
            HuggingFace Dataset ready for training
        """
        # Convert to dict format
        data = {
            "text": [],
            "agent_type": [],
            "rating": []
        }
        
        for example in examples:
            # Format as instruction-following prompt
            text = f"""Below is an instruction that describes a task. Write a response that appropriately completes the request.

### Instruction:
{example.input}

### Response:
{example.output}"""
            
            data["text"].append(text)
            data["agent_type"].append(example.agent_type)
            data["rating"].append(example.rating or 0.0)
        
        return Dataset.from_dict(data)
    
    def train(
        self,
        training_data: List[TrainingExample],
        lora_config: Optional[LoRAConfig] = None,
        num_epochs: int = 3,
        batch_size: int = 4,
        learning_rate: float = 2e-4,
        gradient_accumulation_steps: int = 4
    ) -> str:
        """
        Fine-tune model with LoRA/QLoRA.
        
        Args:
            training_data: Training examples
            lora_config: LoRA configuration (uses defaults if None)
            num_epochs: Number of training epochs
            batch_size: Training batch size
            learning_rate: Learning rate
            gradient_accumulation_steps: Gradient accumulation steps
            
        Returns:
            Path to fine-tuned model
        """
        if lora_config is None:
            lora_config = LoRAConfig()
        
        logger.info(f"Starting fine-tuning with {len(training_data)} examples")
        
        # Prepare dataset
        dataset = self.prepare_dataset(training_data)
        
        # Load base model
        logger.info(f"Loading base model: {self.base_model_path}")
        
        if self.use_qlora:
            # 4-bit quantization for QLoRA
            from transformers import BitsAndBytesConfig
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype="float16",
                bnb_4bit_use_double_quant=True
            )
            model = AutoModelForCausalLM.from_pretrained(
                self.base_model_path,
                quantization_config=bnb_config,
                device_map="auto",
                trust_remote_code=True
            )
        else:
            model = AutoModelForCausalLM.from_pretrained(
                self.base_model_path,
                device_map="auto",
                trust_remote_code=True
            )
        
        tokenizer = AutoTokenizer.from_pretrained(self.base_model_path)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        
        # Configure LoRA
        peft_config = LoraConfig(
            r=lora_config.r,
            lora_alpha=lora_config.lora_alpha,
            target_modules=lora_config.target_modules,
            lora_dropout=lora_config.lora_dropout,
            bias=lora_config.bias,
            task_type=TaskType.CAUSAL_LM
        )
        
        model = get_peft_model(model, peft_config)
        model.print_trainable_parameters()
        
        # Training arguments
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = self.output_dir / f"lora_{timestamp}"
        
        training_args = TrainingArguments(
            output_dir=str(output_path),
            num_train_epochs=num_epochs,
            per_device_train_batch_size=batch_size,
            gradient_accumulation_steps=gradient_accumulation_steps,
            learning_rate=learning_rate,
            fp16=True,
            logging_steps=10,
            save_strategy="epoch",
            optim="paged_adamw_8bit" if self.use_qlora else "adamw_torch",
            warmup_ratio=0.1,
            lr_scheduler_type="cosine"
        )
        
        # Train
        from transformers import Trainer, DataCollatorForLanguageModeling
        
        data_collator = DataCollatorForLanguageModeling(tokenizer, mlm=False)
        
        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=dataset,
            data_collator=data_collator
        )
        
        logger.info("Starting training...")
        trainer.train()
        
        # Save LoRA adapters
        model.save_pretrained(output_path)
        tokenizer.save_pretrained(output_path)
        
        logger.info(f"Fine-tuning complete! Model saved to: {output_path}")
        return str(output_path)
    
    def merge_and_convert_to_gguf(
        self,
        lora_path: str,
        output_gguf_path: str,
        quantization: str = "Q6_K"
    ):
        """
        Merge LoRA adapters with base model and convert to GGUF format.
        
        Args:
            lora_path: Path to fine-tuned LoRA adapters
            output_gguf_path: Path for output GGUF file
            quantization: GGUF quantization method (Q4_K_M, Q6_K, Q8_0, etc.)
        """
        logger.info(f"Merging LoRA adapters from: {lora_path}")
        
        # Load base model and LoRA
        base_model = AutoModelForCausalLM.from_pretrained(
            self.base_model_path,
            device_map="cpu",
            trust_remote_code=True
        )
        
        model = PeftModel.from_pretrained(base_model, lora_path)
        model = model.merge_and_unload()
        
        # Save merged model
        merged_path = Path(lora_path).parent / "merged"
        model.save_pretrained(merged_path)
        
        tokenizer = AutoTokenizer.from_pretrained(lora_path)
        tokenizer.save_pretrained(merged_path)
        
        logger.info(f"Merged model saved to: {merged_path}")
        
        # Convert to GGUF using llama.cpp
        logger.info(f"Converting to GGUF format with {quantization} quantization")
        
        import subprocess
        
        # Path to llama.cpp conversion script
        convert_script = "/home/dgs/llama.cpp/convert_hf_to_gguf.py"
        quantize_binary = "/home/dgs/llama.cpp/build/bin/llama-quantize"
        
        # Convert to FP16 GGUF first
        fp16_path = str(Path(output_gguf_path).with_suffix('.fp16.gguf'))
        subprocess.run([
            "python", convert_script,
            str(merged_path),
            "--outfile", fp16_path,
            "--outtype", "f16"
        ], check=True)
        
        # Quantize to target format
        subprocess.run([
            quantize_binary,
            fp16_path,
            output_gguf_path,
            quantization
        ], check=True)
        
        logger.info(f"GGUF model created: {output_gguf_path}")
        
        # Clean up intermediate files
        Path(fp16_path).unlink()
        
        return output_gguf_path


# Singleton instance
_training_data_collector = None

def get_training_collector() -> TrainingDataCollector:
    """Get singleton training data collector."""
    global _training_data_collector
    if _training_data_collector is None:
        _training_data_collector = TrainingDataCollector()
    return _training_data_collector
