#!/usr/bin/env python3
"""
Load Testing Script for Medical AI Inference System

Usage:
    python3 load_test.py --concurrent 100 --duration 300 --target http://localhost:8000

Tests:
    - Concurrent task submissions
    - Queue handling under load
    - Task status polling
    - Result retrieval
    - Performance metrics collection
"""

import asyncio
import httpx
import time
import statistics
import json
import argparse
from typing import List, Dict, Tuple
from dataclasses import dataclass
from datetime import datetime
import sys

@dataclass
class TestResult:
    """Container for test metrics"""
    task_count: int
    successful: int
    failed: int
    total_duration_s: float
    submission_latency_ms: List[float]
    status_check_latency_ms: List[float]
    retrieval_latency_ms: List[float]
    queue_depths: List[int]
    
    @property
    def success_rate(self) -> float:
        return (self.successful / self.task_count * 100) if self.task_count > 0 else 0
    
    @property
    def throughput_qps(self) -> float:
        return self.task_count / self.total_duration_s if self.total_duration_s > 0 else 0
    
    def print_summary(self):
        """Print test results summary"""
        print(f"\n{'='*70}")
        print(f"LOAD TEST RESULTS - {datetime.now().isoformat()}")
        print(f"{'='*70}\n")
        
        print(f"Test Duration: {self.total_duration_s:.2f} seconds")
        print(f"Tasks Submitted: {self.task_count}")
        print(f"✓ Successful: {self.successful}")
        print(f"✗ Failed: {self.failed}")
        print(f"Success Rate: {self.success_rate:.1f}%\n")
        
        print("THROUGHPUT")
        print(f"  Throughput: {self.throughput_qps:.1f} tasks/sec")
        print(f"  Per minute: {self.throughput_qps * 60:.0f} tasks/min\n")
        
        print("SUBMISSION LATENCY (ms)")
        self._print_latency_stats("  ", self.submission_latency_ms)
        
        print("\nSTATUS CHECK LATENCY (ms)")
        self._print_latency_stats("  ", self.status_check_latency_ms)
        
        print("\nRESULT RETRIEVAL LATENCY (ms)")
        self._print_latency_stats("  ", self.retrieval_latency_ms)
        
        if self.queue_depths:
            print(f"\nQUEUE DEPTH STATS")
            print(f"  Peak: {max(self.queue_depths)}")
            print(f"  Average: {statistics.mean(self.queue_depths):.1f}")
            print(f"  Min: {min(self.queue_depths)}")
        
        print(f"\n{'='*70}\n")
    
    def _print_latency_stats(self, indent: str, latencies: List[float]):
        """Print latency statistics"""
        if not latencies:
            print(f"{indent}No data")
            return
        
        avg = statistics.mean(latencies)
        p50 = sorted(latencies)[int(len(latencies) * 0.5)]
        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        p99 = sorted(latencies)[int(len(latencies) * 0.99)]
        
        print(f"{indent}Avg: {avg:.1f} ms")
        print(f"{indent}p50: {p50:.1f} ms")
        print(f"{indent}p95: {p95:.1f} ms")
        print(f"{indent}p99: {p99:.1f} ms")
        print(f"{indent}Min: {min(latencies):.1f} ms | Max: {max(latencies):.1f} ms")

