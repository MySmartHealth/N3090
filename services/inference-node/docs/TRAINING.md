# Model Fine-tuning and Continuous Learning

Complete infrastructure for fine-tuning medical AI models using real user interactions.

## Architecture

```
User Interactions → PostgreSQL → Training Data Collector → LoRA Fine-tuning → GGUF Conversion → Production Deployment
                        ↓
                  Chat History
                  User Ratings
                  Performance Metrics
```

## Features

✅ **Automatic Data Collection** - Captures all chat interactions in PostgreSQL  
✅ **Quality Filtering** - Filters by user ratings, token count, agent type  
✅ **LoRA/QLoRA Training** - Parameter-efficient fine-tuning (uses <10GB VRAM)  
✅ **GPU Acceleration** - Trains on RTX 3090/3060 GPUs  
✅ **GGUF Conversion** - Auto-converts trained models to llama.cpp format  
✅ **Continuous Learning** - Iterative improvement from production feedback  

## Training Pipeline

### 1. Data Collection

The system automatically collects training data from user interactions:

```python
from app.training import TrainingDataCollector

collector = TrainingDataCollector(min_rating=4.0, min_tokens=10)

# Collect last 30 days of high-quality interactions
training_data = await collector.collect_training_data(
    agent_type="MedicalQA",  # Or None for all agents
    start_date=datetime.now() - timedelta(days=30),
    limit=10000
)

# Export for manual review
collector.export_to_jsonl(training_data, "training_data.jsonl")
```

### 2. Fine-tuning with LoRA/QLoRA

**QLoRA** (4-bit quantized LoRA) allows fine-tuning large models on consumer GPUs:

```bash
# Fine-tune BioMistral-7B on collected data
python scripts/finetune_model.py \
  --base-model ./models/biomistral-7b-fp16 \
  --agent-type MedicalQA \
  --days-back 30 \
  --epochs 3 \
  --batch-size 4 \
  --lora-r 16 \
  --use-qlora \
  --convert-to-gguf \
  --gguf-quantization Q6_K
```

**Parameters:**
- `--base-model` - HuggingFace format model (convert GGUF → HF first if needed)
- `--agent-type` - Filter by agent (MedicalQA, Documentation, Clinical, etc.)
- `--days-back` - Training data time window (default: 30 days)
- `--epochs` - Training iterations (default: 3)
- `--batch-size` - Batch size (4 for 24GB GPU, 2 for 12GB)
- `--lora-r` - LoRA rank (16=balanced, 32=high quality, 8=memory efficient)
- `--use-qlora` - Enable 4-bit quantization (recommended)
- `--convert-to-gguf` - Auto-convert to GGUF after training
- `--gguf-quantization` - Q4_K_M, Q6_K, Q8_0, etc.

### 3. LoRA Configuration

```python
from app.training import LoRAConfig

lora_config = LoRAConfig(
    r=16,                    # Rank (number of low-rank dimensions)
    lora_alpha=32,           # Scaling factor (typically 2 * r)
    target_modules=[         # Which transformer layers to adapt
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj"
    ],
    lora_dropout=0.05,       # Dropout rate
    bias="none"              # Bias handling
)
```

**Memory Requirements:**
- **LoRA (FP16):** ~20-24GB VRAM for 7B model
- **QLoRA (4-bit):** ~8-12GB VRAM for 7B model ✅ Fits RTX 3060!

### 4. Training Process

The fine-tuner automatically:

1. **Loads base model** with 4-bit quantization (QLoRA)
2. **Applies LoRA adapters** to attention layers
3. **Trains only LoRA parameters** (0.1% of total params)
4. **Saves LoRA adapters** (small ~100MB checkpoint)
5. **Merges with base model** (optional)
6. **Converts to GGUF** for production deployment

### 5. Deployment

After training:

```bash
# Option A: Use LoRA adapters with base model (saves space)
# Update model_router.py to load LoRA adapters

# Option B: Use merged GGUF model (converted automatically)
# 1. Place fine-tuned GGUF in models/
# 2. Update ecosystem.config.js with new model path
# 3. Restart llama-server

pm2 restart llama-bimedix2-8081
```

## Example Workflow

```bash
# 1. Collect 30 days of MedicalQA interactions
python scripts/finetune_model.py \
  --base-model ./models/biomistral-7b-fp16 \
  --agent-type MedicalQA \
  --days-back 30 \
  --min-examples 500 \
  --export-jsonl ./data/medicalqa_training.jsonl

# 2. Fine-tune with QLoRA (fits on RTX 3060)
python scripts/finetune_model.py \
  --base-model ./models/biomistral-7b-fp16 \
  --agent-type MedicalQA \
  --epochs 3 \
  --batch-size 2 \
  --lora-r 16 \
  --use-qlora

# 3. Convert to GGUF for production
python scripts/finetune_model.py \
  --base-model ./models/biomistral-7b-fp16 \
  --agent-type MedicalQA \
  --convert-to-gguf \
  --gguf-quantization Q6_K

# 4. Deploy fine-tuned model
cp ./models/biomistral-7b-finetuned-*.Q6_K.gguf \
   ./models/BioMistral-Clinical-7B-Improved.Q6_K.gguf

# Update ecosystem.config.js model path and restart
pm2 restart llama-biomistral-8085
```

