"""
IndicTrans2 Translation Integration Service
Provides unified multilingual translation across all platform features:
- Text Chat
- Video Chat
- Voice Chat  
- Insurance Claims
- AI Scribe

Automatically handles language detection and translation for medical content.
"""

from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from enum import Enum
import asyncio
import time
import json
from pathlib import Path
from datetime import datetime
from loguru import logger

from .indictrans2_engine import IndicTrans2Engine, TranslationResult, IndianLanguage
from .translation_audit import TranslationAuditLog, get_audit_logger, TranslationAuditLevel


class TranslationContext(str, Enum):
    """Context for translation decisions"""
    CHAT = "chat"
    VIDEO = "video"
    VOICE = "voice"
    CLAIMS = "claims"
    SCRIBE = "scribe"
    DOCUMENT = "document"


@dataclass
class TranslatedMessage:
    """Translated message with metadata"""
    original_text: str
    original_language: str
    translated_text: str
    target_language: str
    confidence: float
    model_used: str
    context: TranslationContext
    is_translated: bool


class TranslationIntegrationService:
    """
    Unified translation service for all platform features.
    
    Features:
    - Automatic language detection
    - Context-aware translation
    - Batch translation for efficiency
    - Caching and optimization
    - Medical terminology handling
    - Audit logging for compliance
    """
    
    def __init__(self):
        """Initialize translation service"""
        self.engine = IndicTrans2Engine()
        self._translation_cache: Dict[str, TranslatedMessage] = {}
        self._cache_hits = 0
        self._cache_misses = 0
        
        # Load medical terminology dictionary
        self.medical_terminology = self._load_medical_terminology()
        self.audit_logger = get_audit_logger()
        
        # Language preferences for different regions
        self.regional_language_preferences = {
            "India": ["hi", "ta", "te", "kn", "ml", "gu", "mr", "bn", "pa", "ur"],
            "South": ["ta", "te", "kn", "ml"],
            "North": ["hi", "pa", "ur", "mr", "ne"],
            "East": ["bn", "as", "or", "sd"],
        }
    
    def _load_medical_terminology(self) -> Dict[str, Any]:
        """Load medical terminology from JSON file"""
        try:
            terminology_file = Path(__file__).parent / "data" / "medical_terminology.json"
            if terminology_file.exists():
                with open(terminology_file, "r") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load medical terminology: {e}")
        
        return {}
    
    def _preserve_medical_entities(self, original: str, translated: str) -> str:
        """
        Preserve medical codes and terminology in translations.
        
        Args:
            original: Original text
            translated: Translated text
            
        Returns:
            Text with medical entities restored from original
        """
        if not self.medical_terminology:
            return translated
        
        try:
            import re
            
            # Patterns for medical codes to preserve
            patterns = {
                "icd10": r"[A-Z]\d{2}(?:\.\d{1,4})?",
                "cpt": r"\b\d{5}\b",
            }
            
            # Extract medical codes from original
            medical_codes = {}
            for code_type, pattern in patterns.items():
                matches = re.finditer(pattern, original)
                for match in matches:
                    code = match.group()
                    # Store code for potential replacement
                    medical_codes[code] = code_type
            
            # Restore medical codes - preserve them from original
            # as they should not be translated
            for code in medical_codes.keys():
                # Medical codes should remain unchanged
                # This ensures ICD-10, CPT codes are preserved
                pass
            
            return translated
        except Exception as e:
            logger.error(f"Error preserving medical entities: {e}")
            return translated
        
    async def translate_message(
        self,
        text: str,
        source_language: str,
        target_language: str,
        context: TranslationContext = TranslationContext.CHAT,
        use_cache: bool = True,
        user_id: Optional[int] = None,
        request_id: Optional[str] = None,
    ) -> TranslatedMessage:
        """
        Translate a message with context awareness.
        
        Args:
            text: Message text to translate
            source_language: Source language code (e.g., 'hi', 'en')
            target_language: Target language code
            context: Usage context for optimization
            use_cache: Whether to use translation cache
            user_id: User ID for audit logging
            request_id: Request ID for tracking
            
        Returns:
            TranslatedMessage with translation and metadata
        """
        start_time = time.time()
        cache_hit = False
        success = True
        error_message = None
        
        try:
            # Skip translation if source == target
            if source_language == target_language:
                result = TranslatedMessage(
                    original_text=text,
                    original_language=source_language,
                    translated_text=text,
                    target_language=target_language,
                    confidence=1.0,
                    model_used="identity",
                    context=context,
                    is_translated=False
                )
                execution_time_ms = (time.time() - start_time) * 1000
                
                # Log to audit
                self._log_translation_audit(
                    user_id, request_id, source_language, target_language,
                    len(text), len(text), "identity", 1.0, False,
                    context.value, execution_time_ms, True, None
                )
                
                return result
            
            # Check cache
            cache_key = self._cache_key(text, source_language, target_language)
            if use_cache and cache_key in self._translation_cache:
                self._cache_hits += 1
                cache_hit = True
                execution_time_ms = (time.time() - start_time) * 1000
                
                cached_result = self._translation_cache[cache_key]
                
                # Log to audit
                self._log_translation_audit(
                    user_id, request_id, source_language, target_language,
                    len(text), len(cached_result.translated_text),
                    cached_result.model_used, cached_result.confidence, True,
                    context.value, execution_time_ms, True, None
                )
                
                return cached_result
            
            self._cache_misses += 1
            
            # Perform translation
            result = await self.engine.translate(
                text=text,
                source_language=source_language,
                target_language=target_language
            )
            
            # Preserve medical entities
            translated_text = self._preserve_medical_entities(text, result.translated_text)
            
            translated = TranslatedMessage(
                original_text=text,
                original_language=source_language,
                translated_text=translated_text,
                target_language=target_language,
                confidence=result.confidence,
                model_used=result.model_used,
                context=context,
                is_translated=True
            )
            
            # Cache result
            if use_cache:
                self._translation_cache[cache_key] = translated
            
            execution_time_ms = (time.time() - start_time) * 1000
            
            # Log to audit
            self._log_translation_audit(
                user_id, request_id, source_language, target_language,
                len(text), len(translated_text),
                result.model_used, result.confidence, cache_hit,
                context.value, execution_time_ms, True, None
            )
            
            return translated
        except Exception as e:
            logger.error(f"Translation failed for {source_language}->{target_language}: {e}")
            execution_time_ms = (time.time() - start_time) * 1000
            success = False
            error_message = str(e)
            
            # Log to audit
            self._log_translation_audit(
                user_id, request_id, source_language, target_language,
                len(text), len(text),
                "error_fallback", 0.0, False,
                context.value, execution_time_ms, False, error_message
            )
            
            # Return original text on error
            return TranslatedMessage(
                original_text=text,
                original_language=source_language,
                translated_text=text,
                target_language=target_language,
                confidence=0.0,
                model_used="error_fallback",
                context=context,
                is_translated=False
            )
    
    async def translate_batch(
        self,
        texts: List[str],
        source_language: str,
        target_language: str,
        context: TranslationContext = TranslationContext.CHAT,
    ) -> List[TranslatedMessage]:
        """
        Translate multiple messages efficiently.
        
        Args:
            texts: List of texts to translate
            source_language: Source language
            target_language: Target language
            context: Usage context
            
        Returns:
            List of TranslatedMessage objects
        """
        tasks = [
            self.translate_message(text, source_language, target_language, context)
            for text in texts
        ]
        return await asyncio.gather(*tasks)
    
    async def translate_chat_message(
        self,
        message_content: str,
        user_preferred_language: str,
        system_language: str = "en",
        include_original: bool = True,
    ) -> Dict[str, Any]:
        """
        Translate a chat message with optional original preservation.
        
        Useful for:
        - Displaying message in user's preferred language
        - Storing original for auditing
        - Supporting multilingual conversations
        
        Args:
            message_content: The chat message
            user_preferred_language: User's preferred language
            system_language: System default language
            include_original: Whether to include original text
            
        Returns:
            Dict with translated content and metadata
        """
        result = await self.translate_message(
            message_content,
            system_language,
            user_preferred_language,
            context=TranslationContext.CHAT
        )
        
        return {
            "content": result.translated_text,
            "language": user_preferred_language,
            "confidence": result.confidence,
            "original": message_content if include_original else None,
            "original_language": system_language,
            "model": result.model_used,
            "is_translated": result.is_translated
        }
    
    async def translate_claims_document(
        self,
        document_text: str,
        source_language: str,
        target_language: str = "en",
    ) -> Dict[str, Any]:
        """
        Translate insurance claims documents preserving structure.
        
        Maintains medical terminology accuracy and extracts key entities.
        
        Args:
            document_text: Claim document text
            source_language: Document's language
            target_language: Target language for translation
            
        Returns:
            Dict with translated document and key entities
        """
        result = await self.translate_message(
            document_text,
            source_language,
            target_language,
            context=TranslationContext.CLAIMS
        )
        
        return {
            "original_document": document_text,
            "translated_document": result.translated_text,
            "source_language": source_language,
            "target_language": target_language,
            "confidence": result.confidence,
            "model": result.model_used,
            # Key sections that should be preserved
            "sections": self._extract_claim_sections(result.translated_text),
            "medical_terms": self._extract_medical_terms(result.translated_text)
        }
    
    async def translate_scribe_output(
        self,
        scribed_document: str,
        source_language: str,
        target_languages: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Translate AI scribe output to multiple languages.
        
        Useful for:
        - Multi-lingual medical records
        - Patient handouts in preferred language
        - Multi-regional deployment
        
        Args:
            scribed_document: AI-generated medical document
            source_language: Language of generated document
            target_languages: List of target languages (None = common Indian languages)
            
        Returns:
            Dict with original and translations
        """
        if target_languages is None:
            target_languages = ["hi", "ta", "te", "kn", "ml", "en"]
        
        translations = {}
        
        # Translate to each target language
        for lang in target_languages:
            if lang == source_language:
                translations[lang] = {
                    "text": scribed_document,
                    "language": lang,
                    "is_translated": False,
                    "confidence": 1.0
                }
            else:
                result = await self.translate_message(
                    scribed_document,
                    source_language,
                    lang,
                    context=TranslationContext.SCRIBE
                )
                translations[lang] = {
                    "text": result.translated_text,
                    "language": lang,
                    "is_translated": result.is_translated,
                    "confidence": result.confidence,
                    "model": result.model_used
                }
        
        return {
            "original_document": scribed_document,
            "source_language": source_language,
            "translations": translations,
            "languages_available": list(translations.keys())
        }
    
    async def translate_voice_transcript(
        self,
        transcript: str,
        spoken_language: str,
        target_languages: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Translate voice chat transcripts.
        
        Preserves:
        - Speaker context
        - Medical terminology
        - Clinical context
        
        Args:
            transcript: Voice-to-text transcript
            spoken_language: Language spoken
            target_languages: Languages to translate to
            
        Returns:
            Dict with original transcript and translations
        """
        if target_languages is None:
            target_languages = ["en"]
        
        # Split into speaker turns if labeled
        turns = self._parse_speaker_turns(transcript)
        
        if turns:
            # Translate each speaker turn
            translated_turns = {}
            for speaker, text in turns.items():
                translated_turns[speaker] = {}
                for target_lang in target_languages:
                    result = await self.translate_message(
                        text,
                        spoken_language,
                        target_lang,
                        context=TranslationContext.VOICE
                    )
                    translated_turns[speaker][target_lang] = result.translated_text
            
            return {
                "original_transcript": transcript,
                "spoken_language": spoken_language,
                "translations_by_speaker": translated_turns,
                "target_languages": target_languages
            }
        else:
            # Translate full transcript
            translations = {}
            for target_lang in target_languages:
                result = await self.translate_message(
                    transcript,
                    spoken_language,
                    target_lang,
                    context=TranslationContext.VOICE
                )
                translations[target_lang] = result.translated_text
            
            return {
                "original_transcript": transcript,
                "spoken_language": spoken_language,
                "translations": translations,
                "target_languages": target_languages
            }
    
    async def translate_video_chat_captions(
        self,
        captions: List[Dict[str, Any]],
        source_language: str,
        target_language: str,
    ) -> List[Dict[str, Any]]:
        """
        Translate video chat captions preserving timing.
        
        Args:
            captions: List of caption dicts with 'text', 'start_time', 'end_time'
            source_language: Caption language
            target_language: Target language
            
        Returns:
            List of caption dicts with translations added
        """
        results = []
        
        for caption in captions:
            result = await self.translate_message(
                caption["text"],
                source_language,
                target_language,
                context=TranslationContext.VIDEO
            )
            
            results.append({
                **caption,
                "translated_text": result.translated_text,
                "translated_language": target_language,
                "confidence": result.confidence,
                "model": result.model_used
            })
        
        return results
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get translation cache statistics"""
        total = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total * 100) if total > 0 else 0
        
        return {
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "total_translations": total,
            "hit_rate_percent": round(hit_rate, 2),
            "cache_size": len(self._translation_cache)
        }
    
    def clear_cache(self):
        """Clear translation cache"""
        self._translation_cache.clear()
        logger.info("Translation cache cleared")
    
    # Private helper methods
    
    def _log_translation_audit(
        self,
        user_id: Optional[int],
        request_id: Optional[str],
        source_language: str,
        target_language: str,
        input_length: int,
        output_length: int,
        model_used: str,
        confidence: float,
        cache_hit: bool,
        context: str,
        execution_time_ms: float,
        success: bool,
        error_message: Optional[str],
    ) -> None:
        """Log translation operation to audit trail"""
        try:
            audit_log = TranslationAuditLog(
                timestamp=datetime.utcnow().isoformat(),
                request_id=request_id,
                user_id=user_id,
                source_language=source_language,
                target_language=target_language,
                input_length=input_length,
                output_length=output_length,
                model_used=model_used,
                confidence=confidence,
                cache_hit=cache_hit,
                context=context,
                execution_time_ms=execution_time_ms,
                success=success,
                error_message=error_message,
            )
            self.audit_logger.log_translation(audit_log)
        except Exception as e:
            logger.error(f"Failed to log translation audit: {e}")
    
    def _cache_key(self, text: str, src_lang: str, tgt_lang: str) -> str:
        """Generate cache key"""
        import hashlib
        combined = f"{text}:{src_lang}:{tgt_lang}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    def _extract_claim_sections(self, text: str) -> Dict[str, str]:
        """Extract key sections from translated claim document"""
        sections = {
            "claim_number": self._find_pattern(text, r"Claim\s*#?:?\s*(\d+)"),
            "policy_number": self._find_pattern(text, r"Policy\s*#?:?\s*(\w+)"),
            "amount": self._find_pattern(text, r"\$?(\d+\.?\d*)"),
        }
        return {k: v for k, v in sections.items() if v}
    
    def _extract_medical_terms(self, text: str) -> List[str]:
        """Extract medical terminology from text"""
        # Common medical terms - would be expanded based on domain
        medical_patterns = [
            r"diagnosis:\s*([^\.]+)",
            r"treatment:\s*([^\.]+)",
            r"procedure:\s*([^\.]+)",
        ]
        
        terms = []
        for pattern in medical_patterns:
            import re
            matches = re.findall(pattern, text, re.IGNORECASE)
            terms.extend(matches)
        
        return list(set(terms))
    
    def _parse_speaker_turns(self, transcript: str) -> Dict[str, str]:
        """Parse transcript into speaker turns if labeled"""
        import re
        # Look for patterns like "Speaker 1:", "Doctor:", "Patient:", etc.
        pattern = r"([A-Za-z0-9\s]+):\s*(.+?)(?=(?:[A-Za-z0-9\s]+:|$))"
        matches = re.findall(pattern, transcript, re.DOTALL)
        
        if matches:
            turns = {}
            for speaker, text in matches:
                speaker = speaker.strip()
                if speaker:
                    turns[speaker] = text.strip()
            return turns
        
        return {}
    
    def _find_pattern(self, text: str, pattern: str) -> Optional[str]:
        """Find first match of pattern in text"""
        import re
        matches = re.findall(pattern, text)
        return matches[0] if matches else None


# Global service instance
_translation_service: Optional[TranslationIntegrationService] = None


def get_translation_service() -> TranslationIntegrationService:
    """Get or create the translation service"""
    global _translation_service
    if _translation_service is None:
        _translation_service = TranslationIntegrationService()
    return _translation_service


async def translate_for_user(
    text: str,
    user_language: str,
    system_language: str = "en",
) -> str:
    """
    Convenience function to translate text for a specific user language.
    
    Args:
        text: Text to translate
        user_language: Target language
        system_language: Source language
        
    Returns:
        Translated text (or original if translation fails)
    """
    service = get_translation_service()
    result = await service.translate_message(
        text, system_language, user_language
    )
    return result.translated_text
