"""
Translation Routes - IndicTrans2 API Endpoints
Multilingual support for Indian languages + English
"""
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from loguru import logger

from .indictrans2_engine import get_indictrans_engine, IndianLanguage, TranslationResult
from .auth import get_current_user, get_optional_user, User

router = APIRouter(prefix="/v1/translate", tags=["Multilingual Translation"])


class TranslateRequest(BaseModel):
    """Translation request"""
    text: str = Field(..., description="Text to translate")
    source_language: str = Field(..., description="Source language code (e.g., 'hi', 'en', 'ta')")
    target_language: str = Field(..., description="Target language code")


class TranslateResponse(BaseModel):
    """Translation response"""
    source_text: str
    source_language: str
    source_language_name: str
    target_language: str
    target_language_name: str
    translated_text: str
    confidence: float
    model_used: str


class TransliterateRequest(BaseModel):
    """Transliteration request (script conversion)"""
    text: str = Field(..., description="Text to convert")
    source_script: str = Field("Devanagari", description="Source script")
    target_script: str = Field("IAST", description="Target script")


class TransliterateResponse(BaseModel):
    """Transliteration response"""
    source_text: str
    source_script: str
    target_script: str
    transliterated_text: str
    model_used: str = "IndicTrans2"


class BatchTranslateRequest(BaseModel):
    """Batch translation request"""
    texts: List[str] = Field(..., description="List of texts to translate")
    source_language: str
    target_language: str


class BatchTranslateResponse(BaseModel):
    """Batch translation response"""
    results: List[TranslateResponse]
    count: int
    average_confidence: float


class LanguagesResponse(BaseModel):
    """Available languages"""
    languages: dict
    total_count: int
    supported_pairs_count: int


LANGUAGE_NAMES = {
    "hi": "Hindi",
    "sa": "Sanskrit",
    "mr": "Marathi",
    "ne": "Nepali",
    "ta": "Tamil",
    "te": "Telugu",
    "kn": "Kannada",
    "ml": "Malayalam",
    "gu": "Gujarati",
    "pa": "Punjabi",
    "ur": "Urdu",
    "as": "Assamese",
    "bn": "Bengali",
    "or": "Oriya",
    "mni": "Manipuri",
    "sd": "Sindhi",
    "ks": "Kashmiri",
    "en": "English"
}


