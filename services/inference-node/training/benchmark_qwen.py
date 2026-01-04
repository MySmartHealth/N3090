#!/usr/bin/env python3
"""
Benchmark Qwen-0.6B-medical model across various healthcare tasks
Compare with other models for speed, accuracy, and quality
"""
import asyncio
import time
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.model_router import ModelRouter


# Test prompts for different healthcare tasks
BENCHMARK_TASKS = {
    "medical_qa": {
        "prompt": "What are the common symptoms of Type 2 diabetes?",
        "expected_keywords": ["thirst", "urination", "hunger", "fatigue", "blurred vision"],
        "category": "Medical Knowledge"
    },
    "diagnosis_codes": {
        "prompt": "What is the ICD-10 code for Type 2 diabetes mellitus without complications?",
        "expected_keywords": ["E11.9", "diabetes"],
        "category": "Medical Coding"
    },
    "prescription": {
        "prompt": "Prescribe medication for a 45-year-old male with hypertension, blood pressure 150/95.",
        "expected_keywords": ["lisinopril", "amlodipine", "losartan", "10mg", "daily"],
        "category": "Clinical Decision"
    },
    "claims_analysis": {
        "prompt": "Analyze this claim: Diagnosis E11.9, I10. Procedure 99213. Is this clinically appropriate for routine diabetes management?",
        "expected_keywords": ["appropriate", "diabetes", "office visit", "routine"],
        "category": "Claims Processing"
    },
    "drug_interaction": {
        "prompt": "What are the interactions between metformin and lisinopril?",
        "expected_keywords": ["interaction", "safe", "monitor", "kidney"],
        "category": "Pharmacology"
    },
    "patient_triage": {
        "prompt": "Patient presents with severe chest pain radiating to left arm, sweating. What is the urgency level?",
        "expected_keywords": ["emergency", "urgent", "911", "cardiac", "myocardial"],
        "category": "Triage"
    },
    "lab_interpretation": {
        "prompt": "Interpret: HbA1c 8.5%, Fasting glucose 160 mg/dL. What does this indicate?",
        "expected_keywords": ["diabetes", "poor control", "uncontrolled", "elevated"],
        "category": "Lab Results"
    },
    "simple_chat": {
        "prompt": "What is diabetes?",
        "expected_keywords": ["blood sugar", "glucose", "insulin", "chronic"],
        "category": "Patient Education"
    }
}


async def benchmark_model(model_name: str, model_router: ModelRouter):
    """Benchmark a single model across all tasks"""
    
    print(f"\n{'='*80}")
    print(f"BENCHMARKING: {model_name}")
    print(f"{'='*80}\n")
    
    results = []
    
    for task_id, task_data in BENCHMARK_TASKS.items():
        print(f"Task: {task_data['category']} - {task_id}")
        print(f"Prompt: {task_data['prompt'][:60]}...")
        
        # Measure inference time
        start_time = time.time()
        
        try:
            response = await model_router.route_request(
                agent_type="MedicalQA",  # Use any agent, override model
                messages=[{"role": "user", "content": task_data['prompt']}],
                temperature=0.3,
                max_tokens=200,
                model_override=model_name
            )
            
            end_time = time.time()
            inference_time = end_time - start_time
            
            answer = response.get("content", "")
            
            # Calculate relevance score
            keywords_found = sum(1 for kw in task_data['expected_keywords'] 
                                if kw.lower() in answer.lower())
            relevance_score = keywords_found / len(task_data['expected_keywords'])
            
            result = {
                "task": task_id,
                "category": task_data['category'],
                "inference_time": round(inference_time, 2),
                "response_length": len(answer),
                "relevance_score": round(relevance_score, 2),
                "keywords_found": f"{keywords_found}/{len(task_data['expected_keywords'])}",
                "answer": answer[:150] + "..." if len(answer) > 150 else answer
            }
            
            print(f"  ⏱️  Time: {inference_time:.2f}s")
            print(f"  📊 Relevance: {relevance_score:.0%} ({keywords_found}/{len(task_data['expected_keywords'])} keywords)")
            print(f"  📝 Response: {answer[:100]}...")
            
        except Exception as e:
            result = {
                "task": task_id,
                "category": task_data['category'],
                "error": str(e),
                "inference_time": 0,
                "relevance_score": 0
            }
            print(f"  ❌ Error: {e}")
        
        results.append(result)
        print()
        await asyncio.sleep(0.5)  # Brief pause between requests
    
    return results


