"""
Document Processing Pipeline
Handles OCR, text extraction, and structured data extraction from medical documents.
Supports: Insurance claims, prescriptions, lab reports, discharge summaries
"""
import os
import io
import base64
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum
import asyncio

from loguru import logger

from .persona import AI_NAME, AI_QUALIFICATIONS

# OCR backends (install with: pip install pytesseract pdf2image Pillow)
try:
    import pytesseract
    from PIL import Image
    from pdf2image import convert_from_bytes
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    logger.warning("OCR dependencies not installed. Install: pip install pytesseract pdf2image Pillow")

# Alternative: Azure Form Recognizer for production-grade OCR
try:
    from azure.ai.formrecognizer import DocumentAnalysisClient
    from azure.core.credentials import AzureKeyCredential
    AZURE_OCR_AVAILABLE = bool(os.getenv("AZURE_FORM_RECOGNIZER_KEY"))
except ImportError:
    AZURE_OCR_AVAILABLE = False


class DocumentType(str, Enum):
    """Supported document types"""
    INSURANCE_CLAIM = "insurance_claim"
    PRESCRIPTION = "prescription"
    LAB_REPORT = "lab_report"
    DISCHARGE_SUMMARY = "discharge_summary"
    MEDICAL_RECORD = "medical_record"
    EOB = "explanation_of_benefits"  # EOB from insurance
    PRIOR_AUTH = "prior_authorization"
    UNKNOWN = "unknown"


@dataclass
class OCRResult:
    """Result from OCR processing"""
    text: str
    confidence: float
    language: str = "en"
    page_count: int = 1
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class StructuredDocument:
    """Structured data extracted from document"""
    document_type: DocumentType
    raw_text: str
    entities: Dict[str, Any]  # Extracted key-value pairs
    confidence: float
    metadata: Dict[str, Any]
    
    def __post_init__(self):
        if not self.metadata:
            self.metadata = {}


