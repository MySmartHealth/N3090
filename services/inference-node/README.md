# Inference Node (Stateless AI Appliance)

Implements an OpenAI-compatible endpoint with strict guardrails.

## Key Properties
- Stateless, no local PHI persistence
- Short-lived JWT auth (dev bypass if unset)
- Request-scoped memory only
- Logs prompt/response hashes, not content

## Endpoint
- POST /v1/chat/completions

## Quick Start (Linux)
```bash
cd services/inference-node
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Dev mode: bypass JWT if no secret set
UVICORN_PORT=8000 uvicorn app.main:app --host 0.0.0.0 --port ${UVICORN_PORT} --no-access-log
```

## Test Request (Dev mode)
```bash
curl -sS http://localhost:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -H 'X-Agent-Type: Documentation' \
  -d '{
    "request_id": "req-123",
    "agent_type": "Documentation",
    "model": "qwen-14b",
    "constraints": {"mode": "draft-only"},
    "messages": [
      {"role":"system","content":"You are drafting clinical notes. Do not finalize."},
      {"role":"user","content":"Patient presents with mild cough."}
    ]
  }' | jq .
```

## Environment Variables
- JWT_SECRET: HMAC secret for HS256 verification
- JWT_ISSUER, JWT_AUDIENCE: Optional claims checks
- ALLOW_INSECURE_DEV=true: Explicitly allow dev bypass (if set)
 - UVICORN_PORT: Port to bind, default 8000

## Notes
- Integrate vLLM or model backends in `ModelRouter` later.
- Do not log raw prompts or responses.

## PM2 (Process Manager) Usage
PM2 can supervise the service without Docker.

1) Install prerequisites (Debian/Ubuntu):
```bash
sudo apt update
sudo apt install -y python3-pip python3-venv
# Optional CUDA toolkit
cd /home/dgs/N3090
INSTALL_CUDA=true CUDA_TOOLKIT_VERSION=12-4 ./scripts/local_prereqs.sh
echo 'export PATH=/usr/local/cuda/bin:$PATH' >> ~/.bashrc
source ~/.bashrc
nvidia-smi
nvcc --version
```

2) Build and run llama.cpp GPU server (GGUF):
```bash
cd /home/dgs/N3090/services/inference-node
chmod +x bin/llama_cpp_server.sh
# Build CUDA-enabled server binary once
bin/llama_cpp_server.sh build
# Serve BiMediX2 GGUF on GPU with OpenAI-compatible /v1/chat/completions
MODEL=./models/BiMediX2-8B-hf.i1-Q6_K.gguf LLAMA_CPP_PORT=8080 bin/llama_cpp_server.sh run
# Point FastAPI to the server
export LLAMA_CPP_SERVER=http://127.0.0.1:8080
```

3) Start via PM2 from repo root:
```bash
pm2 start services/inference-node/ecosystem.config.js --env development
pm2 status
```

4) Persist across reboots:
```bash
pm2 save
pm2 startup systemd
# Follow the printed command to enable the service
```

Production variables can be set in the `env_production` section of `ecosystem.config.js`.

## PM2 Remote Deploy
See detailed steps in [docs/PM2_DEPLOY.md](../../docs/PM2_DEPLOY.md).

Quick commands (after editing placeholders in `deploy.production`):
```bash
# One-time setup
pm2 deploy services/inference-node/ecosystem.config.js production setup

# Deploy latest main
pm2 deploy services/inference-node/ecosystem.config.js production
```
