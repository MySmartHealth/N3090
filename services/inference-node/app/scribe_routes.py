"""
AI Scribe and Document Processing Routes
Handles clinical documentation and insurance claim processing
Includes multilingual translation support via IndicTrans2
"""
from typing import Optional, List
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from pydantic import BaseModel, Field
from loguru import logger

from .document_processor import (
    DocumentProcessor,
    ClaimsAdjudicator,
    DocumentType,
)
from .model_router import ModelRouter
from .auth import get_current_user, User
from .translation_integration import get_translation_service, TranslationContext

router = APIRouter(prefix="/v1/scribe", tags=["AI Scribe & Document Processing"])

# Initialize processors
doc_processor = DocumentProcessor()
claims_adjudicator = None  # Will be initialized with model_router


class ScribeRequest(BaseModel):
    """Request for AI scribe to generate clinical documentation"""
    dictation: str = Field(..., description="Doctor's voice-to-text dictation")
    document_type: str = Field(
        "prescription",
        description="Type of document: prescription, discharge_summary, soap_note, procedure_note"
    )
    patient_context: Optional[str] = Field(None, description="Patient demographics and history")
    template: Optional[str] = Field(None, description="Custom template for output")
    # Translation parameters
    source_language: Optional[str] = Field(
        "en",
        description="Language of dictation (e.g., 'en', 'hi', 'ta')"
    )
    translate_to_languages: Optional[List[str]] = Field(
        None,
        description="Languages to translate generated document to (e.g., ['hi', 'ta', 'te'])"
    )


class ScribeResponse(BaseModel):
    """AI-generated clinical document"""
    document: str
    document_type: str
    confidence: float
    extracted_entities: dict
    suggestions: list[str] = []
    # Translation results
    translations: Optional[dict] = None  # Dict of language -> translated document


class ClaimAdjudicationResponse(BaseModel):
    """Claim adjudication result using dual-model approach"""
    decision: str  # approved, denied, pending
    confidence: float
    extracted_data: dict
    raw_text: str
    medical_analysis: str  # BiMediX2-8B medical assessment
    claims_decision: str   # OpenInsurance-Llama3-8B adjudication
    document_type: str
    recommendations: list[str]


def get_model_router():
    """Dependency to get model router instance"""
    from .main import model_router
    return model_router


@router.post("/dictation", response_model=ScribeResponse)
async def ai_scribe_dictation(
    request: ScribeRequest,
    current_user: User = Depends(get_current_user),
    model_router: ModelRouter = Depends(get_model_router)
):
    """
    AI Scribe: Convert doctor's dictation to structured clinical document.
    
    **Use Cases:**
    - Prescription generation from dictation
    - SOAP note creation
    - Discharge summary writing
    - Procedure note documentation
    
    **Example:**
    ```
    POST /v1/scribe/dictation
    {
        "dictation": "Patient is a 45 year old male presenting with hypertension. BP 150/95. Start lisinopril 10mg daily. Follow up in 2 weeks.",
        "document_type": "prescription",
        "patient_context": "John Doe, 45M, PMH: HTN, Allergies: None"
    }
    ```
    """
    try:
        # Build prompt for Scribe agent
        prompt = _build_scribe_prompt(
            request.dictation,
            request.document_type,
            request.patient_context,
            request.template
        )
        
        # Route to Scribe agent (uses BioMistral for high-quality output)
        response = await model_router.route_request(
            agent_type="Scribe",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,  # Moderate creativity for clinical writing
        )
        
        ai_output = response.get("content", "")
        
        # Extract entities (medications, diagnoses, etc.)
        entities = _extract_clinical_entities(ai_output, request.document_type)
        
        # Handle translations if requested
        translations = None
        if request.translate_to_languages:
            try:
                translation_service = get_translation_service()
                translation_results = await translation_service.translate_scribe_output(
                    ai_output,
                    source_language=request.source_language or "en",
                    target_languages=request.translate_to_languages
                )
                
                # Extract translated documents
                translations = {}
                for lang, trans_data in translation_results.get("translations", {}).items():
                    translations[lang] = trans_data.get("text", "")
                
                logger.info(f"Scribe output translated to {len(translations)} languages")
            except Exception as e:
                logger.warning(f"Scribe translation failed: {e}")
        
        return ScribeResponse(
            document=ai_output,
            document_type=request.document_type,
            confidence=0.90,  # Would calculate from model logprobs
            extracted_entities=entities,
            suggestions=[
                "Review for clinical accuracy",
                "Verify medication dosages",
                "Sign and date the document"
            ],
            translations=translations
        )
    
    except Exception as e:
        logger.error(f"AI scribe failed: {e}")
        raise HTTPException(status_code=500, detail=f"Scribe processing failed: {str(e)}")


