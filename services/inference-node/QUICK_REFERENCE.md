# Quick Reference: vLLM & Model Management

## Status at a Glance

```bash
./bin/manage_vllm.sh status
```

**Current Status:**
- ✓ **BioMistral-7B FP16**: 11.6 GB downloaded (primary model)
- ✗ Qwen2.5-14B AWQ: Not started (11 GB, optional)
- ✗ Llama-3.1-8B AWQ: Not started (6 GB, optional)
- ✗ BioMistral-7B AWQ: Not started (5 GB, optional)

## Essential Commands

### Monitor Downloads
```bash
# Check status (no downloads)
./bin/manage_vllm.sh status

# Resume/complete BioMistral-7B FP16 download
./bin/manage_vllm.sh download biomistral-7b-fp16

# Download other models (one at a time)
./bin/manage_vllm.sh download qwen2.5-14b-awq
./bin/manage_vllm.sh download llama3.1-8b-awq

# Download all models (parallel)
./bin/manage_vllm.sh download --all
```

### Prepare for Production
```bash
# Install vLLM (high-performance inference)
./bin/manage_vllm.sh install-vllm

# Start service
./bin/manage_vllm.sh start-service

# Check service health
./bin/manage_vllm.sh health-check

# View logs
./bin/manage_vllm.sh logs
```

## Model Mapping (which model for which task)

| Agent Type | Model | Backend | Speed | Quality |
|------------|-------|---------|-------|---------|
| Chat | BioMistral-7B FP16 | vLLM | ⚡⚡ | ⭐⭐⭐ |
| Appointment | BioMistral-7B FP16 | vLLM | ⚡⚡ | ⭐⭐⭐ |
| MedicalQA | BioMistral-7B FP16 | vLLM | ⚡⚡ | ⭐⭐⭐ |
| Documentation | Medicine-LLM-13B | llama.cpp | ⚡ | ⭐⭐⭐ |
| Billing | OpenIns LLaMA3 | llama.cpp | ⚡⚡ | ⭐⭐ |

## Environment Variables

```bash
# Use these if needed (optional, defaults work fine)
export HF_TOKEN=hf_your_token_here           # For gated models
export MODEL_DIR=/custom/model/path          # Custom model location
export USE_VLLM=1                             # Force vLLM (if installed)
```

## Troubleshooting

### Download Interrupted?
```bash
# Just re-run, it auto-resumes
./bin/manage_vllm.sh download biomistral-7b-fp16
```

### Network Too Slow?
```bash
# Use sequential (one at a time)
./bin/manage_vllm.sh download --all --sequential
```

### vLLM Not Loading?
```bash
# 1. Check it's installed
pip list | grep vllm

# 2. Install if missing
./bin/manage_vllm.sh install-vllm

# 3. Check model path exists
ls -lh models/biomistral-7b-fp16/

# 4. Check logs
./bin/manage_vllm.sh logs
```

### Missing HF Token?
```bash
# Set it for gated model repos
export HF_TOKEN=hf_your_token
./bin/manage_vllm.sh download biomistral-7b-fp16
```

## File Locations

```
services/inference-node/
├── models/
│   ├── biomistral-7b-fp16/          ← Primary (11.6 GB)
│   ├── qwen2.5-14b-instruct-awq/    ← Optional (11 GB)
│   ├── llama3.1-8b-instruct-awq/    ← Optional (6 GB)
│   └── biomistral-7b-awq/            ← Optional (5 GB)
├── app/
│   ├── model_router.py              ← Agent→model mapping (UPDATED)
│   ├── vllm_config.py               ← vLLM engine configs (NEW)
│   ├── vllm_backend.py              ← vLLM integration (NEW)
│   └── main.py                      ← FastAPI service
├── bin/
│   ├── manage_vllm.sh               ← Management CLI (NEW)
│   └── download_models.py           ← Download manager (NEW)
└── docs/
    └── VLLM_SETUP.md                ← Full docs (NEW)
```

## Next Steps (Priority Order)

1. **Complete BioMistral download** (in progress, ~12 hours total)
   - Monitor with `./bin/manage_vllm.sh status`
   - Should reach ~14.5 GB

2. **Install vLLM** (optional but recommended)
   - `./bin/manage_vllm.sh install-vllm`
   - Provides ~2x speedup vs llama.cpp

3. **Start service** (once model ready)
   - `./bin/manage_vllm.sh start-service`
   - Service auto-detects models and initializes vLLM

4. **Test inference**
   - `curl http://localhost:8000/models`
   - POST to `/v1/chat/completions` with your prompt

5. **(Optional) Download secondary models**
   - For fallback / load balancing
   - `./bin/manage_vllm.sh download --all`

## Architecture Summary

```
User Request → FastAPI /v1/chat/completions
                ↓
          JWT + Rate Limit Middleware
                ↓
          ModelRouter (app/model_router.py)
                ├→ Agent Type?
                │   ├→ Chat/Appointment/MedicalQA → BioMistral-7B FP16
                │   └→ Documentation/Billing/Claims → GGUF fallbacks
                ├→ vLLM Available?
                │   ├→ Yes (vLLM Engine) → Fast inference ⚡⚡
                │   └→ No (llama.cpp/stub) → Fallback
                ↓
          Response with metadata
          (model name, backend, GPU IDs, latency)
```

---

**Last Updated:** 2025-12-25  
**vLLM Integration Status:** ✓ Configured & Ready  
**Primary Model:** BioMistral-7B FP16 (11.6 GB, 90% downloaded)
