#!/usr/bin/env python3
"""
AIDoctor GPU Performance Test
Tests BioMistral + Medicine-LLM dual-model capability and GPU utilization.
"""
import asyncio
import httpx
import json
import time
import subprocess
from datetime import datetime

class AIDoctorTest:
    """Test AIDoctor agent with complex medical scenarios."""
    
    # Test prompts
    PROMPTS = {
        "complex_comorbidity": {
            "question": "A 72-year-old diabetic patient with chronic kidney disease (eGFR 35), hypertension, and recent MI presents. Design a comprehensive treatment plan.",
            "difficulty": "Hard"
        },
        "drug_interactions": {
            "question": "What are the potential drug interactions between Warfarin, Aspirin, and Ibuprofen in a renal-impaired patient? What are clinical implications?",
            "difficulty": "Hard"
        },
        "differential_diagnosis": {
            "question": "Patient with fever, productive cough (yellow sputum), dyspnea, and pleuritic chest pain. CXR: right lower lobe infiltrate. Differential diagnosis and treatment?",
            "difficulty": "Medium"
        }
    }
    
    BASE_URL = "http://localhost:8000"
    
    async def get_gpu_usage(self):
        """Get current GPU memory usage."""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,nounits,noheader"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if lines:
                    used, total = map(int, lines[0].split(','))
                    return {"used_mb": used, "total_mb": total, "percent": (used/total)*100}
        except Exception as e:
            print(f"GPU check error: {e}")
        return None
    
    async def test_aindoctor(self, prompt_name: str, prompt_data: dict):
        """Test AIDoctor with a single prompt."""
        question = prompt_data["question"]
        difficulty = prompt_data["difficulty"]
        
        print(f"\n{'='*80}")
        print(f"📋 Test: {prompt_name} ({difficulty})")
        print(f"{'='*80}")
        print(f"Question: {question[:100]}...")
        
        # Get initial GPU state
        gpu_before = await self.get_gpu_usage()
        if gpu_before:
            print(f"📊 GPU Before: {gpu_before['used_mb']:.0f}MB / {gpu_before['total_mb']:.0f}MB ({gpu_before['percent']:.1f}%)")
        
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/v1/chat/completions",
                    json={
                        "agent_type": "AIDoctor",
                        "messages": [
                            {"role": "user", "content": question}
                        ],
                        "max_tokens": 512,
                        "temperature": 0.7
                    },
                    headers={
                        "Content-Type": "application/json",
                        "X-Agent-Type": "AIDoctor"
                    }
                )
                
                latency_ms = (time.time() - start_time) * 1000
                
                if response.status_code == 200:
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    model = data.get("model", "unknown")
                    tokens = data["usage"]["completion_tokens"]
                    tok_per_sec = (tokens / latency_ms) * 1000 if latency_ms > 0 else 0
                    
                    # Get GPU after inference
                    gpu_after = await self.get_gpu_usage()
                    if gpu_after:
                        print(f"📊 GPU After:  {gpu_after['used_mb']:.0f}MB / {gpu_after['total_mb']:.0f}MB ({gpu_after['percent']:.1f}%)")
                    
                    print(f"\n✅ SUCCESS")
                    print(f"⏱️  Latency:      {latency_ms:.0f}ms")
                    print(f"🚀 Throughput:   {tok_per_sec:.2f} tok/s")
                    print(f"📦 Tokens:       {tokens}")
                    print(f"🤖 Model:        {model}")
                    print(f"📝 Response:     {content[:150]}...")
                    
                    return {
                        "prompt": prompt_name,
                        "success": True,
                        "latency_ms": latency_ms,
                        "tokens": tokens,
                        "tok_per_sec": tok_per_sec,
                        "model": model,
                        "response_preview": content[:150]
                    }
                else:
                    print(f"\n❌ HTTP {response.status_code}")
                    print(f"Error: {response.text[:200]}")
                    return {
                        "prompt": prompt_name,
                        "success": False,
                        "error": f"HTTP {response.status_code}",
                        "latency_ms": latency_ms
                    }
        except httpx.ConnectError:
            print(f"\n❌ Cannot connect to server at {self.BASE_URL}")
            print("Make sure the API server is running: ALLOW_INSECURE_DEV=true uvicorn app.main:app --host 0.0.0.0 --port 8000")
            return {
                "prompt": prompt_name,
                "success": False,
                "error": "Connection failed",
                "latency_ms": time.time() - start_time
            }
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            print(f"\n❌ Error: {e}")
            return {
                "prompt": prompt_name,
                "success": False,
                "error": str(e),
                "latency_ms": latency_ms
            }
    
    async def run_all_tests(self):
        """Run all AIDoctor tests."""
        print("\n" + "="*80)
        print("🏥 AIDoctor GPU Performance Test Suite")
        print("="*80)
        print(f"Start time: {datetime.now().isoformat()}")
        print(f"Server: {self.BASE_URL}")
        
        results = []
        for prompt_name, prompt_data in self.PROMPTS.items():
            result = await self.test_aindoctor(prompt_name, prompt_data)
            results.append(result)
            await asyncio.sleep(2)  # Brief pause between tests
        
        # Summary
        print("\n" + "="*80)
        print("📊 SUMMARY")
        print("="*80)
        
        successful = [r for r in results if r["success"]]
        failed = [r for r in results if not r["success"]]
        
        print(f"\n✅ Successful: {len(successful)}/{len(results)}")
        if successful:
            avg_latency = sum(r["latency_ms"] for r in successful) / len(successful)
            avg_tok_sec = sum(r["tok_per_sec"] for r in successful) / len(successful)
            print(f"   Average Latency:  {avg_latency:.0f}ms")
            print(f"   Average Speed:    {avg_tok_sec:.2f} tok/s")
        
        print(f"\n❌ Failed: {len(failed)}/{len(results)}")
        if failed:
            for r in failed:
                print(f"   - {r['prompt']}: {r['error']}")
        
        print("\n" + "="*80)

async def main():
    tester = AIDoctorTest()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())
