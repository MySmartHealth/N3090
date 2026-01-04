#!/usr/bin/env python3
"""
Fine-tune a medical model using collected user interaction data.
Supports LoRA/QLoRA for efficient training on consumer GPUs.
"""
import asyncio
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.training import TrainingDataCollector, ModelFineTuner, LoRAConfig
from loguru import logger


async def main():
    parser = argparse.ArgumentParser(description="Fine-tune medical AI model")
    parser.add_argument(
        "--base-model",
        type=str,
        required=True,
        help="Path to base model (HuggingFace format, e.g., BioMistral-7B-GPTQ)"
    )
    parser.add_argument(
        "--agent-type",
        type=str,
        default=None,
        help="Filter training data by agent type (MedicalQA, Documentation, etc.)"
    )
    parser.add_argument(
        "--days-back",
        type=int,
        default=30,
        help="Collect training data from last N days (default: 30)"
    )
    parser.add_argument(
        "--min-examples",
        type=int,
        default=100,
        help="Minimum number of training examples required (default: 100)"
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=3,
        help="Number of training epochs (default: 3)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=4,
        help="Training batch size (default: 4)"
    )
    parser.add_argument(
        "--lora-r",
        type=int,
        default=16,
        help="LoRA rank (default: 16, higher = more parameters)"
    )
    parser.add_argument(
        "--use-qlora",
        action="store_true",
        default=True,
        help="Use QLoRA (4-bit quantization) for memory efficiency"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./fine-tuned-models",
        help="Output directory for fine-tuned models"
    )
    parser.add_argument(
        "--export-jsonl",
        type=str,
        default=None,
        help="Export training data to JSONL file (optional)"
    )
    parser.add_argument(
        "--convert-to-gguf",
        action="store_true",
        help="Convert fine-tuned model to GGUF format"
    )
    parser.add_argument(
        "--gguf-quantization",
        type=str,
        default="Q6_K",
        choices=["Q4_K_M", "Q5_K_M", "Q6_K", "Q8_0", "F16"],
        help="GGUF quantization method (default: Q6_K)"
    )
    
    args = parser.parse_args()
    
    logger.info("🚀 Starting model fine-tuning pipeline")
    logger.info(f"Base model: {args.base_model}")
    logger.info(f"Agent type: {args.agent_type or 'all'}")
    logger.info(f"Training data: last {args.days_back} days")
    
    # Step 1: Collect training data
    logger.info("\n📊 Step 1: Collecting training data from database...")
    
    collector = TrainingDataCollector(min_rating=4.0, min_tokens=10)
    start_date = datetime.now() - timedelta(days=args.days_back)
    
    training_data = await collector.collect_training_data(
        agent_type=args.agent_type,
        start_date=start_date,
        limit=10000
    )
    
    if len(training_data) < args.min_examples:
        logger.error(
            f"Insufficient training data: {len(training_data)} examples "
            f"(minimum: {args.min_examples})"
        )
        logger.info("💡 Tips to collect more data:")
        logger.info("  - Increase --days-back value")
        logger.info("  - Lower --min-examples requirement")
        logger.info("  - Use system more to generate interaction data")
        sys.exit(1)
    
    logger.info(f"✅ Collected {len(training_data)} high-quality examples")
    
    # Optional: Export to JSONL
    if args.export_jsonl:
        logger.info(f"\n💾 Exporting training data to {args.export_jsonl}")
        collector.export_to_jsonl(training_data, args.export_jsonl)
    
    # Step 2: Configure LoRA
    logger.info(f"\n⚙️  Step 2: Configuring LoRA (rank={args.lora_r})")
    
    lora_config = LoRAConfig(
        r=args.lora_r,
        lora_alpha=args.lora_r * 2,  # Common heuristic: alpha = 2 * r
        lora_dropout=0.05
    )
    
    # Step 3: Fine-tune model
    logger.info(f"\n🎯 Step 3: Fine-tuning with {'QLoRA' if args.use_qlora else 'LoRA'}")
    logger.info(f"Training parameters:")
    logger.info(f"  - Epochs: {args.epochs}")
    logger.info(f"  - Batch size: {args.batch_size}")
    logger.info(f"  - LoRA rank: {args.lora_r}")
    logger.info(f"  - Quantization: {'4-bit (QLoRA)' if args.use_qlora else 'None'}")
    
    fine_tuner = ModelFineTuner(
        base_model_path=args.base_model,
        output_dir=args.output_dir,
        use_qlora=args.use_qlora
    )
    
    lora_path = fine_tuner.train(
        training_data=training_data,
        lora_config=lora_config,
        num_epochs=args.epochs,
        batch_size=args.batch_size
    )
    
    logger.info(f"✅ Fine-tuning complete! LoRA adapters saved to: {lora_path}")
    
    # Step 4: Convert to GGUF (optional)
    if args.convert_to_gguf:
        logger.info(f"\n🔄 Step 4: Converting to GGUF ({args.gguf_quantization})")
        
        model_name = Path(args.base_model).name
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        gguf_path = f"./models/{model_name}-finetuned-{timestamp}.{args.gguf_quantization}.gguf"
        
        fine_tuner.merge_and_convert_to_gguf(
            lora_path=lora_path,
            output_gguf_path=gguf_path,
            quantization=args.gguf_quantization
        )
        
        logger.info(f"✅ GGUF model ready: {gguf_path}")
        logger.info("\n📝 To use the fine-tuned model:")
        logger.info(f"   1. Update model_router.py with new model path")
        logger.info(f"   2. Restart llama-server with: {gguf_path}")
        logger.info(f"   3. Test inference via API")
    
    logger.info("\n🎉 Fine-tuning pipeline complete!")
    logger.info("\n📊 Next steps:")
    logger.info("  - Evaluate model performance on test set")
    logger.info("  - Compare with base model on benchmark tasks")
    logger.info("  - Deploy to production if metrics improve")
    logger.info("  - Continue collecting feedback for next iteration")


if __name__ == "__main__":
    asyncio.run(main())
