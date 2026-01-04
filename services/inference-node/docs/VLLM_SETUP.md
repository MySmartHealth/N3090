# vLLM Configuration & Management

This directory contains configurations for running high-performance vLLM inference on RTX 3090.

## Quick Start

### 1. Check Model Download Status
```bash
cd /home/dgs/N3090/services/inference-node
source .venv/bin/activate

# See which models are downloaded
python bin/download_models.py --status
```

### 2. Download Models (with retry & resume)
```bash
# Download BioMistral-7B FP16 (primary)
python bin/download_models.py biomistral-7b-fp16

# Download all AWQ models
python bin/download_models.py qwen2.5-14b-awq llama3.1-8b-awq biomistral-7b-awq

# Download all models
python bin/download_models.py --all

# Download sequentially (one at a time, better for network stability)
python bin/download_models.py biomistral-7b-fp16 --sequential
```

### 3. Activate vLLM Engine (Future)
Once models are downloaded, the vLLM backend will auto-initialize on service startup:
```bash
python bin/serve.sh
# or
pm2 start ecosystem.config.js
```

The app will:
1. Check for downloaded models
2. Initialize vLLM engines for available models
3. Use vLLM for high-speed inference (vs llama.cpp fallback)

## Models Configured

| Model | Type | Size | Backend | Status |
|-------|------|------|---------|--------|
| BioMistral-7B FP16 | Biomedical | 14.5 GB | vLLM | Primary ✓ |
| Qwen2.5-14B AWQ | General | 11 GB | vLLM | Optional |
| Llama-3.1-8B AWQ | General | 6 GB | vLLM | Optional |
| BioMistral-7B AWQ | Biomedical | 5 GB | vLLM | Optional |

**Agent Mapping** (in `app/model_router.py`):
- `Chat`, `Appointment`, `MedicalQA` → BioMistral-7B FP16 (clinical tasks)
- `Documentation`, `Billing`, `Claims` → Fallback to GGUF models (llama.cpp)

## Troubleshooting

### Download Interrupted?
The download manager automatically resumes from where it left off:
```bash
python bin/download_models.py biomistral-7b-fp16
```

### Network Issues?
Use `--retries` to increase retry attempts (default: 3):
```bash
python bin/download_models.py biomistral-7b-fp16 --retries 5
```

### Model Path Not Found?
Set `MODEL_DIR` env var:
```bash
export MODEL_DIR=/path/to/models
python bin/download_models.py --status
```

### HF Token Missing?
Set it before downloading:
```bash
export HF_TOKEN=hf_xxxxxxxxxxxx
python bin/download_models.py biomistral-7b-fp16
```

## Architecture

### vLLM Engine Management (`app/vllm_config.py`)
- `vLLMEngineConfig`: Dataclass for model + engine settings
- `vLLMEngineRegistry`: Catalog of all vLLM models
- `vLLMEngineManager`: Lifecycle management (init, health check, etc.)

### Download Manager (`bin/download_models.py`)
- `HFDownloader`: Wraps huggingface_hub with retry + resume
- `ModelDownloadConfig`: Catalog of models with HF repo IDs
- CLI: `python bin/download_models.py [model_keys] [--options]`

### Model Router Updates (`app/model_router.py`)
- Added `biomistral-7b-fp16` model config (vLLM backend)
- Updated agent mappings: Chat, Appointment, MedicalQA → BioMistral FP16
- Supports both vLLM (FP16/AWQ) and llama.cpp (GGUF) backends

## Future Enhancements

1. **vLLM Integration**: Replace stub `_stub_generate()` with actual vLLM calls
2. **Multi-GPU Load Balancing**: Distribute AWQ models across 3060
3. **Model Preloading**: Warm up engines on startup with sample tokens
4. **Performance Metrics**: Latency, throughput, memory tracking per model
5. **Graceful Fallback**: Auto-switch to GGUF if vLLM unavailable
