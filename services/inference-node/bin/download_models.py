#!/usr/bin/env python3
"""
Model Download Manager
Robust downloader with retry, resume, and parallel support for Hugging Face models.
"""
import os
import sys
import argparse
import time
import json
from pathlib import Path
from typing import Dict, List, Optional
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


class ModelDownloadConfig:
    """Configuration for models to download per RTX3090 Blueprint."""
    MODELS = {
        # PRIMARY: Medical Q&A Agent (BiMediX2)
        "bimedix2-8b-fp16": {
            "repo_id": "BioMistral/BiMediX2-8B",  # or specific repo
            "local_dir": "models/BiMediX2-8B-fp16",
            "allow_patterns": ["*.safetensors", "*.bin", "*.json", "*.txt", "*.md", "*tokenizer*"],
            "size_gb": 20.0,
            "description": "BiMediX2-8B FP16 (Medical Q&A + multimodal, blueprint primary)",
        },
        # CLAIMS PROCESSING: Mixtral 8x7B
        "mixtral-8x7b-4bit": {
            "repo_id": "TheBloke/Mixtral-8x7B-Instruct-v0.1-GPTQ",
            "local_dir": "models/mixtral-8x7b-4bit",
            "allow_patterns": ["*.safetensors", "*.json", "*tokenizer*", "*.txt", "*.md"],
            "size_gb": 14.0,
            "description": "Mixtral-8x7B 4-bit (Claims parsing & adjudication)",
        },
        # DOCUMENTATION: Qwen 2.5 14B
        "qwen2.5-14b-4bit": {
            "repo_id": "TheBloke/Qwen2.5-14B-Instruct-GPTQ",
            "local_dir": "models/qwen2.5-14b-4bit",
            "allow_patterns": ["*.safetensors", "*.json", "*tokenizer*", "*.txt", "*.md"],
            "size_gb": 12.0,
            "description": "Qwen2.5-14B 4-bit (Documentation/Coverage adjudication)",
        },
        # PATIENT CHAT/TRIAGE: ChatDoctor 7B
        "chatdoctor-7b-fp16": {
            "repo_id": "MediaBankAI/ChatDoctor-7B",
            "local_dir": "models/chatdoctor-7b-fp16",
            "allow_patterns": ["*.safetensors", "*.bin", "*.json", "*tokenizer*", "*.txt", "*.md"],
            "size_gb": 14.0,
            "description": "ChatDoctor-7B FP16 (Patient chat/triage, lightweight)",
        },
    }


class HFDownloader:
    """Hugging Face model downloader with retry and resume."""
    
    def __init__(self, hf_token: Optional[str] = None, max_retries: int = 3):
        self.hf_token = hf_token or os.getenv("HF_TOKEN")
        self.max_retries = max_retries
        
        if not self.hf_token:
            logger.warning("HF_TOKEN not set; some models may require authentication")
    
    def download_model(
        self,
        repo_id: str,
        local_dir: str,
        allow_patterns: Optional[List[str]] = None,
        max_retries: Optional[int] = None,
    ) -> bool:
        """
        Download model with retry and resume logic.
        
        Returns:
            True if download succeeded, False otherwise.
        """
        max_retries = max_retries or self.max_retries
        attempt = 0
        
        while attempt < max_retries:
            attempt += 1
            logger.info(
                f"Download attempt {attempt}/{max_retries}: "
                f"{repo_id} → {local_dir}"
            )
            
            try:
                from huggingface_hub import snapshot_download
                
                # Disable hf-transfer to avoid xet protocol issues
                os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"
                
                snapshot_download(
                    repo_id=repo_id,
                    repo_type="model",
                    local_dir=local_dir,
                    allow_patterns=allow_patterns,
                    token=self.hf_token,
                    resume_download=True,  # Auto-resume from interruption
                    cache_dir=None,  # Don't use cache, download directly
                )
                
                logger.info(f"✓ Successfully downloaded {repo_id}")
                return True
            
            except Exception as e:
                logger.error(f"✗ Attempt {attempt} failed: {type(e).__name__}: {str(e)[:100]}")
                
                if attempt < max_retries:
                    wait_time = min(2 ** attempt, 60)  # Exponential backoff, max 60s
                    logger.info(f"Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Failed to download {repo_id} after {max_retries} attempts")
                    return False
        
        return False
    
    def download_batch(self, models: Dict[str, Dict], sequential: bool = False) -> Dict[str, bool]:
        """
        Download multiple models.
        
        Args:
            models: Dict of model_key -> {repo_id, local_dir, allow_patterns}
            sequential: If True, download one at a time. If False, parallel (default).
        
        Returns:
            Dict of model_key -> success_bool
        """
        results = {}
        
        if sequential:
            for model_key, config in models.items():
                results[model_key] = self.download_model(
                    repo_id=config["repo_id"],
                    local_dir=config["local_dir"],
                    allow_patterns=config.get("allow_patterns"),
                )
        else:
            # For parallel, use ThreadPoolExecutor
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = {
                    executor.submit(
                        self.download_model,
                        config["repo_id"],
                        config["local_dir"],
                        config.get("allow_patterns"),
                    ): model_key
                    for model_key, config in models.items()
                }
                
                for future in as_completed(futures):
                    model_key = futures[future]
                    try:
                        results[model_key] = future.result()
                    except Exception as e:
                        logger.error(f"Error downloading {model_key}: {e}")
                        results[model_key] = False
        
        return results


