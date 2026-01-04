#!/usr/bin/env python3
"""
Direct test of Qwen model via llama.cpp backend.
"""
import asyncio
import httpx
import json
import time

BASE_URL = "http://localhost:8081"  # BiMediX on 8081
QWEN_URL = "http://localhost:8080"  # Assuming Qwen is on 8080 or check which port

async def test_qwen():
    """Test Qwen 0.6B directly via llama.cpp."""
    print("🧪 Testing Qwen 0.6B-Medical (GGUF) via llama.cpp...")
    
    # First, find which port Qwen is on
    ports_to_try = [8080, 8082, 8086, 8087]
    qwen_port = None
    
    async with httpx.AsyncClient(timeout=5) as client:
        for port in ports_to_try:
            try:
                resp = await client.get(f"http://localhost:{port}/health")
                if resp.status_code == 200:
                    print(f"✅ Found llama.cpp server on port {port}")
                    qwen_port = port
                    break
            except:
                pass
    
    if not qwen_port:
        print("❌ Could not find llama.cpp server")
        return
    
    # Now test a simple prompt
    prompt = "What is the fastest treatment for acute pain?"
    
    async with httpx.AsyncClient(timeout=120) as client:
        start_time = time.time()
        
        payload = {
            "prompt": prompt,
            "n_predict": 128,
            "temperature": 0.7,
        }
        
        try:
            resp = await client.post(
                f"http://localhost:{qwen_port}/completion",
                json=payload,
                headers={"Authorization": "Bearer dev-key"},
                timeout=120
            )
            
            latency = (time.time() - start_time) * 1000
            
            if resp.status_code == 200:
                data = resp.json()
                result = data.get("content", "")
                print(f"\n⚡ Latency: {latency:.0f}ms")
                print(f"📝 Response: {result[:200]}...")
                print(f"\n✅ Qwen 0.6B is working!")
            else:
                print(f"❌ HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_qwen())