@router.post("/translate", response_model=TranslateResponse)
async def translate_text(
    request: TranslateRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Translate text between Indian languages and English.
    
    **Supported Languages:**
    - Hindi (hi), Tamil (ta), Telugu (te), Kannada (kn), Malayalam (ml)
    - Gujarati (gu), Punjabi (pa), Marathi (mr), Bengali (bn), Oriya (or)
    - Assamese (as), Urdu (ur), Sanskrit (sa), Nepali (ne), Manipuri (mni)
    - Kashmiri (ks), Sindhi (sd), English (en)
    
    **Examples:**
    ```bash
    # Hindi to English
    curl -X POST http://localhost:8000/v1/translate/translate \\
      -H "Authorization: Bearer YOUR_TOKEN" \\
      -H "Content-Type: application/json" \\
      -d '{
        "text": "नमस्ते, आप कैसे हैं?",
        "source_language": "hi",
        "target_language": "en"
      }'
    
    # English to Tamil
    curl -X POST http://localhost:8000/v1/translate/translate \\
      -H "Authorization: Bearer YOUR_TOKEN" \\
      -H "Content-Type: application/json" \\
      -d '{
        "text": "Hello, how are you?",
        "source_language": "en",
        "target_language": "ta"
      }'
    ```
    """
    try:
        engine = get_indictrans_engine()
        
        result = await engine.translate(
            text=request.text,
            source_language=request.source_language,
            target_language=request.target_language
        )
        
        source_name = LANGUAGE_NAMES.get(request.source_language, request.source_language)
        target_name = LANGUAGE_NAMES.get(request.target_language, request.target_language)
        
        return TranslateResponse(
            source_text=result.source_text,
            source_language=result.source_language,
            source_language_name=source_name,
            target_language=result.target_language,
            target_language_name=target_name,
            translated_text=result.translated_text,
            confidence=result.confidence,
            model_used=result.model_used
        )
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Translation error: {e}")
        raise HTTPException(status_code=500, detail=f"Translation failed: {str(e)}")


@router.post("/batch", response_model=BatchTranslateResponse)
async def batch_translate(
    request: BatchTranslateRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Translate multiple texts in batch.
    
    **Use Cases:**
    - Multi-language support for medical documents
    - Patient education materials in multiple languages
    - Multilingual clinical reports
    """
    try:
        engine = get_indictrans_engine()
        
        results = await engine.translate_batch(
            texts=request.texts,
            source_language=request.source_language,
            target_language=request.target_language
        )
        
        source_name = LANGUAGE_NAMES.get(request.source_language, request.source_language)
        target_name = LANGUAGE_NAMES.get(request.target_language, request.target_language)
        
        responses = [
            TranslateResponse(
                source_text=r.source_text,
                source_language=r.source_language,
                source_language_name=source_name,
                target_language=r.target_language,
                target_language_name=target_name,
                translated_text=r.translated_text,
                confidence=r.confidence,
                model_used=r.model_used
            )
            for r in results
        ]
        
        avg_confidence = sum(r.confidence for r in results) / len(results) if results else 0
        
        return BatchTranslateResponse(
            results=responses,
            count=len(results),
            average_confidence=avg_confidence
        )
    
    except Exception as e:
        logger.error(f"Batch translation error: {e}")
        raise HTTPException(status_code=500, detail=f"Batch translation failed: {str(e)}")


@router.post("/transliterate", response_model=TransliterateResponse)
async def transliterate_text(
    request: TransliterateRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Convert between scripts (Devanagari ↔ IAST, Latin, etc.).
    
    **Supported Scripts:**
    - Devanagari (Hindi, Sanskrit, Marathi, Nepali)
    - IAST (International Alphabet of Sanskrit Transliteration)
    - ISO (ISO 15919 transliteration)
    - Latin/Roman
    - SLP1, WX, Kolkata
    - Tamil, Telugu, Kannada, Malayalam scripts
    
    **Example:**
    ```bash
    # Devanagari to IAST
    curl -X POST http://localhost:8000/v1/translate/transliterate \\
      -H "Authorization: Bearer YOUR_TOKEN" \\
      -H "Content-Type: application/json" \\
      -d '{
        "text": "नमस्ते",
        "source_script": "Devanagari",
        "target_script": "IAST"
      }'
    
    Response: "namaste"
    ```
    """
    try:
        engine = get_indictrans_engine()
        
        result = await engine.transliterate(
            text=request.text,
            source_script=request.source_script,
            target_script=request.target_script
        )
        
        return TransliterateResponse(
            source_text=request.text,
            source_script=request.source_script,
            target_script=request.target_script,
            transliterated_text=result
        )
    
    except Exception as e:
        logger.error(f"Transliteration error: {e}")
        raise HTTPException(status_code=500, detail=f"Transliteration failed: {str(e)}")


@router.get("/languages", response_model=LanguagesResponse)
async def get_languages(
    current_user: User = Depends(get_optional_user)
):
    """
    Get list of supported languages.
    
    **Response:**
    ```json
    {
      "languages": {
        "hi": "Hindi",
        "ta": "Tamil",
        "en": "English",
        ...
      },
      "total_count": 18,
      "supported_pairs_count": 306
    }
    ```
    """
    engine = get_indictrans_engine()
    langs = engine.get_supported_languages()
    pairs = engine.get_language_pairs()
    
    return LanguagesResponse(
        languages=langs,
        total_count=len(langs),
        supported_pairs_count=len(pairs)
    )


@router.get("/language-pairs")
async def get_language_pairs(
    current_user: User = Depends(get_current_user)
):
    """
    Get all supported language pairs for translation.
    
    Returns: List of (source_lang, target_lang) tuples
    """
    engine = get_indictrans_engine()
    pairs = engine.get_language_pairs()
    
    return {
        "total_pairs": len(pairs),
        "pairs": [
            {
                "source": src,
                "source_name": LANGUAGE_NAMES.get(src, src),
                "target": tgt,
                "target_name": LANGUAGE_NAMES.get(tgt, tgt)
            }
            for src, tgt in pairs
        ]
    }


@router.post("/document-translate")
async def translate_document(
    file_content: str,
    source_language: str,
    target_language: str,
    current_user: User = Depends(get_current_user)
):
    """
    Translate entire document (medical record, prescription, etc.).
    
    **Use Cases:**
    - Multilingual medical records
    - Patient-friendly health information
    - Insurance claims in regional languages
    
    Returns: Full translated document
    """
    try:
        engine = get_indictrans_engine()
        
        # Split by sentences/paragraphs for better translation
        paragraphs = file_content.split('\n')
        
        translated_paragraphs = []
        for para in paragraphs:
            if para.strip():
                result = await engine.translate(
                    text=para,
                    source_language=source_language,
                    target_language=target_language
                )
                translated_paragraphs.append(result.translated_text)
            else:
                translated_paragraphs.append('')
        
        translated_document = '\n'.join(translated_paragraphs)
        
        source_name = LANGUAGE_NAMES.get(source_language, source_language)
        target_name = LANGUAGE_NAMES.get(target_language, target_language)
        
        return {
            "source_language": source_language,
            "source_language_name": source_name,
            "target_language": target_language,
            "target_language_name": target_name,
            "original_document": file_content,
            "translated_document": translated_document,
            "paragraph_count": len([p for p in paragraphs if p.strip()])
        }
    
    except Exception as e:
        logger.error(f"Document translation error: {e}")
        raise HTTPException(status_code=500, detail=f"Document translation failed: {str(e)}")
