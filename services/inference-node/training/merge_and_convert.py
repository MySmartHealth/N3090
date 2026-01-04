"""
Merge LoRA adapter into base model and convert to GGUF for production deployment
This script takes a fine-tuned LoRA adapter and creates a production-ready GGUF model
"""
import os
import sys
import torch
import argparse
import subprocess
from pathlib import Path
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer


def merge_lora_adapter(base_model_path: str, lora_adapter_path: str, output_dir: str):
    """
    Merge LoRA adapter weights into base model
    
    Args:
        base_model_path: Path to base HuggingFace model
        lora_adapter_path: Path to fine-tuned LoRA adapter
        output_dir: Where to save merged model
    """
    print("=" * 80)
    print("MERGING LORA ADAPTER INTO BASE MODEL")
    print("=" * 80)
    print(f"Base Model: {base_model_path}")
    print(f"LoRA Adapter: {lora_adapter_path}")
    print(f"Output: {output_dir}")
    print()
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Load base model
    print("📥 Loading base model...")
    base_model = AutoModelForCausalLM.from_pretrained(
        base_model_path,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True
    )
    
    # Load tokenizer
    tokenizer = AutoTokenizer.from_pretrained(base_model_path, trust_remote_code=True)
    
    # Load and merge LoRA adapter
    print("🔗 Loading LoRA adapter...")
    model = PeftModel.from_pretrained(base_model, lora_adapter_path)
    
    print("⚙️  Merging LoRA weights into base model...")
    merged_model = model.merge_and_unload()
    
    # Save merged model
    print(f"💾 Saving merged model to {output_dir}...")
    merged_model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    
    print("✅ LoRA adapter merged successfully!")
    print()
    
    return output_dir


def convert_to_gguf(model_dir: str, quantization: str = "q6_k"):
    """
    Convert HuggingFace model to GGUF format for llama.cpp
    
    Args:
        model_dir: Path to HuggingFace model directory
        quantization: Quantization type (q4_k_m, q5_k_m, q6_k, q8_0, f16)
    """
    print("=" * 80)
    print("CONVERTING TO GGUF FORMAT")
    print("=" * 80)
    print(f"Input: {model_dir}")
    print(f"Quantization: {quantization.upper()}")
    print()
    
    # Find llama.cpp directory
    llamacpp_paths = [
        "/home/dgs/llama.cpp",
        os.path.expanduser("~/llama.cpp"),
        "../llama.cpp",
        "../../llama.cpp"
    ]
    
    llamacpp_dir = None
    for path in llamacpp_paths:
        if os.path.exists(path):
            llamacpp_dir = path
            break
    
    if not llamacpp_dir:
        print("⚠️  Warning: llama.cpp not found at common locations")
        print("   Expected locations:")
        for path in llamacpp_paths:
            print(f"   - {path}")
        print()
        print("   Download llama.cpp:")
        print("   git clone https://github.com/ggerganov/llama.cpp")
        print("   cd llama.cpp && make")
        return None
    
    print(f"✅ Found llama.cpp at: {llamacpp_dir}")
    
    # Convert to FP16 GGUF first
    model_name = Path(model_dir).name
    fp16_gguf = f"{model_dir}/{model_name}-fp16.gguf"
    
    print("🔄 Step 1: Converting to FP16 GGUF...")
    convert_script = os.path.join(llamacpp_dir, "convert_hf_to_gguf.py")
    
    if not os.path.exists(convert_script):
        # Try older script name
        convert_script = os.path.join(llamacpp_dir, "convert.py")
    
    cmd_convert = [
        "python",
        convert_script,
        model_dir,
        "--outtype", "f16",
        "--outfile", fp16_gguf
    ]
    
    print(f"   Running: {' '.join(cmd_convert)}")
    result = subprocess.run(cmd_convert, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"❌ Conversion failed: {result.stderr}")
        return None
    
    print(f"✅ Created FP16 GGUF: {fp16_gguf}")
    
    # Quantize if requested
    if quantization.lower() != "f16" and quantization.lower() != "fp16":
        print(f"🔄 Step 2: Quantizing to {quantization.upper()}...")
        
        quantized_gguf = f"{model_dir}/{model_name}-{quantization.upper()}.gguf"
        quantize_bin = os.path.join(llamacpp_dir, "llama-quantize")
        
        if not os.path.exists(quantize_bin):
            quantize_bin = os.path.join(llamacpp_dir, "build/bin/llama-quantize")
        
        if not os.path.exists(quantize_bin):
            print(f"⚠️  Warning: llama-quantize not found")
            print(f"   Build it: cd {llamacpp_dir} && make")
            return fp16_gguf
        
        cmd_quantize = [
            quantize_bin,
            fp16_gguf,
            quantized_gguf,
            quantization.upper()
        ]
        
        print(f"   Running: {' '.join(cmd_quantize)}")
        result = subprocess.run(cmd_quantize, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"⚠️  Quantization warning: {result.stderr}")
            print(f"   Using FP16 version: {fp16_gguf}")
            return fp16_gguf
        
        print(f"✅ Created quantized GGUF: {quantized_gguf}")
        
        # Remove FP16 intermediate file to save space
        if os.path.exists(fp16_gguf):
            os.remove(fp16_gguf)
            print(f"   Removed intermediate file: {fp16_gguf}")
        
        return quantized_gguf
    
    return fp16_gguf