@router.post("/ocr/claim", response_model=ClaimAdjudicationResponse)
async def process_claim_document(
    file: UploadFile = File(..., description="Scanned insurance claim (PDF or image)"),
    policy_id: str = Form(..., description="Patient's insurance policy ID"),
    current_user: User = Depends(get_current_user),
    model_router: ModelRouter = Depends(get_model_router)
):
    """
    OCR + Dual-AI Adjudication: Extract and analyze claims using two specialized models.
    
    **Two-Model Approach:**
    1. **BiMediX2-8B** - Analyzes medical entities (ICD-10, CPT codes, medical necessity)
    2. **OpenInsurance-Llama3-8B** - Evaluates policy coverage and claim admissibility
    
    **Process:**
    1. OCR to extract text from scanned document
    2. Extract structured data (claim number, codes, amounts)
    3. BiMediX analyzes medical accuracy and necessity
    4. OpenInsurance makes final adjudication decision
    5. Return combined analysis with confidence and reasoning
    
    **Supported Formats:** PDF, PNG, JPEG, TIFF
    
    **Example:**
    ```bash
    curl -X POST http://localhost:8000/v1/scribe/ocr/claim \\
      -F "file=@claim_document.pdf" \\
      -F "policy_id=POL-12345" \\
      -H "Authorization: Bearer YOUR_TOKEN"
    ```
    """
    try:
        # Read file bytes
        file_bytes = await file.read()
        file_type = file.content_type or "application/pdf"
        
        # Initialize claims adjudicator with model router
        global claims_adjudicator
        if not claims_adjudicator:
            claims_adjudicator = ClaimsAdjudicator(model_router)
        
        # Process claim
        result = await claims_adjudicator.adjudicate_claim(
            file_bytes,
            policy_id,
            file_type
        )
        
        return ClaimAdjudicationResponse(**result)
    
    except Exception as e:
        logger.error(f"Claim OCR processing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Claim processing failed: {str(e)}")


@router.post("/ocr/extract")
async def extract_document_text(
    file: UploadFile = File(..., description="Medical document (PDF or image)"),
    document_type: Optional[str] = Form(None, description="Expected document type"),
    current_user: User = Depends(get_current_user)
):
    """
    OCR: Extract text and structured data from any medical document.
    
    **Supported Documents:**
    - Insurance claims
    - Prescriptions
    - Lab reports
    - Discharge summaries
    - Medical records
    
    **Returns:** Raw text + extracted entities
    """
    try:
        file_bytes = await file.read()
        file_type = file.content_type or "image/png"
        
        # Parse document type
        doc_type = None
        if document_type:
            try:
                doc_type = DocumentType(document_type)
            except ValueError:
                pass
        
        # Process document
        result = await doc_processor.process_document(file_bytes, file_type, doc_type)
        
        return {
            "document_type": result.document_type.value,
            "raw_text": result.raw_text,
            "extracted_entities": result.entities,
            "confidence": result.confidence,
            "metadata": result.metadata
        }
    
    except Exception as e:
        logger.error(f"Document OCR failed: {e}")
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {str(e)}")


