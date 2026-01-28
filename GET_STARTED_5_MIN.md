# 🚀 Get Started in 5 Minutes

## Prerequisites

You need from Mediqzy.com:
- ✅ Base URL (e.g., `https://api.mediqzy.com`)
- ✅ API Key (e.g., `sk-mediqzy-xxxxx`)
- ✅ Model Name (e.g., `mediqzy-clinical`)

---

## Step 1: Configure (1 minute)

### Option A: Using Environment Variables

```bash
export EXTERNAL_LLM_ENABLED=true
export EXTERNAL_LLM_PROVIDER=mediqzy
export EXTERNAL_LLM_BASE_URL=https://api.mediqzy.com
export EXTERNAL_LLM_API_KEY=your-api-key-here
export EXTERNAL_LLM_MODEL=mediqzy-clinical
export EXTERNAL_LLM_TEMPERATURE=0.7
export EXTERNAL_LLM_MAX_TOKENS=2048
```

### Option B: Using .env File

Create `.env` in `/home/dgs/N3090/services/inference-node/`:

```bash
EXTERNAL_LLM_ENABLED=true
EXTERNAL_LLM_PROVIDER=mediqzy
EXTERNAL_LLM_BASE_URL=https://api.mediqzy.com
EXTERNAL_LLM_API_KEY=your-api-key-here
EXTERNAL_LLM_MODEL=mediqzy-clinical
EXTERNAL_LLM_TEMPERATURE=0.7
EXTERNAL_LLM_MAX_TOKENS=2048
```

### Option C: Using Docker

Create `.env` file, then:

```bash
docker-compose -f docker-compose.external-llm.yml up -d
```

---

## Step 2: Start Service (1 minute)

```bash
cd /home/dgs/N3090/services/inference-node

# Start with Mediqzy routing
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

## Step 3: Test It (1 minute)

### Basic Test

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "What is hypertension?"}
    ],
    "agent_type": "MedicalQA"
  }'
```

### Expected Response

```json
{
  "id": "cmpl-...",
  "created": 1704729600,
  "model": "mediqzy:mediqzy-clinical",
  "choices": [{
    "message": {
      "role": "assistant",
      "content": "Hypertension is a chronic condition where blood pressure is..."
    }
  }],
  "usage": {
    "prompt_tokens": 12,
    "completion_tokens": 150,
    "total_tokens": 162
  }
}
```

✅ If you see `"model": "mediqzy:mediqzy-clinical"`, it's working!

---

## Step 4: Verify Fallback (1 minute)

To test that fallback works if Mediqzy goes down:

```bash
# Simulate API error by setting wrong key
export EXTERNAL_LLM_API_KEY=invalid-key

# Restart service
# Test again - should still work but use local model
```

Look for in logs:
```
falling back to local
```

---

## Step 5: Check Logs (Optional)

```bash
# See all Mediqzy routing decisions
tail -f logs/inference.log | grep -i "external_llm"

# Count successful external LLM calls
grep "Routing to external LLM" logs/inference.log | wc -l
```

---

## ✅ You're Done!

Your N3090 is now connected to Mediqzy.com! 🎉

### What Happens Now

1. **Every request** to `/v1/chat/completions` goes to Mediqzy first
2. **If Mediqzy fails**, automatically uses local models
3. **Responses** are in OpenAI format (compatible everywhere)
4. **Tokens** are tracked and reported

---

## Next Steps

### For Production

1. **Update credentials in secrets manager** (don't hardcode)
2. **Monitor response times**
3. **Set up alerts** for high fallback rate
4. **Review costs** (if using paid tier)

### For Development

1. **Try different models** by changing `EXTERNAL_LLM_MODEL`
2. **Tune temperature** from 0 (precise) to 1 (creative)
3. **Experiment with agent types** (Claims, Documentation, etc.)

---

## Common Issues

| Issue | Fix |
|-------|-----|
| "Connection refused" | Check `EXTERNAL_LLM_BASE_URL` is correct |
| "401 Unauthorized" | Verify `EXTERNAL_LLM_API_KEY` |
| Always uses local | Ensure `EXTERNAL_LLM_ENABLED=true` |
| Timeout errors | Increase `EXTERNAL_LLM_TIMEOUT=60` |

---

## More Information

- 📖 **Full Setup Guide**: `MEDIQZY_QUICK_START.md`
- 📚 **Complete Reference**: `docs/EXTERNAL_LLM_INTEGRATION.md`
- 💻 **Code Examples**: `MEDIQZY_API_EXAMPLES.md`
- 📋 **File Index**: `FILE_INDEX.md`

---

## Support

Get help:
1. Check `MEDIQZY_QUICK_START.md` troubleshooting section
2. Review logs: `tail -f logs/inference.log`
3. Verify config: `env | grep EXTERNAL_LLM`
4. Test manually: `curl -v https://api.mediqzy.com/v1/models`

---

**Ready to use!** 🚀