def main():
    parser = argparse.ArgumentParser(
        description="Merge LoRA adapter and convert to GGUF for production"
    )
    
    parser.add_argument(
        "--base_model",
        required=True,
        help="Path to base HuggingFace model"
    )
    parser.add_argument(
        "--lora_adapter",
        required=True,
        help="Path to fine-tuned LoRA adapter"
    )
    parser.add_argument(
        "--output_dir",
        required=True,
        help="Output directory for merged model"
    )
    parser.add_argument(
        "--quantize",
        default="q6_k",
        choices=["q4_k_m", "q4_k_s", "q5_k_m", "q5_k_s", "q6_k", "q8_0", "f16"],
        help="GGUF quantization type (default: q6_k)"
    )
    parser.add_argument(
        "--skip_gguf",
        action="store_true",
        help="Only merge LoRA, skip GGUF conversion"
    )
    
    args = parser.parse_args()
    
    # Step 1: Merge LoRA adapter
    merged_dir = merge_lora_adapter(
        args.base_model,
        args.lora_adapter,
        args.output_dir
    )
    
    # Step 2: Convert to GGUF
    if not args.skip_gguf:
        gguf_path = convert_to_gguf(merged_dir, args.quantize)
        
        if gguf_path:
            print()
            print("=" * 80)
            print("🎉 CONVERSION COMPLETE!")
            print("=" * 80)
            print()
            print(f"📁 Merged HuggingFace model: {merged_dir}")
            print(f"📦 Production GGUF model: {gguf_path}")
            print()
            print("Next steps:")
            print("1. Test the GGUF model with llama.cpp:")
            print(f"   llama-server -m {gguf_path} --port 8090")
            print()
            print("2. Update model_router.py to use the new model:")
            print(f'   "bi-medix2-finetuned": "{gguf_path}"')
            print()
            print("3. Deploy to production with A/B testing")
            print()
        else:
            print()
            print("⚠️  GGUF conversion failed")
            print(f"   But merged HuggingFace model is available: {merged_dir}")
            print()
    else:
        print()
        print("=" * 80)
        print("✅ MERGE COMPLETE!")
        print("=" * 80)
        print()
        print(f"📁 Merged model saved to: {merged_dir}")
        print()
        print("To convert to GGUF later:")
        print(f"  python training/merge_and_convert.py --skip_merge --quantize q6_k {merged_dir}")


if __name__ == "__main__":
    main()
