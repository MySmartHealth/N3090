# Synthetic Intelligence Platform – Engineering Blueprint

This repo contains actionable scaffolding aligned to the design:
- AWS control plane as system of record
- Local GPU nodes as stateless inference appliances
- Deterministic, audited workflows (Step Functions)

## Components
- services/inference-node: OpenAI-compatible FastAPI with guardrails
- infra/aws: IaC stubs and provisioning notes
- scripts: operational helpers
- docs/RTX3090_Specialist_Node_Blueprint.md: Presentation-ready node blueprint

## Compliance & Audit
- No PHI persisted locally
- Logs store prompt/response hashes, not raw content
- AWS S3 Object Lock for immutable logs (control plane)

## Next Work
- Integrate vLLM/model router
- Implement AWS Step Functions + Rules Engine
- Node registry + heartbeat service
