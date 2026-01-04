# Model Artifacts Directory

Place local model weights and tokenizer assets here.

## Suggested Layout
- bimedix2/
- mixtral-8x7b/
- qwen-14b/
- llama-8b/
- chatdoctor/

## Notes
- This folder is not tracked for large binaries; add models to your own storage.
- Keep permissions restrictive; no PHI should be stored.
- Update `ModelRegistry` paths in `app/model_router.py` to match your local layout.