## Training Data Quality

The collector applies these filters:

- ✅ **User Rating ≥ 4.0** (1-5 scale from user feedback)
- ✅ **Minimum 10 tokens** in assistant response
- ✅ **Valid conversation pairs** (user input → assistant output)
- ✅ **Agent-specific filtering** (optional)
- ✅ **Time-based filtering** (recent data only)

## Continuous Learning Loop

```
1. Users interact with system → Chat messages stored in PostgreSQL
2. User feedback collected → Ratings/corrections stored
3. Periodic fine-tuning → Weekly/monthly retraining
4. Model evaluation → A/B test new vs old model
5. Deploy if improved → Gradual rollout
6. Monitor performance → Collect more feedback
7. Repeat → Continuous improvement
```

## Installation

```bash
# Install training dependencies (large download ~5GB)
pip install transformers peft datasets bitsandbytes accelerate trl

# Or uncomment in requirements.txt and run:
pip install -r requirements.txt
```

## Advanced Usage

### Custom Training Loop

```python
from app.training import ModelFineTuner, LoRAConfig

# Initialize fine-tuner
fine_tuner = ModelFineTuner(
    base_model_path="./models/biomistral-7b-fp16",
    output_dir="./fine-tuned-models",
    use_qlora=True
)

# Custom LoRA config for high-quality training
lora_config = LoRAConfig(
    r=32,              # Higher rank = more parameters
    lora_alpha=64,
    lora_dropout=0.1
)

# Train
lora_path = fine_tuner.train(
    training_data=training_examples,
    lora_config=lora_config,
    num_epochs=5,
    batch_size=2,
    learning_rate=1e-4
)

# Convert to GGUF
fine_tuner.merge_and_convert_to_gguf(
    lora_path=lora_path,
    output_gguf_path="./models/custom-medical-model.Q6_K.gguf",
    quantization="Q6_K"
)
```

### Multi-Agent Training

Train separate models for each agent type:

```bash
# Documentation agent
python scripts/finetune_model.py \
  --base-model ./models/medicine-llm-13b-fp16 \
  --agent-type Documentation \
  --epochs 5

# Clinical agent
python scripts/finetune_model.py \
  --base-model ./models/biomistral-7b-fp16 \
  --agent-type Clinical \
  --epochs 3

# Billing agent
python scripts/finetune_model.py \
  --base-model ./models/openinsurance-llama3-8b-fp16 \
  --agent-type Billing \
  --epochs 3
```

## Performance Tips

1. **Batch Size:** Start small (2-4), increase if VRAM allows
2. **Learning Rate:** 2e-4 for QLoRA, 1e-4 for full fine-tuning
3. **Epochs:** 3-5 typically sufficient, monitor for overfitting
4. **LoRA Rank:** 16 balanced, 8 for speed, 32 for quality
5. **Gradient Accumulation:** Use 4-8 to simulate larger batches
6. **Mixed Precision:** Always use FP16 (enabled by default)

## Monitoring

Track training metrics:

```python
# Training logs automatically saved to:
./fine-tuned-models/lora_YYYYMMDD_HHMMSS/

# View TensorBoard logs:
tensorboard --logdir ./fine-tuned-models/
```

## Troubleshooting

**Out of Memory:**
- Reduce `--batch-size` (try 1 or 2)
- Enable `--use-qlora`
- Reduce `--lora-r` (try 8)
- Use gradient checkpointing (automatic in QLoRA)

**Poor Performance:**
- Increase `--min-examples` (need 500+ for good results)
- Increase `--lora-r` (try 32 or 64)
- Increase `--epochs` (try 5-10)
- Check training data quality (user ratings, relevance)

**Conversion Errors:**
- Ensure llama.cpp is built with CUDA support
- Check paths to `convert_hf_to_gguf.py` and `llama-quantize`
- Verify HuggingFace model format is correct

## Resources

- **PEFT Documentation:** https://huggingface.co/docs/peft
- **QLoRA Paper:** https://arxiv.org/abs/2305.14314
- **llama.cpp:** https://github.com/ggerganov/llama.cpp
- **Training Guide:** https://huggingface.co/blog/qlora

## Next Steps

1. Set up automated weekly retraining pipeline
2. Implement A/B testing framework for new models
3. Add model evaluation metrics (BLEU, ROUGE, medical accuracy)
4. Create feedback UI for users to rate responses
5. Build model versioning and rollback system
