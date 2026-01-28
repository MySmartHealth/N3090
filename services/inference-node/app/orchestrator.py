"""
LLM Orchestrator for Dual-Agent and Multi-Agent Workflows
Implements parallel multi-tasking to improve efficiency of agent operations.

SPEED TIER OPTIMIZATION (from benchmark results):
- Tier 1 (Real-Time, <2s):   Chat, Appointment, Monitoring, Billing, Claims, MedicalQA
  * Use for: Interactive tasks, urgent responses, real-time video/voice
  * Performance: 1.2-1.4s average latency
  
- Tier 2 (High-Quality, 33s): Clinical, Documentation
  * Use for: Clinical decisions, complex medical analysis, comprehensive documentation
  * Performance: 33s avg, but 72-100 tok/s generation with 2,000+ token responses
  * Quality: ⭐⭐⭐⭐⭐ Medical accuracy

Strategy: Use Tier 1 for parallel tasks, reserve Tier 2 for quality-critical clinical work
"""
import asyncio
from typing import List, Dict, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger
import time

from .model_router import ModelRouter
from .persona import get_system_prompt


class WorkflowType(str, Enum):
    """Predefined workflow types for common healthcare tasks."""
    DISCHARGE_SUMMARY = "discharge_summary"
    PHARMACY_DOC = "pharmacy_documentation"
    INSURANCE_CLAIM = "insurance_claim"
    LAB_REPORT = "lab_report"
    RADIOLOGY_REPORT = "radiology_report"
    COMPREHENSIVE_ASSESSMENT = "comprehensive_assessment"
    BILLING_WITH_JUSTIFICATION = "billing_with_justification"
    PARALLEL_QA = "parallel_qa"


@dataclass
class AgentTask:
    """Single agent task definition."""
    agent_type: str
    prompt: str
    priority: int = 0  # Higher = more urgent
    max_tokens: int = 512
    temperature: float = 0.7
    dependencies: List[str] = field(default_factory=list)  # Task IDs this depends on
    task_id: Optional[str] = None
    
    def __post_init__(self):
        if self.task_id is None:
            self.task_id = f"{self.agent_type}_{id(self)}"


@dataclass
class AgentResult:
    """Result from a single agent execution."""
    task_id: str
    agent_type: str
    success: bool
    content: str
    model: str
    latency_ms: float
    tokens: int
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkflowResult:
    """Aggregated result from multi-agent workflow."""
    workflow_type: str
    success: bool
    results: List[AgentResult]
    aggregated_content: str
    total_latency_ms: float
    parallel_efficiency: float  # 0-1, how much parallelization helped
    metadata: Dict[str, Any] = field(default_factory=dict)