class DocumentProcessor:
    """
    OCR and document processing pipeline for medical/insurance documents.
    
    Features:
    - OCR for scanned documents (Tesseract/Azure)
    - Text extraction from PDFs
    - Structured data extraction (entities, key-value pairs)
    - Document classification
    """
    
    def __init__(self):
        self.ocr_backend = "tesseract" if OCR_AVAILABLE else None
        if AZURE_OCR_AVAILABLE:
            self.ocr_backend = "azure"
            self.azure_client = DocumentAnalysisClient(
                endpoint=os.getenv("AZURE_FORM_RECOGNIZER_ENDPOINT"),
                credential=AzureKeyCredential(os.getenv("AZURE_FORM_RECOGNIZER_KEY"))
            )
        
        logger.info(f"Document processor initialized with OCR backend: {self.ocr_backend}")
    
    async def process_document(
        self,
        file_data: bytes,
        file_type: str = "image/png",
        document_type: Optional[DocumentType] = None
    ) -> StructuredDocument:
        """
        Process a document (image or PDF) and extract structured data.
        
        Args:
            file_data: Raw file bytes
            file_type: MIME type (image/png, image/jpeg, application/pdf)
            document_type: Expected document type (optional, will auto-detect)
        
        Returns:
            StructuredDocument with extracted text and entities
        """
        # Step 1: OCR / Text Extraction
        ocr_result = await self._extract_text(file_data, file_type)
        
        # Step 2: Document Classification
        if not document_type:
            document_type = self._classify_document(ocr_result.text)
        
        # Step 3: Extract Structured Data
        entities = self._extract_entities(ocr_result.text, document_type)
        
        return StructuredDocument(
            document_type=document_type,
            raw_text=ocr_result.text,
            entities=entities,
            confidence=ocr_result.confidence,
            metadata={
                "file_type": file_type,
                "page_count": ocr_result.page_count,
                "ocr_backend": self.ocr_backend,
                **ocr_result.metadata
            }
        )
    
    async def _extract_text(self, file_data: bytes, file_type: str) -> OCRResult:
        """Extract text using appropriate OCR backend"""
        
        if self.ocr_backend == "azure":
            return await self._azure_ocr(file_data)
        elif self.ocr_backend == "tesseract":
            return await self._tesseract_ocr(file_data, file_type)
        else:
            raise RuntimeError("No OCR backend available. Install pytesseract or configure Azure.")
    
    async def _tesseract_ocr(self, file_data: bytes, file_type: str) -> OCRResult:
        """Tesseract OCR (open-source, local)"""
        if not OCR_AVAILABLE:
            raise RuntimeError("Tesseract not available")
        
        try:
            if file_type == "application/pdf":
                # Convert PDF pages to images
                images = convert_from_bytes(file_data)
                texts = []
                for img in images:
                    text = pytesseract.image_to_string(img)
                    texts.append(text)
                full_text = "\n\n--- PAGE BREAK ---\n\n".join(texts)
                page_count = len(images)
            else:
                # Direct image OCR
                image = Image.open(io.BytesIO(file_data))
                full_text = pytesseract.image_to_string(image)
                page_count = 1
            
            return OCRResult(
                text=full_text,
                confidence=0.85,  # Tesseract doesn't provide confidence
                page_count=page_count,
                metadata={"ocr_engine": "tesseract"}
            )
        
        except Exception as e:
            logger.error(f"Tesseract OCR failed: {e}")
            raise
    
    async def _azure_ocr(self, file_data: bytes) -> OCRResult:
        """Azure Form Recognizer OCR (production-grade)"""
        if not AZURE_OCR_AVAILABLE:
            raise RuntimeError("Azure Form Recognizer not configured")
        
        try:
            poller = self.azure_client.begin_analyze_document(
                "prebuilt-read", document=file_data
            )
            result = poller.result()
            
            # Extract text from all pages
            full_text = "\n\n".join([page.content for page in result.pages])
            
            return OCRResult(
                text=full_text,
                confidence=result.pages[0].lines[0].confidence if result.pages else 0.9,
                page_count=len(result.pages),
                metadata={
                    "ocr_engine": "azure",
                    "model_id": result.model_id
                }
            )
        
        except Exception as e:
            logger.error(f"Azure OCR failed: {e}")
            raise
    
    def _classify_document(self, text: str) -> DocumentType:
        """
        Auto-detect document type based on content keywords.
        
        Uses simple keyword matching. For production, use a classifier model.
        """
        text_lower = text.lower()
        
        # Insurance claims keywords
        if any(kw in text_lower for kw in [
            "claim number", "policy number", "diagnosis code", "procedure code",
            "icd-10", "cpt code", "claim form", "cms-1500", "ub-04"
        ]):
            return DocumentType.INSURANCE_CLAIM
        
        # Prescription keywords
        if any(kw in text_lower for kw in [
            "rx ", "prescription", "sig:", "dispense", "refill", "dosage",
            "take ", "medication", "pharmacy"
        ]):
            return DocumentType.PRESCRIPTION
        
        # Lab report keywords
        if any(kw in text_lower for kw in [
            "laboratory", "test result", "reference range", "specimen",
            "wbc", "rbc", "hemoglobin", "glucose", "pathology"
        ]):
            return DocumentType.LAB_REPORT
        
        # Discharge summary keywords
        if any(kw in text_lower for kw in [
            "discharge summary", "admission date", "discharge date",
            "hospital course", "discharge diagnosis", "discharge instructions"
        ]):
            return DocumentType.DISCHARGE_SUMMARY
        
        # EOB keywords
        if any(kw in text_lower for kw in [
            "explanation of benefits", "amount billed", "amount allowed",
            "you may owe", "provider paid", "eob"
        ]):
            return DocumentType.EOB
        
        return DocumentType.UNKNOWN
    
    def _extract_entities(self, text: str, doc_type: DocumentType) -> Dict[str, Any]:
        """
        Extract structured entities based on document type.
        
        For production: Use NER models (spaCy medical NER, BioBERT, etc.)
        """
        entities = {}
        
        if doc_type == DocumentType.INSURANCE_CLAIM:
            entities = self._extract_claim_entities(text)
        elif doc_type == DocumentType.PRESCRIPTION:
            entities = self._extract_prescription_entities(text)
        elif doc_type == DocumentType.LAB_REPORT:
            entities = self._extract_lab_entities(text)
        elif doc_type == DocumentType.DISCHARGE_SUMMARY:
            entities = self._extract_discharge_entities(text)
        
        return entities
    
    def _extract_claim_entities(self, text: str) -> Dict[str, Any]:
        """Extract entities from insurance claim"""
        import re
        
        entities = {
            "claim_number": None,
            "policy_number": None,
            "patient_name": None,
            "provider_name": None,
            "diagnosis_codes": [],
            "procedure_codes": [],
            "claim_amount": None,
            "service_date": None,
        }
        
        # Claim number (various formats)
        claim_match = re.search(r"claim\s*(?:number|#)?\s*:?\s*([A-Z0-9-]+)", text, re.IGNORECASE)
        if claim_match:
            entities["claim_number"] = claim_match.group(1)
        
        # Policy number
        policy_match = re.search(r"policy\s*(?:number|#)?\s*:?\s*([A-Z0-9-]+)", text, re.IGNORECASE)
        if policy_match:
            entities["policy_number"] = policy_match.group(1)
        
        # ICD-10 codes
        icd_codes = re.findall(r"\b([A-Z]\d{2}(?:\.\d{1,4})?)\b", text)
        entities["diagnosis_codes"] = list(set(icd_codes))
        
        # CPT codes
        cpt_codes = re.findall(r"\b(\d{5})\b", text)
        entities["procedure_codes"] = list(set(cpt_codes))
        
        # Claim amount
        amount_match = re.search(r"\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)", text)
        if amount_match:
            entities["claim_amount"] = amount_match.group(1).replace(",", "")
        
        return entities
    
    def _extract_prescription_entities(self, text: str) -> Dict[str, Any]:
        """Extract entities from prescription"""
        import re
        
        entities = {
            "medication": None,
            "dosage": None,
            "frequency": None,
            "quantity": None,
            "refills": None,
            "prescriber": None,
        }
        
        # Extract medication name (after "Rx:" or at beginning)
        rx_match = re.search(r"(?:Rx|Prescription):\s*([A-Za-z\s]+)", text, re.IGNORECASE)
        if rx_match:
            entities["medication"] = rx_match.group(1).strip()
        
        # Dosage
        dosage_match = re.search(r"(\d+\s*(?:mg|mcg|ml|units?))", text, re.IGNORECASE)
        if dosage_match:
            entities["dosage"] = dosage_match.group(1)
        
        # Frequency (e.g., "twice daily", "BID", "QD")
        freq_match = re.search(r"(?:take|sig:)\s*([^.]+)", text, re.IGNORECASE)
        if freq_match:
            entities["frequency"] = freq_match.group(1).strip()
        
        return entities
    
    def _extract_lab_entities(self, text: str) -> Dict[str, Any]:
        """Extract entities from lab report"""
        import re
        
        entities = {
            "test_name": None,
            "results": [],
            "abnormal_flags": [],
        }
        
        # Find test results with reference ranges
        result_pattern = r"([A-Za-z\s]+)\s*(\d+\.?\d*)\s*(?:reference|normal)?\s*:?\s*(\d+\.?\d*\s*-\s*\d+\.?\d*)"
        matches = re.findall(result_pattern, text, re.IGNORECASE)
        
        for match in matches:
            test_name, value, ref_range = match
            entities["results"].append({
                "test": test_name.strip(),
                "value": value,
                "reference_range": ref_range
            })
        
        return entities
    
    def _extract_discharge_entities(self, text: str) -> Dict[str, Any]:
        """Extract entities from discharge summary"""
        import re
        
        entities = {
            "admission_date": None,
            "discharge_date": None,
            "primary_diagnosis": None,
            "procedures": [],
            "medications": [],
        }
        
        # Admission date
        adm_match = re.search(r"admission\s*date:\s*(\d{1,2}/\d{1,2}/\d{2,4})", text, re.IGNORECASE)
        if adm_match:
            entities["admission_date"] = adm_match.group(1)
        
        # Discharge date
        dis_match = re.search(r"discharge\s*date:\s*(\d{1,2}/\d{1,2}/\d{2,4})", text, re.IGNORECASE)
        if dis_match:
            entities["discharge_date"] = dis_match.group(1)
        
        return entities