@router.post("/translate/claim")
async def translate_claim_document(
    claim_text: str = Form(..., description="Extracted or raw claim document text"),
    source_language: str = Form(..., description="Language of claim document (e.g., 'hi', 'ta', 'en')"),
    target_language: str = Form("en", description="Target language for translation"),
    current_user: User = Depends(get_current_user)
):
    """
    Translate insurance claim documents while preserving medical entities and structure.
    
    **Features:**
    - Maintains claim structure and formatting
    - Extracts medical terms and codes (ICD-10, CPT)
    - Preserves numerical data (amounts, dates)
    - Returns both translated text and structured entities
    
    **Supported Languages:** Hindi, Tamil, Telugu, Kannada, Malayalam, English, and 18+ Indian languages
    
    **Example:**
    ```bash
    curl -X POST http://localhost:8000/v1/scribe/translate/claim \\
      -F "claim_text=<claim_text>" \\
      -F "source_language=hi" \\
      -F "target_language=en" \\
      -H "Authorization: Bearer YOUR_TOKEN"
    ```
    """
    try:
        translation_service = get_translation_service()
        
        result = await translation_service.translate_claims_document(
            claim_text,
            source_language=source_language,
            target_language=target_language
        )
        
        return {
            "original_document": result["original_document"],
            "translated_document": result["translated_document"],
            "source_language": source_language,
            "target_language": target_language,
            "confidence": result["confidence"],
            "model_used": result["model"],
            "extracted_sections": result["sections"],
            "medical_terms": result["medical_terms"]
        }
    
    except Exception as e:
        logger.error(f"Claim translation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Translation failed: {str(e)}")


@router.post("/translate/voice")
async def translate_voice_transcript(
    transcript: str = Form(..., description="Voice-to-text transcript"),
    spoken_language: str = Form(..., description="Language spoken"),
    target_languages: Optional[str] = Form(
        "en",
        description="Comma-separated list of target languages"
    ),
    current_user: User = Depends(get_current_user)
):
    """
    Translate voice chat/call transcripts to multiple languages.
    
    **Use Cases:**
    - Multilingual telemedicine calls
    - Doctor-patient communication in preferred languages
    - Voice note translation
    - Call transcripts for records
    
    **Example:**
    ```bash
    curl -X POST http://localhost:8000/v1/scribe/translate/voice \\
      -F "transcript=<voice_transcript>" \\
      -F "spoken_language=hi" \\
      -F "target_languages=en,ta,te" \\
      -H "Authorization: Bearer YOUR_TOKEN"
    ```
    """
    try:
        translation_service = get_translation_service()
        
        # Parse target languages
        targets = [lang.strip() for lang in target_languages.split(",")] if target_languages else ["en"]
        
        result = await translation_service.translate_voice_transcript(
            transcript,
            spoken_language=spoken_language,
            target_languages=targets
        )
        
        return result
    
    except Exception as e:
        logger.error(f"Voice transcript translation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Translation failed: {str(e)}")


@router.post("/translate/video-captions")
async def translate_video_captions(
    captions_json: str = Form(
        ...,
        description="JSON array of captions: [{\"text\": \"...\", \"start_time\": 0.0, \"end_time\": 1.0}, ...]"
    ),
    source_language: str = Form(..., description="Language of video captions"),
    target_language: str = Form(..., description="Target language"),
    current_user: User = Depends(get_current_user)
):
    """
    Translate video captions/subtitles preserving timing information.
    
    **Features:**
    - Preserves start/end times for subtitle sync
    - Maintains formatting and punctuation
    - Supports medical terminology in telemedicine videos
    
    **Input Format:**
    ```json
    [
      {"text": "Patient presents with chest pain", "start_time": 0.5, "end_time": 2.0},
      {"text": "Vital signs are stable", "start_time": 2.1, "end_time": 4.0}
    ]
    ```
    
    **Example:**
    ```bash
    curl -X POST http://localhost:8000/v1/scribe/translate/video-captions \\
      -F "captions_json='[{...}]'" \\
      -F "source_language=en" \\
      -F "target_language=hi" \\
      -H "Authorization: Bearer YOUR_TOKEN"
    ```
    """
    try:
        import json
        
        # Parse captions JSON
        captions = json.loads(captions_json)
        if not isinstance(captions, list):
            raise ValueError("Captions must be a JSON array")
        
        translation_service = get_translation_service()
        
        result = await translation_service.translate_video_chat_captions(
            captions,
            source_language=source_language,
            target_language=target_language
        )
        
        return {
            "translated_captions": result,
            "source_language": source_language,
            "target_language": target_language,
            "caption_count": len(result)
        }
    
    except Exception as e:
        logger.error(f"Video caption translation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Translation failed: {str(e)}")