def print_summary(model_name: str, results: list):
    """Print summary statistics"""
    
    successful = [r for r in results if 'error' not in r]
    
    if not successful:
        print(f"\n❌ All tasks failed for {model_name}")
        return
    
    avg_time = sum(r['inference_time'] for r in successful) / len(successful)
    avg_relevance = sum(r['relevance_score'] for r in successful) / len(successful)
    avg_length = sum(r['response_length'] for r in successful) / len(successful)
    
    print(f"\n{'='*80}")
    print(f"SUMMARY: {model_name}")
    print(f"{'='*80}")
    print(f"  Tasks Completed: {len(successful)}/{len(results)}")
    print(f"  Avg Inference Time: {avg_time:.2f}s")
    print(f"  Avg Relevance Score: {avg_relevance:.0%}")
    print(f"  Avg Response Length: {avg_length:.0f} chars")
    print(f"\n  Performance by Category:")
    
    # Group by category
    categories = {}
    for r in successful:
        cat = r['category']
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(r)
    
    for cat, cat_results in categories.items():
        cat_avg_time = sum(r['inference_time'] for r in cat_results) / len(cat_results)
        cat_avg_relevance = sum(r['relevance_score'] for r in cat_results) / len(cat_results)
        print(f"    {cat:20} - Time: {cat_avg_time:.2f}s, Relevance: {cat_avg_relevance:.0%}")


async def compare_models():
    """Compare multiple models"""
    
    model_router = ModelRouter()
    
    # Models to benchmark
    models_to_test = [
        "qwen-0.6b-medical",      # The model in question
        "tiny-llama-1b",          # Comparison: similar size
        "bi-medix2",              # Comparison: medical specialist
        "bio-mistral-7b",         # Comparison: larger medical model
    ]
    
    all_results = {}
    
    for model_name in models_to_test:
        print(f"\n\n{'#'*80}")
        print(f"# Testing Model: {model_name}")
        print(f"{'#'*80}")
        
        try:
            results = await benchmark_model(model_name, model_router)
            all_results[model_name] = results
            print_summary(model_name, results)
        except Exception as e:
            print(f"\n❌ Failed to benchmark {model_name}: {e}")
            all_results[model_name] = {"error": str(e)}
    
    # Save results
    output_file = Path("benchmark_results.json")
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\n\n{'='*80}")
    print(f"COMPARISON TABLE")
    print(f"{'='*80}\n")
    
    # Create comparison table
    print(f"{'Model':<25} {'Avg Time':<12} {'Avg Relevance':<15} {'Success Rate'}")
    print(f"{'-'*70}")
    
    for model_name, results in all_results.items():
        if isinstance(results, dict) and 'error' in results:
            print(f"{model_name:<25} {'N/A':<12} {'N/A':<15} {'Failed'}")
        else:
            successful = [r for r in results if 'error' not in r]
            if successful:
                avg_time = sum(r['inference_time'] for r in successful) / len(successful)
                avg_relevance = sum(r['relevance_score'] for r in successful) / len(successful)
                success_rate = len(successful) / len(results)
                print(f"{model_name:<25} {avg_time:<11.2f}s {avg_relevance:<14.0%} {success_rate:.0%}")
    
    print(f"\n📁 Detailed results saved to: {output_file}")
    print("\n🏆 RECOMMENDATIONS:")
    
    # Find best model for each metric
    valid_models = {k: v for k, v in all_results.items() 
                   if not isinstance(v, dict) or 'error' not in v}
    
    if valid_models:
        # Fastest model
        fastest = min(valid_models.items(), 
                     key=lambda x: sum(r['inference_time'] for r in x[1] if 'error' not in r) / len([r for r in x[1] if 'error' not in r]))
        print(f"  ⚡ Fastest: {fastest[0]}")
        
        # Most relevant
        most_relevant = max(valid_models.items(),
                          key=lambda x: sum(r['relevance_score'] for r in x[1] if 'error' not in r) / len([r for r in x[1] if 'error' not in r]))
        print(f"  🎯 Most Relevant: {most_relevant[0]}")
        
        print(f"\n  💡 Qwen-0.6B Use Cases:")
        print(f"     - Best for: Speed-critical tasks (patient chat, triage)")
        print(f"     - Trade-off: Lower accuracy vs larger models")
        print(f"     - Memory: Minimal (~1GB VRAM)")


async def main():
    print("="*80)
    print("MEDICAL MODEL BENCHMARK SUITE")
    print("="*80)
    print("\nTesting Qwen-0.6B-medical against other models")
    print("Tasks: Medical QA, Coding, Diagnosis, Claims, Pharmacology\n")
    
    await compare_models()


if __name__ == "__main__":
    asyncio.run(main())