class ClaimsAdjudicator:
    """
    AI-powered claims adjudication engine.
    
    Determines claim admissibility based on:
    - Policy coverage rules
    - Medical necessity
    - Coding accuracy
    - Prior authorization requirements
    """
    
    def __init__(self, model_router=None):
        self.model_router = model_router
        self.doc_processor = DocumentProcessor()
    
    async def adjudicate_claim(
        self,
        claim_document: bytes,
        policy_id: str,
        file_type: str = "application/pdf"
    ) -> Dict[str, Any]:
        """
        Adjudicate insurance claim for admissibility.
        
        Uses two-model approach:
        1. BiMediX2-8B - Analyzes medical entities (diagnoses, procedures, necessity)
        2. OpenInsurance-Llama3-8B - Evaluates claims policy and coverage
        
        Returns:
            {
                "decision": "approved" | "denied" | "pending",
                "confidence": 0.95,
                "reasons": ["Medical necessity confirmed", "In-network provider"],
                "extracted_data": {...},
                "recommendations": ["Request additional documentation"]
            }
        """
        # Step 1: OCR and extract claim data
        structured_doc = await self.doc_processor.process_document(
            claim_document, file_type, DocumentType.INSURANCE_CLAIM
        )
        
        # Step 2: Build medical analysis prompt for BiMediX
        medical_prompt = self._build_medical_analysis_prompt(structured_doc)
        
        # Step 3: Get medical analysis from BiMediX
        medical_analysis = ""
        if self.model_router:
            try:
                logger.info("ClaimsOCR: Using BiMediX for medical entity analysis")
                med_response = await self.model_router.route_request(
                    agent_type="MedicalQA",  # Uses BiMediX2-8B
                    messages=[{"role": "user", "content": medical_prompt}],
                    temperature=0.1,
                )
                medical_analysis = med_response.get("content", "")
            except Exception as e:
                logger.error(f"Medical analysis failed: {e}")
                medical_analysis = "Medical analysis unavailable"
        
        # Step 4: Build claims adjudication prompt with medical context
        claims_prompt = self._build_adjudication_prompt(
            structured_doc, policy_id, medical_analysis
        )
        
        # Step 5: Get final adjudication from OpenInsurance model
        if self.model_router:
            try:
                logger.info("ClaimsOCR: Using OpenInsurance for claims adjudication")
                response = await self.model_router.route_request(
                    agent_type="Claims",  # Uses OpenInsurance-Llama3-8B
                    messages=[{"role": "user", "content": claims_prompt}],
                    temperature=0.1,  # Low temp for consistent decisions
                )
                ai_decision = response.get("content", "")
            except Exception as e:
                logger.error(f"Claims adjudication failed: {e}")
                ai_decision = "Unable to process claim automatically. Manual review required."
        else:
            ai_decision = "AI adjudication not available (no model router)"
        
        # Step 6: Parse AI response and return structured decision
        return {
            "decision": "pending",  # Would parse from AI response
            "confidence": structured_doc.confidence,
            "extracted_data": structured_doc.entities,
            "raw_text": structured_doc.raw_text,
            "medical_analysis": medical_analysis,
            "claims_decision": ai_decision,
            "document_type": structured_doc.document_type.value,
            "recommendations": [
                "Review extracted claim data for accuracy",
                "Verify policy coverage for diagnosis codes",
                "Check provider network status"
            ]
        }
    
    def _build_medical_analysis_prompt(self, structured_doc: StructuredDocument) -> str:
        """Build prompt for BiMediX medical entity analysis"""
        
        entities = structured_doc.entities
        
        prompt = f"""You are {AI_NAME} ({AI_QUALIFICATIONS}), analyzing a healthcare insurance claim for clinical accuracy and medical necessity.

**EXTRACTED MEDICAL DATA:**
- Diagnosis Codes (ICD-10): {', '.join(entities.get('diagnosis_codes', []))}
- Procedure Codes (CPT): {', '.join(entities.get('procedure_codes', []))}
- Service Date: {entities.get('service_date', 'Not extracted')}

**CLAIM TEXT (Medical Context):**
{structured_doc.raw_text[:1500]}

**ANALYZE THE FOLLOWING:**
1. **ICD-10 Code Validity**: Are the diagnosis codes clinically appropriate?
2. **CPT Code Accuracy**: Do procedure codes match the diagnoses?
3. **Medical Necessity**: Is the treatment medically necessary for these diagnoses?
4. **Coding Specificity**: Are codes specific enough or too general?
5. **Clinical Coherence**: Do diagnoses and procedures make clinical sense together?

**PROVIDE:**
- Clinical assessment of medical necessity
- Any concerns about coding accuracy
- Potential medical flags or inconsistencies
- Recommendations for clinical review

Be concise and focus on medical/clinical aspects only.
"""
        return prompt
    
    def _build_adjudication_prompt(
        self, 
        structured_doc: StructuredDocument, 
        policy_id: str,
        medical_analysis: str
    ) -> str:
        """Build prompt for OpenInsurance claims adjudication"""
        
        entities = structured_doc.entities
        
        prompt = f"""You are {AI_NAME} ({AI_QUALIFICATIONS}), an expert in Indian health insurance claims adjudication with knowledge of IRDAI regulations. Review this claim and determine admissibility.

**CLAIM INFORMATION:**
- Claim Number: {entities.get('claim_number', 'Not extracted')}
- Policy Number: {entities.get('policy_number', 'Not extracted')}
- Policy ID: {policy_id}
- Diagnosis Codes: {', '.join(entities.get('diagnosis_codes', []))}
- Procedure Codes: {', '.join(entities.get('procedure_codes', []))}
- Claim Amount: ₹{entities.get('claim_amount', 'Not extracted')}
- Service Date: {entities.get('service_date', 'Not extracted')}

**MEDICAL ANALYSIS (from clinical review):**
{medical_analysis}

**ADJUDICATION CRITERIA:**
1. **Coverage Verification**: Are the diagnosis/procedure codes covered under policy {policy_id}?
2. **Medical Necessity**: Is the treatment medically necessary based on the diagnosis?
3. **Coding Accuracy**: Are ICD-10 and CPT codes appropriate and properly documented?
4. **Prior Authorization**: Does this claim require prior authorization?
5. **Network Status**: Is this an in-network or out-of-network claim?

**PROVIDE:**
- Decision: APPROVED / DENIED / PENDING
- Confidence: 0-100%
- Detailed reasoning for decision
- Missing information (if any)
- Recommendations for provider or patient
"""
        return prompt


# Export main classes
__all__ = [
    "DocumentProcessor",
    "ClaimsAdjudicator",
    "DocumentType",
    "OCRResult",
    "StructuredDocument"
]
