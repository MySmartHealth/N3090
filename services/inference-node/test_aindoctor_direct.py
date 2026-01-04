#!/usr/bin/env python3
"""
AIDoctor GPU Test - Direct llama.cpp Testing
Tests BioMistral (port 8085) and Medicine-LLM (port 8081) directly via llama.cpp
Avoids FastAPI complexity for quick GPU benchmarking.
"""
import asyncio
import httpx
import json
import time
import subprocess
from datetime import datetime

class AIDoctorGPUTest:
    """Direct test of BioMistral + Medicine-LLM via llama.cpp."""
    
    # BioMistral endpoint (Clinical expertise - port 8085)
    BIOMISTRAL_URL = "http://localhost:8085"
    # Medicine-LLM endpoint (Comprehensive knowledge - port 8081)  
    MEDICINE_LLM_URL = "http://localhost:8081"
    
    API_KEY = "dev-key"
    
    PROMPTS = {
        "complex_comorbidity": "A 72-year-old diabetic patient with chronic kidney disease (eGFR 35), hypertension, and recent MI presents. Design a comprehensive treatment plan considering comorbidities and drug interactions.",
        "drug_interactions": "What are the potential drug interactions between Warfarin, Aspirin, and Ibuprofen in a renal-impaired patient? What are clinical implications?",
        "differential_diagnosis": "Patient with fever, productive cough (yellow sputum), dyspnea, and pleuritic chest pain. CXR shows right lower lobe infiltrate. What is the most likely diagnosis and recommended treatment?"
    }
    
    async def get_gpu_usage(self):
        """Get current GPU memory usage."""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu", "--format=csv,nounits,noheader"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if lines:
                    parts = lines[0].split(',')
                    used, total, util = int(parts[0]), int(parts[1]), int(parts[2])
                    return {
                        "used_mb": used,
                        "total_mb": total,
                        "percent": (used/total)*100,
                        "util_percent": util
                    }
        except:
            pass
        return None
    
    async def test_model(self, model_name: str, url: str, prompt: str):
        """Test a single model."""
        print(f"\n{'─'*70}")
        print(f"🤖 Testing: {model_name}")
        print(f"   URL: {url}")
        
        gpu_before = await self.get_gpu_usage()
        if gpu_before:
            print(f"   GPU Before: {gpu_before['used_mb']}MB ({gpu_before['percent']:.1f}%) | Util: {gpu_before['util_percent']}%")
        
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                payload = {
                    "prompt": prompt,
                    "n_predict": 256,
                    "temperature": 0.7,
                }
                
                resp = await client.post(
                    f"{url}/completion",
                    json=payload,
                    headers={"Authorization": f"Bearer {self.API_KEY}"},
                    timeout=120
                )
                
                latency_ms = (time.time() - start_time) * 1000
                
                if resp.status_code == 200:
                    data = resp.json()
                    content = data.get("content", "")
                    tokens_predicted = data.get("tokens_predicted", 0)
                    tokens_evaluated = data.get("tokens_evaluated", 0)
                    
                    # Total tokens is predicted + evaluated
                    tokens = tokens_predicted + tokens_evaluated
                    
                    tok_per_sec = (tokens / latency_ms) * 1000 if latency_ms > 0 else 0
                    
                    gpu_after = await self.get_gpu_usage()
                    if gpu_after:
                        print(f"   GPU After:  {gpu_after['used_mb']}MB ({gpu_after['percent']:.1f}%) | Util: {gpu_after['util_percent']}%")
                    
                    print(f"\n   ✅ Success")
                    print(f"   ⏱️  Latency:    {latency_ms:.0f}ms")
                    print(f"   🚀 Throughput: {tok_per_sec:.2f} tok/s")
                    print(f"   📦 Tokens:     {tokens}")
                    print(f"   💬 Response:   {content[:100].strip()}...")
                    
                    return {
                        "model": model_name,
                        "success": True,
                        "latency_ms": latency_ms,
                        "tokens": tokens,
                        "tok_per_sec": tok_per_sec,
                        "response": content[:100]
                    }
                else:
                    print(f"   ❌ HTTP {resp.status_code}")
                    print(f"   Error: {resp.text[:200]}")
                    return {
                        "model": model_name,
                        "success": False,
                        "error": f"HTTP {resp.status_code}",
                        "latency_ms": latency_ms
                    }
        except httpx.ConnectError as e:
            print(f"   ❌ Connection Failed: {str(e)[:100]}")
            return {
                "model": model_name,
                "success": False,
                "error": f"Cannot connect to {url}",
                "latency_ms": (time.time() - start_time) * 1000
            }
        except Exception as e:
            print(f"   ❌ Error: {str(e)[:100]}")
            return {
                "model": model_name,
                "success": False,
                "error": str(e)[:100],
                "latency_ms": (time.time() - start_time) * 1000
            }
    
    async def run_benchmark(self):
        """Run full AIDoctor benchmark."""
        print("\n" + "="*70)
        print("🏥 AIDoctor Dual-Model GPU Benchmark")
        print("="*70)
        print(f"Start: {datetime.now().isoformat()}")
        print(f"Models: BioMistral (Clinical) + Medicine-LLM (Knowledge Base)")
        
        # Print GPU info
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,compute_cap", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            print(f"GPU: {result.stdout.strip()}")
        
        all_results = []
        
        for prompt_name, prompt_text in self.PROMPTS.items():
            print(f"\n\n{'='*70}")
            print(f"📝 Test: {prompt_name.upper()}")
            print(f"{'='*70}")
            print(f"Prompt: {prompt_text[:80]}...")
            
            # Test BioMistral
            bio_result = await self.test_model(
                "BioMistral-7B (Clinical)",
                self.BIOMISTRAL_URL,
                prompt_text
            )
            all_results.append(bio_result)
            
            await asyncio.sleep(2)
            
            # Test Medicine-LLM
            med_result = await self.test_model(
                "Medicine-LLM-13B (Knowledge)",
                self.MEDICINE_LLM_URL,
                prompt_text
            )
            all_results.append(med_result)
            
            await asyncio.sleep(2)
        
        # Summary
        print(f"\n\n{'='*70}")
        print("📊 BENCHMARK SUMMARY")
        print("="*70)
        
        successful = [r for r in all_results if r["success"]]
        failed = [r for r in all_results if not r["success"]]
        
        print(f"\n✅ Successful: {len(successful)}/{len(all_results)}")
        if successful:
            avg_latency = sum(r["latency_ms"] for r in successful) / len(successful)
            avg_tok_sec = sum(r["tok_per_sec"] for r in successful) / len(successful)
            print(f"   Avg Latency:  {avg_latency:.0f}ms")
            print(f"   Avg Speed:    {avg_tok_sec:.2f} tok/s")
            print(f"\n   By Model:")
            for model in ["BioMistral-7B (Clinical)", "Medicine-LLM-13B (Knowledge)"]:
                model_results = [r for r in successful if r["model"] == model]
                if model_results:
                    m_lat = sum(r["latency_ms"] for r in model_results) / len(model_results)
                    m_tok = sum(r["tok_per_sec"] for r in model_results) / len(model_results)
                    print(f"   • {model:30s}: {m_lat:6.0f}ms | {m_tok:5.2f} tok/s")
        
        print(f"\n❌ Failed: {len(failed)}/{len(all_results)}")
        if failed:
            for r in failed:
                print(f"   • {r['model']:30s}: {r['error'][:40]}")
        
        print(f"\n{'='*70}\n")

async def main():
    tester = AIDoctorGPUTest()
    await tester.run_benchmark()

if __name__ == "__main__":
    asyncio.run(main())
