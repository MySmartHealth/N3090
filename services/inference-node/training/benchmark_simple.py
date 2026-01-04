#!/usr/bin/env python3
"""
Simple benchmark for Qwen-0.6B medical model
Tests directly against running llama.cpp servers
"""
import requests
import time
import json

# Running model servers (from ecosystem.config.js)
MODELS = {
    "qwen-0.6b-medical": "http://localhost:8086/v1/chat/completions",
    "tiny-llama-1b": "http://localhost:8083/v1/chat/completions",
    "bi-medix2": "http://localhost:8081/v1/chat/completions",
    "bio-mistral-7b": "http://localhost:8085/v1/chat/completions",
}

# Healthcare benchmark tasks
TASKS = [
    {
        "name": "Medical QA",
        "prompt": "What are the common symptoms of Type 2 diabetes?",
        "keywords": ["thirst", "urination", "hunger", "fatigue"]
    },
    {
        "name": "ICD-10 Coding",
        "prompt": "What is the ICD-10 code for Type 2 diabetes without complications?",
        "keywords": ["E11.9"]
    },
    {
        "name": "Prescription",
        "prompt": "Prescribe for hypertension, BP 150/95, age 45.",
        "keywords": ["lisinopril", "amlodipine", "10mg", "daily"]
    },
    {
        "name": "Claims Analysis",
        "prompt": "Is diagnosis E11.9 and procedure 99213 appropriate for routine diabetes visit?",
        "keywords": ["appropriate", "yes", "routine"]
    },
    {
        "name": "Patient Triage",
        "prompt": "Patient: severe chest pain, left arm pain, sweating. Urgency?",
        "keywords": ["emergency", "urgent", "911", "immediate"]
    },
    {
        "name": "Simple Chat",
        "prompt": "What is diabetes?",
        "keywords": ["blood sugar", "glucose", "insulin"]
    }
]


def test_model(model_name, endpoint):
    """Benchmark a single model"""
    print(f"\n{'='*70}")
    print(f"Testing: {model_name}")
    print(f"{'='*70}")
    
    # Check if server is running
    try:
        health_check = endpoint.replace("/v1/chat/completions", "/health")
        requests.get(health_check, timeout=2)
    except:
        print(f"❌ Server not running at {endpoint}")
        return None
    
    results = []
    total_time = 0
    total_relevance = 0
    
    for task in TASKS:
        print(f"\n📋 {task['name']}")
        print(f"   Q: {task['prompt'][:60]}...")
        
        payload = {
            "messages": [{"role": "user", "content": task['prompt']}],
            "temperature": 0.3,
            "max_tokens": 150
        }
        
        try:
            start = time.time()
            response = requests.post(endpoint, json=payload, timeout=60)
            end = time.time()
            
            if response.status_code == 200:
                data = response.json()
                answer = data['choices'][0]['message']['content']
                inference_time = end - start
                
                # Calculate relevance
                found = sum(1 for kw in task['keywords'] if kw.lower() in answer.lower())
                relevance = found / len(task['keywords'])
                
                total_time += inference_time
                total_relevance += relevance
                
                print(f"   ⏱️  {inference_time:.2f}s | 🎯 {relevance:.0%} | 📏 {len(answer)} chars")
                print(f"   A: {answer[:80]}...")
                
                results.append({
                    "task": task['name'],
                    "time": round(inference_time, 2),
                    "relevance": round(relevance, 2),
                    "length": len(answer)
                })
            else:
                print(f"   ❌ Error: HTTP {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    if results:
        avg_time = total_time / len(results)
        avg_relevance = total_relevance / len(results)
        
        print(f"\n{'─'*70}")
        print(f"Summary: {len(results)}/{len(TASKS)} tasks completed")
        print(f"  Avg Time: {avg_time:.2f}s")
        print(f"  Avg Relevance: {avg_relevance:.0%}")
        print(f"  Total Time: {total_time:.1f}s")
        
        return {
            "model": model_name,
            "tasks_completed": len(results),
            "avg_time": round(avg_time, 2),
            "avg_relevance": round(avg_relevance, 2),
            "total_time": round(total_time, 2),
            "details": results
        }
    
    return None


def main():
    print("="*70)
    print("QWEN-0.6B MEDICAL MODEL BENCHMARK")
    print("="*70)
    print("\n📊 Testing across 6 healthcare tasks")
    print("🔬 Comparing with other medical models\n")
    
    all_results = {}
    
    for model_name, endpoint in MODELS.items():
        result = test_model(model_name, endpoint)
        if result:
            all_results[model_name] = result
    
    # Comparison table
    if len(all_results) > 1:
        print(f"\n\n{'='*70}")
        print("COMPARISON TABLE")
        print(f"{'='*70}\n")
        
        print(f"{'Model':<25} {'Avg Time':<12} {'Relevance':<12} {'Total Time'}")
        print(f"{'-'*70}")
        
        for model, data in sorted(all_results.items(), key=lambda x: x[1]['avg_time']):
            print(f"{model:<25} {data['avg_time']:<11.2f}s {data['avg_relevance']:<11.0%} {data['total_time']:.1f}s")
        
        # Recommendations
        print(f"\n{'='*70}")
        print("RECOMMENDATIONS")
        print(f"{'='*70}\n")
        
        fastest = min(all_results.items(), key=lambda x: x[1]['avg_time'])
        most_accurate = max(all_results.items(), key=lambda x: x[1]['avg_relevance'])
        
        print(f"⚡ Fastest: {fastest[0]} ({fastest[1]['avg_time']:.2f}s avg)")
        print(f"🎯 Most Accurate: {most_accurate[0]} ({most_accurate[1]['avg_relevance']:.0%} relevance)")
        
        if 'qwen-0.6b-medical' in all_results:
            qwen = all_results['qwen-0.6b-medical']
            print(f"\n💡 Qwen-0.6B Performance:")
            print(f"   Speed: {qwen['avg_time']:.2f}s per task")
            print(f"   Accuracy: {qwen['avg_relevance']:.0%} keyword match")
            print(f"   Best for: Ultra-fast patient chat, triage, simple Q&A")
            print(f"   Trade-off: Lower accuracy than 7-8B models")
            print(f"   Memory: ~1GB VRAM (smallest model)")
    
    # Save results
    with open('qwen_benchmark_results.json', 'w') as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\n📁 Results saved to: qwen_benchmark_results.json")


if __name__ == "__main__":
    main()