def main():
    """CLI for model downloads."""
    parser = argparse.ArgumentParser(
        description="Download LLM models from Hugging Face Hub"
    )
    parser.add_argument(
        "models",
        nargs="*",
        help="Model keys to download (biomistral-7b-fp16, qwen2.5-14b-awq, etc.). "
             "If none specified, list available models.",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("HF_TOKEN"),
        help="Hugging Face API token (default: HF_TOKEN env var)",
    )
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="Download one model at a time instead of parallel",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Max retries per model (default: 3)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Download all available models",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Check download status of all models",
    )
    
    args = parser.parse_args()
    
    config = ModelDownloadConfig()
    downloader = HFDownloader(hf_token=args.token, max_retries=args.retries)
    
    # Status check mode
    if args.status:
        logger.info("Model download status:")
        for model_key, model_config in config.MODELS.items():
            local_dir = model_config["local_dir"]
            exists = os.path.isdir(local_dir)
            size = ""
            if exists:
                size_bytes = sum(
                    f.stat().st_size
                    for f in Path(local_dir).rglob("*")
                    if f.is_file()
                )
                size_gb = size_bytes / (1024**3)
                size = f" ({size_gb:.1f} GB)"
            
            status = "✓" if exists else "✗"
            logger.info(f"  {status} {model_key}: {model_config['description']}{size}")
        return 0
    
    # Determine models to download
    if args.all:
        models_to_dl = config.MODELS
    elif args.models:
        models_to_dl = {k: config.MODELS[k] for k in args.models if k in config.MODELS}
        unknown = set(args.models) - set(config.MODELS.keys())
        if unknown:
            logger.error(f"Unknown models: {unknown}")
            logger.info(f"Available: {', '.join(config.MODELS.keys())}")
            return 1
    else:
        logger.info("Available models:")
        for model_key, model_config in config.MODELS.items():
            logger.info(f"  {model_key}: {model_config['description']} (~{model_config['size_gb']} GB)")
        logger.info("\nRun with model key(s) to download, or --all to download all.")
        return 0
    
    if not models_to_dl:
        logger.error("No models selected for download")
        return 1
    
    logger.info(f"Downloading {len(models_to_dl)} model(s) ({'sequential' if args.sequential else 'parallel'})...")
    results = downloader.download_batch(models_to_dl, sequential=args.sequential)
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("Download Summary:")
    for model_key, success in results.items():
        status = "✓ SUCCESS" if success else "✗ FAILED"
        logger.info(f"  {status}: {model_key}")
    
    all_success = all(results.values())
    logger.info("="*60)
    
    return 0 if all_success else 1


if __name__ == "__main__":
    sys.exit(main())
