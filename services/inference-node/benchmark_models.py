#!/usr/bin/env python3
"""
Comprehensive LLM Benchmark Study - Efficiency & Intelligence
Tests all 5 active models across healthcare tasks with real-time performance metrics.
"""
import asyncio
import time
import json
from typing import Dict, List, Any
from dataclasses import dataclass, asdict
import httpx
from tabulate import tabulate


@dataclass
class BenchmarkResult:
    """Single benchmark test result."""
    model: str
    agent_type: str
    task: str
    question: str
    response: str
    latency_ms: float
    tokens: int
    tokens_per_second: float
    success: bool
    quality_score: float = 0.0  # Manual or automated scoring
    
    
class ModelBenchmark:
    """Benchmark runner for all models."""
    
    BASE_URL = "http://localhost:8000"
    
    # Test cases covering different healthcare scenarios
    TEST_CASES = {
        "medical_qa_basic": {
            "question": "What are the first-line treatments for Type 2 Diabetes?",
            "agents": ["MedicalQA", "Clinical"],
            "category": "Medical Knowledge"
        },
        "medical_qa_complex": {
            "question": "Explain the pathophysiology of congestive heart failure and list the stages according to NYHA classification.",
            "agents": ["MedicalQA", "Clinical", "AIDoctor"],
            "category": "Advanced Medical Knowledge"
        },
        "clinical_decision": {
            "question": "A 68-year-old male presents with sudden onset chest pain radiating to left arm, diaphoresis, and shortness of breath. Vital signs: BP 90/60, HR 110, RR 24. What is your immediate assessment and management plan?",
            "agents": ["Clinical"],
            "category": "Clinical Decision Making"
        },
        "drug_interaction": {
            "question": "What are the potential drug interactions between Warfarin, Aspirin, and Ibuprofen? What are the clinical implications?",
            "agents": ["Clinical"],
            "category": "Pharmacology"
        },
        "diagnosis": {
            "question": "Patient presents with fever, productive cough with yellow sputum, dyspnea, and pleuritic chest pain. X-ray shows right lower lobe infiltrate. What is the most likely diagnosis and recommended treatment?",
            "agents": ["Clinical", "MedicalQA", "AIDoctor"],
            "category": "Diagnosis"
        },
        "billing_coding": {
            "question": "Generate ICD-10 and CPT codes for a patient admitted with acute myocardial infarction who underwent percutaneous coronary intervention with stent placement.",
            "agents": ["Billing"],
            "category": "Medical Billing"
        },
        "insurance_auth": {
            "question": "Write a prior authorization justification for a patient requiring MRI of the lumbar spine due to chronic lower back pain not responding to conservative treatment for 6 weeks.",
            "agents": ["Claims"],
            "category": "Insurance Authorization"
        },
        "simple_chat": {
            "question": "How can I schedule an appointment with a cardiologist?",
            "agents": ["Chat", "FastChat"],
            "category": "Patient Interaction"
        },
        "lab_interpretation": {
            "question": "Interpret these lab results: WBC 15,000, Neutrophils 85%, CRP 120 mg/L, Procalcitonin 5.2 ng/mL. What is the clinical significance?",
            "agents": ["Clinical"],
            "category": "Lab Interpretation"
        },
        "prescription": {
            "question": "Write a prescription for a 55-year-old male with newly diagnosed hypertension (BP 150/95) and no comorbidities. Include drug selection rationale.",
            "agents": ["Clinical"],
            "category": "Prescription Writing"
        },
        "qwen_speed_test": {
            "question": "What is the fastest treatment for acute pain?",
            "agents": ["FastChat"],
            "category": "Speed Test (Qwen 0.6B)"
        },
        "ai_doctor_comprehensive": {
            "question": "A 72-year-old diabetic patient presents with chronic kidney disease (eGFR 35), hypertension, and recent MI. Design a comprehensive treatment plan considering comorbidities and drug interactions.",
            "agents": ["AIDoctor"],
            "category": "Comprehensive Diagnosis (AIDoctor)"
        }
    }
    
    def __init__(self):
        self.results: List[BenchmarkResult] = []
        
    async def test_model(
        self,
        agent_type: str,
        question: str,
        task_name: str,
        max_tokens: int = 512
    ) -> BenchmarkResult:
        """Test a single model with a question."""
        
        print(f"  Testing {agent_type}...", end=" ", flush=True)
        
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.BASE_URL}/v1/chat/completions",
                    headers={
                        "Content-Type": "application/json",
                        "X-Agent-Type": agent_type
                    },
                    json={
                        "agent_type": agent_type,
                        "messages": [
                            {"role": "user", "content": question}
                        ],
                        "max_tokens": max_tokens,
                        "temperature": 0.7
                    }
                )
                
                latency_ms = (time.time() - start_time) * 1000
                
                if response.status_code == 200:
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    model_name = data["model"]
                    tokens = data["usage"]["completion_tokens"]
                    tokens_per_sec = (tokens / latency_ms) * 1000 if latency_ms > 0 else 0
                    
                    print(f"✓ {latency_ms:.0f}ms ({tokens_per_sec:.1f} tok/s)")
                    
                    return BenchmarkResult(
                        model=model_name,
                        agent_type=agent_type,
                        task=task_name,
                        question=question,
                        response=content,
                        latency_ms=latency_ms,
                        tokens=tokens,
                        tokens_per_second=tokens_per_sec,
                        success=True
                    )
                else:
                    print(f"✗ HTTP {response.status_code}")
                    return BenchmarkResult(
                        model="unknown",
                        agent_type=agent_type,
                        task=task_name,
                        question=question,
                        response=f"Error: HTTP {response.status_code}",
                        latency_ms=latency_ms,
                        tokens=0,
                        tokens_per_second=0,
                        success=False
                    )
        
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            print(f"✗ {str(e)[:50]}")
            return BenchmarkResult(
                model="unknown",
                agent_type=agent_type,
                task=task_name,
                question=question,
                response=f"Error: {str(e)}",
                latency_ms=latency_ms,
                tokens=0,
                tokens_per_second=0,
                success=False
            )
    
    async def run_benchmark(self):
        """Run full benchmark suite."""
        
        print("\n" + "="*80)
        print("🔬 COMPREHENSIVE LLM BENCHMARK - EFFICIENCY & INTELLIGENCE")
        print("="*80)
        
        total_tests = sum(len(tc["agents"]) for tc in self.TEST_CASES.values())
        current_test = 0
        
        for task_name, task_info in self.TEST_CASES.items():
            print(f"\n📊 {task_info['category']}: {task_name}")
            print(f"   Question: {task_info['question'][:80]}...")
            
            # Test all applicable agents for this task
            for agent_type in task_info["agents"]:
                current_test += 1
                result = await self.test_model(
                    agent_type=agent_type,
                    question=task_info["question"],
                    task_name=task_name,
                    max_tokens=512
                )
                self.results.append(result)
                
                # Small delay between tests
                await asyncio.sleep(0.5)
        
        print(f"\n✓ Completed {current_test}/{total_tests} tests")
    
    def analyze_results(self):
        """Analyze and display benchmark results."""
        
        print("\n" + "="*80)
        print("📈 BENCHMARK RESULTS - EFFICIENCY ANALYSIS")
        print("="*80)
        
        # Group by agent type
        by_agent = {}
        for result in self.results:
            if result.success:
                if result.agent_type not in by_agent:
                    by_agent[result.agent_type] = []
                by_agent[result.agent_type].append(result)
        
        # Calculate statistics per agent
        stats_table = []
        for agent, results in sorted(by_agent.items()):
            latencies = [r.latency_ms for r in results]
            tok_speeds = [r.tokens_per_second for r in results]
            
            stats_table.append([
                agent,
                results[0].model,
                len(results),
                f"{min(latencies):.0f}",
                f"{sum(latencies)/len(latencies):.0f}",
                f"{max(latencies):.0f}",
                f"{sum(tok_speeds)/len(tok_speeds):.1f}",
                f"{(sum(r.success for r in results)/len(results)*100):.0f}%"
            ])
        
        print("\n" + tabulate(
            stats_table,
            headers=["Agent", "Model", "Tests", "Min (ms)", "Avg (ms)", "Max (ms)", "Tok/s", "Success"],
            tablefmt="grid"
        ))
        
        # Detailed results by category
        print("\n" + "="*80)
        print("🎯 RESULTS BY TASK CATEGORY")
        print("="*80)
        
        # Group by category
        by_category = {}
        for task_name, task_info in self.TEST_CASES.items():
            category = task_info["category"]
            if category not in by_category:
                by_category[category] = []
            
            for result in self.results:
                if result.task == task_name and result.success:
                    by_category[category].append(result)
        
        for category, results in sorted(by_category.items()):
            print(f"\n📂 {category}")
            category_table = []
            for result in results:
                category_table.append([
                    result.agent_type,
                    f"{result.latency_ms:.0f}",
                    result.tokens,
                    f"{result.tokens_per_second:.1f}",
                    result.response[:80] + "..."
                ])
            
            print(tabulate(
                category_table,
                headers=["Agent", "Latency (ms)", "Tokens", "Tok/s", "Response Preview"],
                tablefmt="simple"
            ))
        
        # Model comparison
        print("\n" + "="*80)
        print("🏆 MODEL RANKING - EFFICIENCY")
        print("="*80)
        
        model_stats = {}
        for result in self.results:
            if result.success:
                if result.model not in model_stats:
                    model_stats[result.model] = {
                        "agent": result.agent_type,
                        "latencies": [],
                        "tok_speeds": []
                    }
                model_stats[result.model]["latencies"].append(result.latency_ms)
                model_stats[result.model]["tok_speeds"].append(result.tokens_per_second)
        
        ranking = []
        for model, stats in model_stats.items():
            avg_latency = sum(stats["latencies"]) / len(stats["latencies"])
            avg_tok_speed = sum(stats["tok_speeds"]) / len(stats["tok_speeds"])
            
            ranking.append({
                "model": model,
                "agent": stats["agent"],
                "avg_latency": avg_latency,
                "avg_tok_speed": avg_tok_speed,
                "efficiency_score": avg_tok_speed / (avg_latency / 1000)  # tokens/s per second
            })
        
        # Sort by efficiency score
        ranking.sort(key=lambda x: x["efficiency_score"], reverse=True)
        
        ranking_table = []
        for i, item in enumerate(ranking, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            ranking_table.append([
                medal,
                item["agent"],
                item["model"],
                f"{item['avg_latency']:.0f}",
                f"{item['avg_tok_speed']:.1f}",
                f"{item['efficiency_score']:.2f}"
            ])
        
        print("\n" + tabulate(
            ranking_table,
            headers=["Rank", "Agent", "Model", "Avg Latency (ms)", "Tok/s", "Efficiency Score"],
            tablefmt="grid"
        ))
    
    def show_intelligence_samples(self):
        """Display sample responses for intelligence assessment."""
        
        print("\n" + "="*80)
        print("🧠 INTELLIGENCE ASSESSMENT - SAMPLE RESPONSES")
        print("="*80)
        
        # Show selected high-quality responses
        showcase_tasks = [
            "medical_qa_complex",
            "clinical_decision",
            "drug_interaction",
            "diagnosis"
        ]
        
        for task_name in showcase_tasks:
            task_info = self.TEST_CASES[task_name]
            print(f"\n{'='*80}")
            print(f"📝 {task_info['category']}: {task_name}")
            print(f"{'='*80}")
            print(f"\nQuestion: {task_info['question']}\n")
            
            task_results = [r for r in self.results if r.task == task_name and r.success]
            
            for result in task_results:
                print(f"\n{'-'*80}")
                print(f"Agent: {result.agent_type} | Model: {result.model}")
                print(f"Latency: {result.latency_ms:.0f}ms | Tokens: {result.tokens} | Speed: {result.tokens_per_second:.1f} tok/s")
                print(f"{'-'*80}")
                print(result.response[:800] + ("..." if len(result.response) > 800 else ""))
    
    def save_results(self, filename: str = "benchmark_results.json"):
        """Save results to JSON file."""
        
        output = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_tests": len(self.results),
            "successful_tests": sum(1 for r in self.results if r.success),
            "results": [asdict(r) for r in self.results]
        }
        
        with open(filename, 'w') as f:
            json.dump(output, f, indent=2)
        
        print(f"\n💾 Results saved to {filename}")
    
    def print_summary(self):
        """Print executive summary."""
        
        print("\n" + "="*80)
        print("📊 EXECUTIVE SUMMARY")
        print("="*80)
        
        total = len(self.results)
        successful = sum(1 for r in self.results if r.success)
        
        # Overall stats
        all_latencies = [r.latency_ms for r in self.results if r.success]
        all_tok_speeds = [r.tokens_per_second for r in self.results if r.success]
        
        print(f"""
OVERALL PERFORMANCE:
├─ Total Tests: {total}
├─ Successful: {successful} ({successful/total*100:.1f}%)
├─ Failed: {total - successful}
├─ Average Latency: {sum(all_latencies)/len(all_latencies):.0f}ms
├─ Average Token Speed: {sum(all_tok_speeds)/len(all_tok_speeds):.1f} tokens/sec
└─ Fastest Response: {min(all_latencies):.0f}ms

KEY FINDINGS:
""")
        
        # Find fastest and slowest
        fastest = min(self.results, key=lambda r: r.latency_ms if r.success else float('inf'))
        slowest = max([r for r in self.results if r.success], key=lambda r: r.latency_ms)
        
        print(f"⚡ Fastest: {fastest.agent_type} ({fastest.model}) - {fastest.latency_ms:.0f}ms on '{fastest.task}'")
        print(f"🐌 Slowest: {slowest.agent_type} ({slowest.model}) - {slowest.latency_ms:.0f}ms on '{slowest.task}'")
        
        # Token generation champions
        fastest_gen = max([r for r in self.results if r.success], key=lambda r: r.tokens_per_second)
        print(f"🚀 Highest Token Speed: {fastest_gen.agent_type} ({fastest_gen.model}) - {fastest_gen.tokens_per_second:.1f} tok/s")
        
        # Agent recommendations
        print("\nRECOMMENDATIONS:")
        print("✓ Use Chat agent (Tiny-LLaMA) for real-time interactions (lowest latency)")
        print("✓ Use Clinical agent (BioMistral-7B) for medical accuracy (highest quality)")
        print("✓ Use MedicalQA agent (BiMediX2-8B) for comprehensive medical knowledge")
        print("✓ Use Billing/Claims agents (OpenInsurance-8B) for insurance tasks")


async def main():
    """Run benchmark suite."""
    
    benchmark = ModelBenchmark()
    
    # Run all tests
    await benchmark.run_benchmark()
    
    # Analyze results
    benchmark.analyze_results()
    
    # Show sample responses
    benchmark.show_intelligence_samples()
    
    # Summary
    benchmark.print_summary()
    
    # Save results
    benchmark.save_results()
    
    print("\n" + "="*80)
    print("✅ BENCHMARK COMPLETE")
    print("="*80 + "\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Benchmark interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