# Helper functions

def _build_scribe_prompt(
    dictation: str,
    doc_type: str,
    patient_context: Optional[str],
    template: Optional[str]
) -> str:
    """Build prompt for AI scribe"""
    
    context_str = f"\n**Patient Context:** {patient_context}" if patient_context else ""
    template_str = f"\n**Template:** {template}" if template else ""
    
    if doc_type == "prescription":
        prompt = f"""You are an AI medical scribe. Generate a properly formatted prescription based on the doctor's dictation.
{context_str}

**Doctor's Dictation:**
{dictation}

**Generate a prescription with:**
1. Patient name and DOB (if available)
2. Medication name
3. Dosage and form
4. Frequency and route
5. Quantity and refills
6. Special instructions
7. Prescriber signature line

**Output as a formal prescription document.**
"""
    
    elif doc_type == "discharge_summary":
        prompt = f"""You are an AI medical scribe. Generate a comprehensive discharge summary based on the doctor's dictation.
{context_str}

**Doctor's Dictation:**
{dictation}

**Include standard sections:**
1. Patient Demographics
2. Admission Date & Discharge Date
3. Admitting Diagnosis
4. Discharge Diagnosis
5. Hospital Course (brief narrative)
6. Procedures Performed
7. Discharge Medications
8. Discharge Instructions
9. Follow-up Appointments

**Use proper medical terminology and formatting.**
"""
    
    elif doc_type == "soap_note":
        prompt = f"""You are an AI medical scribe. Generate a SOAP note from the doctor's dictation.
{context_str}

**Doctor's Dictation:**
{dictation}

**Format as SOAP:**
- **S (Subjective):** Patient's complaints, history
- **O (Objective):** Vital signs, exam findings
- **A (Assessment):** Diagnosis, clinical impression
- **P (Plan):** Treatment plan, medications, follow-up

**Be concise and clinically accurate.**
"""
    
    else:  # Generic
        prompt = f"""You are an AI medical scribe. Generate a {doc_type} document from the doctor's dictation.
{context_str}
{template_str}

**Doctor's Dictation:**
{dictation}

**Generate a professional medical document with proper formatting and medical terminology.**
"""
    
    return prompt


def _extract_clinical_entities(text: str, doc_type: str) -> dict:
    """Extract clinical entities from generated document"""
    import re
    
    entities = {
        "medications": [],
        "diagnoses": [],
        "procedures": [],
        "dosages": [],
        "icd_codes": [],
    }
    
    # Extract medications (basic regex, use NER for production)
    med_pattern = r"\b([A-Z][a-z]+(?:pril|cillin|mycin|statin|olol|pam|done|ine))\b"
    entities["medications"] = list(set(re.findall(med_pattern, text)))
    
    # Extract dosages
    dosage_pattern = r"\b(\d+\s*(?:mg|mcg|ml|units?))\b"
    entities["dosages"] = list(set(re.findall(dosage_pattern, text, re.IGNORECASE)))
    
    # Extract ICD-10 codes
    icd_pattern = r"\b([A-Z]\d{2}(?:\.\d{1,4})?)\b"
    entities["icd_codes"] = list(set(re.findall(icd_pattern, text)))
    
    return entities
