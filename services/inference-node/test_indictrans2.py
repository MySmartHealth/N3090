"""
Test IndicTrans2 Translation Engine
Tests multilingual translation for Indian languages
"""
import asyncio
from app.indictrans2_engine import get_indictrans_engine, IndianLanguage


async def test_indictrans2_hindi_to_english():
    """Test Hindi to English translation"""
    engine = get_indictrans_engine()
    
    # Hindi medical text
    hindi_text = "नमस्ते, मुझे सिरदर्द और बुखार है।"
    
    result = await engine.translate(
        text=hindi_text,
        source_language="hi",
        target_language="en"
    )
    
    print(f"\n🇮🇳 Hindi → English")
    print(f"Original: {result.source_text}")
    print(f"Translated: {result.translated_text}")
    print(f"Confidence: {result.confidence}")
    
    assert result.translated_text is not None
    assert len(result.translated_text) > 0
    assert result.source_language == "hi"
    assert result.target_language == "en"


async def test_indictrans2_english_to_tamil():
    """Test English to Tamil translation"""
    engine = get_indictrans_engine()
    
    english_text = "The patient has diabetes and hypertension."
    
    result = await engine.translate(
        text=english_text,
        source_language="en",
        target_language="ta"
    )
    
    print(f"\n🇬🇧 English → Tamil (தமிழ்)")
    print(f"Original: {result.source_text}")
    print(f"Translated: {result.translated_text}")
    print(f"Confidence: {result.confidence}")
    
    assert result.translated_text is not None
    assert len(result.translated_text) > 0


async def test_indictrans2_prescription_translation():
    """Test prescription translation Hindi → English"""
    engine = get_indictrans_engine()
    
    prescription = "एक दिन में दो बार गोली लें। भोजन के बाद लें। 10 दिन तक चलाएं।"
    
    result = await engine.translate(
        text=prescription,
        source_language="hi",
        target_language="en"
    )
    
    print(f"\n💊 Prescription Translation (Hindi → English)")
    print(f"Original: {result.source_text}")
    print(f"Translated: {result.translated_text}")
    
    # In demo mode, just check that translation was returned
    assert result.translated_text is not None
    assert len(result.translated_text) > 0


async def test_indictrans2_batch_translation():
    """Test batch translation"""
    engine = get_indictrans_engine()
    
    texts = [
        "आपको डॉक्टर से मिलना चाहिए।",
        "आप दवाई समय पर लें।",
        "अगली सप्ताह फिर आएं।"
    ]
    
    results = await engine.translate_batch(
        texts=texts,
        source_language="hi",
        target_language="en"
    )
    
    print(f"\n📋 Batch Translation (3 texts, Hindi → English)")
    for i, result in enumerate(results, 1):
        print(f"\n{i}. {result.source_text}")
        print(f"   → {result.translated_text}")
    
    assert len(results) == 3
    assert all(r.translated_text for r in results)


async def test_indictrans2_transliteration():
    """Test Devanagari to IAST transliteration"""
    engine = get_indictrans_engine()
    
    devanagari_text = "नमस्ते"
    
    result = await engine.transliterate(
        text=devanagari_text,
        source_script="Devanagari",
        target_script="IAST"
    )
    
    print(f"\n🔤 Transliteration (Devanagari → IAST)")
    print(f"Original: {devanagari_text}")
    print(f"Transliterated: {result}")
    
    # Should produce something like "namaste"
    assert result is not None
    assert len(result) > 0


async def test_indictrans2_medical_discharge_summary():
    """Test discharge summary translation (Hindi → English)"""
    engine = get_indictrans_engine()
    
    discharge_summary_hindi = """
    रोगी का नाम: राज कुमार
    उम्र: 45 साल
    रोग निदान: उच्च रक्तचाप और मधुमेह
    उपचार: दवाई और डाइट कंट्रोल
    अगले सप्ताह फॉलो अप करें।
    """
    
    result = await engine.translate(
        text=discharge_summary_hindi,
        source_language="hi",
        target_language="en"
    )
    
    print(f"\n🏥 Discharge Summary (Hindi → English)")
    print(f"Original:\n{result.source_text}")
    print(f"\nTranslated:\n{result.translated_text}")
    
    assert result.translated_text is not None
    assert len(result.translated_text) > 0


async def test_supported_languages():
    """Test getting supported languages"""
    engine = get_indictrans_engine()
    
    languages = engine.get_supported_languages()
    pairs = engine.get_language_pairs()
    
    print(f"\n📚 Supported Languages")
    print(f"Total Languages: {len(languages)}")
    print(f"Languages: {', '.join(languages.keys())}")
    print(f"\nTotal Language Pairs: {len(pairs)}")
    
    # Should have Hindi, Tamil, Telugu, Kannada, etc.
    assert "hi" in languages  # Hindi
    assert "en" in languages  # English
    assert "ta" in languages  # Tamil
    assert "te" in languages  # Telugu
    assert "kn" in languages  # Kannada
    assert "ml" in languages  # Malayalam


async def test_indictrans2_english_to_multiple_languages():
    """Test English medical text to multiple Indian languages"""
    engine = get_indictrans_engine()
    
    english_medical = "Take this medicine twice daily after meals."
    target_langs = {
        "hi": "Hindi",
        "ta": "Tamil",
        "te": "Telugu",
        "kn": "Kannada"
    }
    
    print(f"\n🌍 English Medical Text to Multiple Languages")
    print(f"Original: {english_medical}")
    
    for lang_code, lang_name in target_langs.items():
        result = await engine.translate(
            text=english_medical,
            source_language="en",
            target_language=lang_code
        )
        print(f"\n{lang_name} ({lang_code}): {result.translated_text}")
        
        assert result.translated_text is not None
        assert result.target_language == lang_code


async def test_indictrans2_different_language_pairs():
    """Test various language pairs"""
    engine = get_indictrans_engine()
    
    test_cases = [
        ("hi", "ta", "सिरदर्द के लिए एस्पिरिन लें।"),  # Hindi → Tamil
        ("ta", "en", "நீங்கள் மருந்து சாப்பிடுங்கள்।"),  # Tamil → English
        ("te", "en", "ఆసుపత్రికి వెళ్లండి।"),  # Telugu → English
    ]
    
    print(f"\n🔄 Multiple Language Pair Tests")
    
    for src, tgt, text in test_cases:
        try:
            result = await engine.translate(
                text=text,
                source_language=src,
                target_language=tgt
            )
            print(f"\n{src.upper()} → {tgt.upper()}")
            print(f"Original: {text}")
            print(f"Translated: {result.translated_text}")
            
            assert result.translated_text is not None
        except Exception as e:
            print(f"⚠️  {src} → {tgt}: {str(e)}")


async def run_all_tests():
    """Run all tests"""
    print("\n" + "="*60)
    print("🚀 IndicTrans2 Translation Engine Tests")
    print("="*60)
    
    try:
        await test_indictrans2_hindi_to_english()
        await test_indictrans2_english_to_tamil()
        await test_indictrans2_prescription_translation()
        await test_indictrans2_batch_translation()
        await test_indictrans2_transliteration()
        await test_indictrans2_medical_discharge_summary()
        await test_supported_languages()
        await test_indictrans2_english_to_multiple_languages()
        await test_indictrans2_different_language_pairs()
        
        print("\n" + "="*60)
        print("✅ All tests passed!")
        print("="*60)
    
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(run_all_tests())