class LLMOrchestrator:
    """
    Orchestrates multiple LLM agents for complex workflows.
    Supports parallel execution, dependency management, and result aggregation.
    """
    
    def __init__(self, model_router: ModelRouter):
        self.router = model_router
        self.workflow_templates = self._initialize_workflows()
    
    def _initialize_workflows(self) -> Dict[WorkflowType, Callable]:
        """Initialize predefined workflow templates."""
        return {
            WorkflowType.DISCHARGE_SUMMARY: self._discharge_summary_workflow,
            WorkflowType.PHARMACY_DOC: self._pharmacy_documentation_workflow,
            WorkflowType.INSURANCE_CLAIM: self._insurance_claim_workflow,
            WorkflowType.LAB_REPORT: self._lab_report_workflow,
            WorkflowType.RADIOLOGY_REPORT: self._radiology_report_workflow,
            WorkflowType.COMPREHENSIVE_ASSESSMENT: self._comprehensive_assessment_workflow,
            WorkflowType.BILLING_WITH_JUSTIFICATION: self._billing_justification_workflow,
            WorkflowType.PARALLEL_QA: self._parallel_qa_workflow,
        }
    
    async def execute_workflow(
        self,
        workflow_type: WorkflowType,
        context: Dict[str, Any],
        custom_tasks: Optional[List[AgentTask]] = None
    ) -> WorkflowResult:
        """
        Execute a predefined workflow or custom task list.
        
        Args:
            workflow_type: Type of workflow to execute
            context: Context data for the workflow (patient info, medical data, etc.)
            custom_tasks: Optional custom task list (overrides template)
        
        Returns:
            WorkflowResult with aggregated outputs
        """
        start_time = time.time()
        
        # Get tasks from template or use custom
        if custom_tasks:
            tasks = custom_tasks
        else:
            workflow_fn = self.workflow_templates.get(workflow_type)
            if not workflow_fn:
                raise ValueError(f"Unknown workflow type: {workflow_type}")
            tasks = workflow_fn(context)
        
        logger.info(f"Executing workflow: {workflow_type.value} with {len(tasks)} tasks")
        
        # Execute tasks with dependency resolution
        results = await self._execute_tasks_with_dependencies(tasks, context)
        
        # Aggregate results
        aggregated = self._aggregate_results(workflow_type, results, context)
        
        total_latency = (time.time() - start_time) * 1000
        
        # Calculate parallel efficiency
        sequential_time = sum(r.latency_ms for r in results)
        parallel_efficiency = min(1.0, sequential_time / total_latency if total_latency > 0 else 1.0)
        
        return WorkflowResult(
            workflow_type=workflow_type.value,
            success=all(r.success for r in results),
            results=results,
            aggregated_content=aggregated,
            total_latency_ms=total_latency,
            parallel_efficiency=parallel_efficiency,
            metadata={
                "num_tasks": len(tasks),
                "sequential_time_ms": sequential_time,
                "speedup_factor": sequential_time / total_latency if total_latency > 0 else 1.0,
            }
        )
    
    async def _execute_tasks_with_dependencies(
        self,
        tasks: List[AgentTask],
        context: Dict[str, Any]
    ) -> List[AgentResult]:
        """Execute tasks respecting dependencies, parallelizing where possible."""
        
        # Build dependency graph
        task_map = {task.task_id: task for task in tasks}
        completed = {}
        results = []
        
        while len(completed) < len(tasks):
            # Find tasks ready to execute (no pending dependencies)
            ready_tasks = [
                task for task in tasks
                if task.task_id not in completed
                and all(dep in completed for dep in task.dependencies)
            ]
            
            if not ready_tasks:
                # Circular dependency or error
                remaining = [t for t in tasks if t.task_id not in completed]
                logger.error(f"Cannot resolve dependencies for tasks: {[t.task_id for t in remaining]}")
                break
            
            # Execute ready tasks in parallel
            logger.info(f"Executing {len(ready_tasks)} tasks in parallel")
            batch_results = await asyncio.gather(
                *[self._execute_single_task(task, context, completed) for task in ready_tasks],
                return_exceptions=True
            )
            
            # Process results
            for task, result in zip(ready_tasks, batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Task {task.task_id} failed: {result}")
                    result = AgentResult(
                        task_id=task.task_id,
                        agent_type=task.agent_type,
                        success=False,
                        content="",
                        model="",
                        latency_ms=0,
                        tokens=0,
                        error=str(result)
                    )
                
                completed[task.task_id] = result
                results.append(result)
        
        return results
    
    async def _execute_single_task(
        self,
        task: AgentTask,
        context: Dict[str, Any],
        completed_tasks: Dict[str, AgentResult]
    ) -> AgentResult:
        """Execute a single agent task."""
        start_time = time.time()
        
        try:
            # Build prompt with dependency results if needed
            prompt = task.prompt
            if task.dependencies:
                dependency_results = "\n\n".join([
                    f"[{dep} Result]:\n{completed_tasks[dep].content}"
                    for dep in task.dependencies if dep in completed_tasks
                ])
                prompt = f"{dependency_results}\n\n{prompt}"
            
            # Create messages with Dr. iSHA persona
            messages = [
                {"role": "system", "content": get_system_prompt(task.agent_type)},
                {"role": "user", "content": prompt}
            ]
            
            # Execute via router
            response = await self.router.generate(
                agent_type=task.agent_type,
                messages=messages,
                max_tokens=task.max_tokens,
                temperature=task.temperature,
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            return AgentResult(
                task_id=task.task_id,
                agent_type=task.agent_type,
                success=True,
                content=response["text"],
                model=response["model"],
                latency_ms=latency_ms,
                tokens=response["tokens_generated"],
                metadata={
                    "backend": response["backend"],
                    "gpu_ids": response["gpu_ids"],
                }
            )
        
        except Exception as e:
            logger.error(f"Task {task.task_id} execution failed: {e}")
            latency_ms = (time.time() - start_time) * 1000
            return AgentResult(
                task_id=task.task_id,
                agent_type=task.agent_type,
                success=False,
                content="",
                model="",
                latency_ms=latency_ms,
                tokens=0,
                error=str(e)
            )
    
    def _aggregate_results(
        self,
        workflow_type: WorkflowType,
        results: List[AgentResult],
        context: Dict[str, Any]
    ) -> str:
        """Aggregate results from multiple agents into final output."""
        
        if workflow_type == WorkflowType.DISCHARGE_SUMMARY:
            return self._aggregate_discharge_summary(results, context)
        elif workflow_type == WorkflowType.PHARMACY_DOC:
            return self._aggregate_pharmacy_doc(results, context)
        elif workflow_type == WorkflowType.INSURANCE_CLAIM:
            return self._aggregate_insurance_claim(results, context)
        else:
            # Default aggregation: concatenate with headers
            sections = []
            for result in results:
                if result.success:
                    sections.append(f"=== {result.agent_type.upper()} ===\n{result.content}")
            return "\n\n".join(sections)
    
    # ==================== WORKFLOW TEMPLATES ====================
    
    def _discharge_summary_workflow(self, context: Dict[str, Any]) -> List[AgentTask]:
        """Discharge summary: Clinical summary + Billing codes (parallel then merge)."""
        patient_data = context.get("patient_data", "")
        admission_date = context.get("admission_date", "")
        discharge_date = context.get("discharge_date", "")
        
        clinical_task = AgentTask(
            task_id="clinical_summary",
            agent_type="Clinical",
            prompt=f"""Generate a comprehensive clinical discharge summary for the following patient:

Patient Data: {patient_data}
Admission Date: {admission_date}
Discharge Date: {discharge_date}

Include:
1. Admission diagnosis
2. Hospital course and treatments
3. Discharge diagnosis
4. Medications at discharge
5. Follow-up instructions
6. Prognosis

Format as a formal clinical discharge summary.""",
            max_tokens=1024,
            temperature=0.3,
            priority=1
        )
        
        billing_task = AgentTask(
            task_id="billing_codes",
            agent_type="Billing",
            prompt=f"""Extract and generate billing codes (ICD-10, CPT) for the following patient case:

Patient Data: {patient_data}
Admission Date: {admission_date}
Discharge Date: {discharge_date}

Provide:
1. Primary ICD-10 diagnosis codes
2. Secondary diagnosis codes
3. Procedure codes (CPT)
4. DRG code if applicable
5. Billing justification notes

Format as structured billing documentation.""",
            max_tokens=512,
            temperature=0.2,
            priority=1
        )
        
        return [clinical_task, billing_task]
    
    def _pharmacy_documentation_workflow(self, context: Dict[str, Any]) -> List[AgentTask]:
        """Pharmacy documentation: Clinical (drug interactions) + Billing (pharmacy codes)."""
        medication_list = context.get("medications", "")
        patient_info = context.get("patient_info", "")
        
        clinical_task = AgentTask(
            task_id="drug_analysis",
            agent_type="Clinical",
            prompt=f"""Analyze the following medication list for a patient:

Patient: {patient_info}
Medications: {medication_list}

Provide:
1. Drug interaction analysis
2. Contraindications based on patient history
3. Dosage verification
4. Clinical warnings and precautions
5. Monitoring recommendations""",
            max_tokens=768,
            temperature=0.3
        )
        
        billing_task = AgentTask(
            task_id="pharmacy_billing",
            agent_type="Billing",
            prompt=f"""Generate pharmacy billing documentation for:

Patient: {patient_info}
Medications: {medication_list}

Include:
1. NDC codes for each medication
2. Quantity and days supply
3. Insurance coverage codes
4. Prior authorization requirements
5. Billing notes""",
            max_tokens=512,
            temperature=0.2,
            dependencies=["drug_analysis"]  # Run after clinical analysis
        )
        
        return [clinical_task, billing_task]
    
    def _insurance_claim_workflow(self, context: Dict[str, Any]) -> List[AgentTask]:
        """Insurance claim: Medical necessity (MedicalQA) + Claim processing (Claims)."""
        procedure = context.get("procedure", "")
        diagnosis = context.get("diagnosis", "")
        patient_data = context.get("patient_data", "")
        
        medical_justification = AgentTask(
            task_id="medical_necessity",
            agent_type="MedicalQA",
            prompt=f"""Provide medical necessity justification for insurance authorization:

Procedure: {procedure}
Diagnosis: {diagnosis}
Patient Data: {patient_data}

Explain:
1. Medical indication for the procedure
2. Evidence-based rationale
3. Expected outcomes
4. Alternative treatments considered
5. Why this procedure is necessary""",
            max_tokens=768,
            temperature=0.3,
            priority=2
        )
        
        claim_processing = AgentTask(
            task_id="claim_form",
            agent_type="Claims",
            prompt=f"""Generate insurance claim authorization request:

Procedure: {procedure}
Diagnosis: {diagnosis}
Patient Data: {patient_data}

Include:
1. Claim form header (patient demographics)
2. Procedure codes and descriptions
3. Diagnosis codes
4. Medical necessity statement
5. Supporting documentation checklist
6. Prior authorization reference numbers""",
            max_tokens=512,
            temperature=0.2,
            dependencies=["medical_necessity"]
        )
        
        return [medical_justification, claim_processing]
    
    def _lab_report_workflow(self, context: Dict[str, Any]) -> List[AgentTask]:
        """Lab report: Clinical interpretation + Billing codes."""
        lab_results = context.get("lab_results", "")
        patient_info = context.get("patient_info", "")
        
        interpretation = AgentTask(
            task_id="lab_interpretation",
            agent_type="Clinical",
            prompt=f"""Interpret the following laboratory results:

Patient: {patient_info}
Lab Results: {lab_results}

Provide:
1. Analysis of abnormal values
2. Clinical significance
3. Differential diagnosis implications
4. Recommended follow-up tests
5. Clinical recommendations""",
            max_tokens=768,
            temperature=0.3
        )
        
        return [interpretation]
    
    def _radiology_report_workflow(self, context: Dict[str, Any]) -> List[AgentTask]:
        """Radiology report: Clinical interpretation."""
        imaging_findings = context.get("findings", "")
        study_type = context.get("study_type", "")
        
        task = AgentTask(
            task_id="radiology_interpretation",
            agent_type="Clinical",
            prompt=f"""Generate a radiology report for:

Study Type: {study_type}
Findings: {imaging_findings}

Format:
1. TECHNIQUE
2. COMPARISON
3. FINDINGS
4. IMPRESSION
5. RECOMMENDATIONS""",
            max_tokens=1024,
            temperature=0.3
        )
        
        return [task]
    
    def _comprehensive_assessment_workflow(self, context: Dict[str, Any]) -> List[AgentTask]:
        """Comprehensive patient assessment: All agents in parallel."""
        patient_case = context.get("patient_case", "")
        
        tasks = [
            AgentTask(
                task_id="medical_assessment",
                agent_type="MedicalQA",
                prompt=f"Provide comprehensive medical assessment for: {patient_case}",
                max_tokens=768,
                priority=3
            ),
            AgentTask(
                task_id="clinical_decision",
                agent_type="Clinical",
                prompt=f"Provide clinical decision support and treatment recommendations for: {patient_case}",
                max_tokens=768,
                priority=3
            ),
            AgentTask(
                task_id="billing_overview",
                agent_type="Billing",
                prompt=f"Provide billing and coding overview for: {patient_case}",
                max_tokens=512,
                priority=2
            ),
        ]
        
        return tasks
    
    def _billing_justification_workflow(self, context: Dict[str, Any]) -> List[AgentTask]:
        """Billing with medical justification."""
        service = context.get("service", "")
        
        tasks = [
            AgentTask(
                task_id="medical_justification",
                agent_type="MedicalQA",
                prompt=f"Provide medical justification for: {service}",
                max_tokens=512,
                priority=2
            ),
            AgentTask(
                task_id="billing_codes",
                agent_type="Billing",
                prompt=f"Generate billing codes and documentation for: {service}",
                max_tokens=512,
                priority=1,
                dependencies=["medical_justification"]
            ),
        ]
        
        return tasks
    
    def _parallel_qa_workflow(self, context: Dict[str, Any]) -> List[AgentTask]:
        """Parallel Q&A: Send same question to multiple agents for comparison."""
        question = context.get("question", "")
        
        tasks = [
            AgentTask(
                task_id="bimedix_answer",
                agent_type="MedicalQA",
                prompt=question,
                max_tokens=512
            ),
            AgentTask(
                task_id="biomistral_answer",
                agent_type="Clinical",
                prompt=question,
                max_tokens=512
            ),
        ]
        
        return tasks
    
    # ==================== AGGREGATION METHODS ====================
    
    def _aggregate_discharge_summary(self, results: List[AgentResult], context: Dict[str, Any]) -> str:
        """Aggregate clinical summary with billing codes."""
        clinical = next((r for r in results if r.task_id == "clinical_summary"), None)
        billing = next((r for r in results if r.task_id == "billing_codes"), None)
        
        parts = ["=== DISCHARGE SUMMARY ===\n"]
        
        if clinical and clinical.success:
            parts.append(clinical.content)
        
        parts.append("\n\n=== BILLING INFORMATION ===\n")
        
        if billing and billing.success:
            parts.append(billing.content)
        
        parts.append(f"\n\n[Generated by: {clinical.model if clinical else 'N/A'} + {billing.model if billing else 'N/A'}]")
        
        return "\n".join(parts)
    
    def _aggregate_pharmacy_doc(self, results: List[AgentResult], context: Dict[str, Any]) -> str:
        """Aggregate pharmacy documentation."""
        drug_analysis = next((r for r in results if r.task_id == "drug_analysis"), None)
        billing = next((r for r in results if r.task_id == "pharmacy_billing"), None)
        
        parts = ["=== PHARMACY DOCUMENTATION ===\n"]
        
        if drug_analysis and drug_analysis.success:
            parts.append("--- Clinical Analysis ---\n")
            parts.append(drug_analysis.content)
        
        if billing and billing.success:
            parts.append("\n\n--- Billing Information ---\n")
            parts.append(billing.content)
        
        return "\n".join(parts)
    
    def _aggregate_insurance_claim(self, results: List[AgentResult], context: Dict[str, Any]) -> str:
        """Aggregate insurance claim documentation."""
        medical = next((r for r in results if r.task_id == "medical_necessity"), None)
        claim = next((r for r in results if r.task_id == "claim_form"), None)
        
        parts = ["=== INSURANCE AUTHORIZATION REQUEST ===\n"]
        
        if medical and medical.success:
            parts.append("--- Medical Necessity Justification ---\n")
            parts.append(medical.content)
        
        if claim and claim.success:
            parts.append("\n\n--- Claim Documentation ---\n")
            parts.append(claim.content)
        
        return "\n".join(parts)


# Singleton instance
_orchestrator_instance: Optional[LLMOrchestrator] = None


def get_orchestrator(router: Optional[ModelRouter] = None) -> LLMOrchestrator:
    """Get or create orchestrator singleton."""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        if router is None:
            from .model_router import ModelRouter
            router = ModelRouter()
        _orchestrator_instance = LLMOrchestrator(router)
    return _orchestrator_instance