class LoadTester:
    """Load testing orchestrator"""
    
    def __init__(self, target_url: str, concurrent_tasks: int = 100):
        self.target_url = target_url.rstrip('/')
        self.concurrent_tasks = concurrent_tasks
        self.results = TestResult(
            task_count=0,
            successful=0,
            failed=0,
            total_duration_s=0,
            submission_latency_ms=[],
            status_check_latency_ms=[],
            retrieval_latency_ms=[],
            queue_depths=[]
        )
    
    async def submit_task(self, client: httpx.AsyncClient, task_num: int) -> Tuple[str, bool, float]:
        """Submit a single task and measure latency"""
        payload = {
            "agent_type": "Chat",
            "messages": [
                {
                    "role": "user",
                    "content": f"Medical question #{task_num}: What is the treatment for hypertension?"
                }
            ],
            "priority": "HIGH" if task_num % 10 == 0 else "NORMAL",
            "timeout_seconds": 60,
            "max_tokens": 500
        }
        
        start = time.time()
        try:
            response = await client.post(
                f"{self.target_url}/v1/async/submit",
                json=payload,
                timeout=10
            )
            latency = (time.time() - start) * 1000
            
            if response.status_code == 200:
                task_id = response.json().get("task_id")
                return task_id, True, latency
            else:
                return None, False, latency
        except Exception as e:
            latency = (time.time() - start) * 1000
            print(f"  Error submitting task {task_num}: {str(e)[:60]}")
            return None, False, latency
    
    async def check_status(self, client: httpx.AsyncClient, task_id: str) -> Tuple[str, float]:
        """Check task status"""
        start = time.time()
        try:
            response = await client.get(
                f"{self.target_url}/v1/async/status/{task_id}",
                timeout=10
            )
            latency = (time.time() - start) * 1000
            
            if response.status_code == 200:
                status = response.json().get("status", "unknown")
                return status, latency
            return "error", latency
        except Exception:
            return "error", (time.time() - start) * 1000
    
    async def get_queue_depth(self, client: httpx.AsyncClient) -> int:
        """Get current queue depth"""
        try:
            response = await client.get(
                f"{self.target_url}/v1/async/stats",
                timeout=10
            )
            if response.status_code == 200:
                return response.json().get("queue", {}).get("total_tasks", 0)
        except Exception:
            pass
        return 0
    
    async def retrieve_result(self, client: httpx.AsyncClient, task_id: str) -> Tuple[bool, float]:
        """Retrieve task result"""
        start = time.time()
        try:
            response = await client.get(
                f"{self.target_url}/v1/async/result/{task_id}",
                timeout=10
            )
            latency = (time.time() - start) * 1000
            return response.status_code == 200, latency
        except Exception:
            return False, (time.time() - start) * 1000
    
    async def run_load_test(self):
        """Execute load test"""
        print(f"\nStarting load test...")
        print(f"  Target: {self.target_url}")
        print(f"  Concurrent tasks: {self.concurrent_tasks}")
        print(f"  Starting at: {datetime.now().isoformat()}\n")
        
        start_time = time.time()
        
        async with httpx.AsyncClient(timeout=30) as client:
            # Phase 1: Submit all tasks concurrently
            print("Phase 1: Submitting tasks...")
            task_ids = []
            
            submit_tasks = [
                self.submit_task(client, i) 
                for i in range(self.concurrent_tasks)
            ]
            
            results = await asyncio.gather(*submit_tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, Exception):
                    self.results.failed += 1
                else:
                    task_id, success, latency = result
                    self.results.submission_latency_ms.append(latency)
                    if success:
                        task_ids.append(task_id)
                        self.results.successful += 1
                    else:
                        self.results.failed += 1
            
            self.results.task_count = self.concurrent_tasks
            
            print(f"  ✓ Submitted: {self.results.successful} tasks")
            print(f"  ✗ Failed: {self.results.failed} tasks\n")
            
            # Phase 2: Poll status while processing
            print("Phase 2: Monitoring queue and checking status...")
            max_wait_seconds = 120
            poll_interval = 2
            elapsed = 0
            
            while elapsed < max_wait_seconds and task_ids:
                # Sample status checks
                sample_ids = task_ids[::max(1, len(task_ids)//5)][:5]
                
                status_checks = [
                    self.check_status(client, task_id)
                    for task_id in sample_ids
                ]
                
                status_results = await asyncio.gather(*status_checks, return_exceptions=True)
                
                for result in status_results:
                    if not isinstance(result, Exception):
                        status, latency = result
                        self.results.status_check_latency_ms.append(latency)
                
                # Check queue depth
                queue_depth = await self.get_queue_depth(client)
                self.results.queue_depths.append(queue_depth)
                
                print(f"  Queue depth: {queue_depth} | Elapsed: {elapsed}s")
                
                if queue_depth == 0:
                    break
                
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
            
            # Phase 3: Try to retrieve results
            print(f"\nPhase 3: Retrieving results...")
            
            retrieval_tasks = [
                self.retrieve_result(client, task_id)
                for task_id in task_ids[:min(10, len(task_ids))]  # Sample 10
            ]
            
            retrieval_results = await asyncio.gather(*retrieval_tasks, return_exceptions=True)
            
            for result in retrieval_results:
                if not isinstance(result, Exception):
                    success, latency = result
                    if success:
                        self.results.retrieval_latency_ms.append(latency)
        
        self.results.total_duration_s = time.time() - start_time
        self.results.print_summary()

async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Load test Medical AI inference system"
    )
    parser.add_argument(
        "--target",
        default="http://localhost:8000",
        help="Target API URL (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--concurrent",
        type=int,
        default=100,
        help="Number of concurrent tasks (default: 100)"
    )
    
    args = parser.parse_args()
    
    tester = LoadTester(args.target, args.concurrent)
    await tester.run_load_test()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        sys.exit(1)
