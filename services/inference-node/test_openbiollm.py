#!/usr/bin/env python3
"""
OpenBioLLM-70B Comprehensive Test Suite
Tests: Deep Reasoning, Chat, Medical Documentation, Imaging Reports, Scribe
"""

import requests
import json
import time
from datetime import datetime

BASE_URL = "http://localhost:8080"

def chat_completion(messages, temperature=0.7, max_tokens=1024, stream=False):
    """Send chat completion request to llama.cpp server"""
    payload = {
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": stream
    }
    
    start_time = time.time()
    response = requests.post(f"{BASE_URL}/v1/chat/completions", json=payload)
    elapsed = time.time() - start_time
    
    if response.status_code == 200:
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        usage = result.get("usage", {})
        tokens_generated = usage.get("completion_tokens", 0)
        tokens_per_sec = tokens_generated / elapsed if elapsed > 0 else 0
        return {
            "content": content,
            "elapsed": elapsed,
            "tokens": tokens_generated,
            "tokens_per_sec": tokens_per_sec,
            "usage": usage
        }
    else:
        return {"error": response.text, "status_code": response.status_code}

def print_result(test_name, result):
    """Pretty print test results"""
    print(f"\n{'='*80}")
    print(f"TEST: {test_name}")
    print(f"{'='*80}")
    
    if "error" in result:
        print(f"❌ ERROR: {result['error']}")
        return
    
    print(f"⏱️  Time: {result['elapsed']:.2f}s")
    print(f"📊 Tokens: {result['tokens']} ({result['tokens_per_sec']:.2f} tok/s)")
    print(f"\n📝 Response:\n{'-'*40}")
    print(result['content'][:3000])
    if len(result['content']) > 3000:
        print(f"\n... [truncated, {len(result['content'])} chars total]")
    print(f"{'-'*40}")

def test_deep_reasoning():
    """Test complex medical reasoning and differential diagnosis"""
    print("\n" + "🧠 " * 20)
    print("TESTING: DEEP MEDICAL REASONING")
    print("🧠 " * 20)
    
    messages = [
        {"role": "system", "content": "You are an expert medical diagnostician. Provide detailed differential diagnoses with clinical reasoning."},
        {"role": "user", "content": """A 45-year-old female presents with:
- 3-month history of progressive fatigue
- Unintentional weight loss of 15 lbs
- Night sweats
- Intermittent low-grade fever (99.5-100.5°F)
- Painless lymphadenopathy in the cervical and axillary regions
- Labs: Hgb 10.2, WBC 12,500, Platelets 450,000, ESR 65, LDH elevated

Please provide:
1. Top 5 differential diagnoses ranked by probability
2. Key distinguishing features for each
3. Recommended diagnostic workup
4. Red flags to watch for
5. Clinical reasoning for your top diagnosis"""}
    ]
    
    result = chat_completion(messages, temperature=0.3, max_tokens=2048)
    print_result("Deep Medical Reasoning - Differential Diagnosis", result)
    return result

def test_chat_interaction():
    """Test conversational medical chat"""
    print("\n" + "💬 " * 20)
    print("TESTING: CONVERSATIONAL MEDICAL CHAT")
    print("💬 " * 20)
    
    # Multi-turn conversation
    conversation = [
        {"role": "system", "content": "You are a helpful medical AI assistant providing evidence-based information to healthcare providers."},
        {"role": "user", "content": "What are the current guidelines for hypertension management?"},
    ]
    
    result1 = chat_completion(conversation, temperature=0.5, max_tokens=800)
    print_result("Chat - Initial Query (Hypertension Guidelines)", result1)
    
    # Follow-up question
    if "content" in result1:
        conversation.append({"role": "assistant", "content": result1["content"]})
        conversation.append({"role": "user", "content": "What about resistant hypertension? What additional medications should be considered?"})
        
        result2 = chat_completion(conversation, temperature=0.5, max_tokens=800)
        print_result("Chat - Follow-up (Resistant Hypertension)", result2)
        return result2
    return result1

def test_medical_scribe():
    """Test medical scribe - converting audio transcription to clinical notes"""
    print("\n" + "📋 " * 20)
    print("TESTING: MEDICAL SCRIBE / DOCUMENTATION")
    print("📋 " * 20)
    
    messages = [
        {"role": "system", "content": """You are a medical scribe AI. Convert the following doctor-patient conversation transcript into a structured clinical note in SOAP format (Subjective, Objective, Assessment, Plan). Include appropriate medical terminology and ICD-10 codes where applicable."""},
        {"role": "user", "content": """TRANSCRIPT:

Doctor: Good morning Mrs. Johnson. What brings you in today?

Patient: Hi doctor. I've been having this terrible chest pain for the past two days. It's right here in the center of my chest.

Doctor: Can you describe the pain? Is it sharp, dull, pressure-like?

Patient: It feels like pressure, like something heavy sitting on my chest. It gets worse when I walk up stairs or exert myself.

Doctor: Does it radiate anywhere?

Patient: Yes, sometimes down my left arm and up to my jaw.

Doctor: Any shortness of breath, nausea, sweating?

Patient: Yes, I've been sweating a lot and feel nauseated, especially when the pain is bad.

Doctor: Any history of heart disease in your family?

Patient: My father had a heart attack at 55. My mother has high blood pressure.

Doctor: Let me check your vitals. BP is 165/95, heart rate 92, oxygen saturation 96%. I'm going to order an EKG and some blood work including troponins. Based on your symptoms and risk factors, we need to rule out acute coronary syndrome. I'm going to give you aspirin now and we may need to admit you for observation.

Patient: Is it serious doctor?

Doctor: We're taking it very seriously. Your symptoms are concerning and we want to make sure your heart is okay. The tests will help us determine the next steps."""}
    ]
    
    result = chat_completion(messages, temperature=0.2, max_tokens=1500)
    print_result("Medical Scribe - SOAP Note Generation", result)
    return result

def test_medical_documentation():
    """Test generation of various medical documents"""
    print("\n" + "📄 " * 20)
    print("TESTING: MEDICAL DOCUMENTATION GENERATION")
    print("📄 " * 20)
    
    messages = [
        {"role": "system", "content": "You are a medical documentation specialist. Generate comprehensive, accurate clinical documentation."},
        {"role": "user", "content": """Generate a discharge summary for the following patient:

Patient: John Smith, 62-year-old male
Admission Date: January 3, 2026
Discharge Date: January 8, 2026
Admitting Diagnosis: STEMI (ST-elevation myocardial infarction)
Hospital Course:
- Presented to ED with chest pain, EKG showed ST elevation in leads V1-V4
- Emergent cardiac catheterization revealed 95% LAD occlusion
- Successful PCI with 2 drug-eluting stents placed
- Post-procedure course uncomplicated
- Echo showed EF 45%, anterior wall hypokinesis
- Started on DAPT, high-intensity statin, ACE inhibitor, beta-blocker
- Cardiac rehab referral placed

Include: Principal diagnosis, procedures, medications on discharge, follow-up instructions, activity restrictions, and warning signs to watch for."""}
    ]
    
    result = chat_completion(messages, temperature=0.2, max_tokens=1500)
    print_result("Medical Documentation - Discharge Summary", result)
    return result

def test_imaging_report():
    """Test medical imaging extraction and reporting"""
    print("\n" + "🔬 " * 20)
    print("TESTING: MEDICAL IMAGING REPORT ANALYSIS")
    print("🔬 " * 20)
    
    messages = [
        {"role": "system", "content": "You are a radiologist assistant AI. Analyze imaging findings and generate structured radiology reports."},
        {"role": "user", "content": """Given the following chest CT findings, generate a complete structured radiology report:

FINDINGS:
- Right upper lobe: 2.3 cm spiculated nodule with SUV 8.5 on PET
- Mediastinal lymphadenopathy: 2R lymph node 1.8cm, 4R lymph node 1.5cm, 7 subcarinal 2.1cm
- No pleural effusion
- Heart size normal, no pericardial effusion
- Liver: 1.2 cm hypodense lesion segment 6, indeterminate
- Adrenal glands: bilateral 8mm nodules
- No destructive bone lesions
- Patient history: 58-year-old male, 40 pack-year smoking history, presenting with hemoptysis

Generate a complete structured radiology report including:
1. Clinical indication
2. Technique
3. Comparison
4. Findings (by organ system)
5. Impression with TNM staging if applicable
6. Recommendations"""}
    ]
    
    result = chat_completion(messages, temperature=0.2, max_tokens=1500)
    print_result("Imaging - Structured Radiology Report", result)
    return result

def test_parameter_variations():
    """Test model behavior with different temperature and sampling parameters"""
    print("\n" + "⚙️ " * 20)
    print("TESTING: PARAMETER VARIATIONS")
    print("⚙️ " * 20)
    
    prompt = [
        {"role": "system", "content": "You are a medical AI assistant."},
        {"role": "user", "content": "What are the first-line treatments for Type 2 Diabetes?"}
    ]
    
    # Test different temperatures
    for temp in [0.1, 0.5, 0.9]:
        result = chat_completion(prompt, temperature=temp, max_tokens=400)
        print_result(f"Parameter Test - Temperature {temp}", result)
    
    return result

def test_clinical_decision_support():
    """Test clinical decision support capabilities"""
    print("\n" + "🏥 " * 20)
    print("TESTING: CLINICAL DECISION SUPPORT")
    print("🏥 " * 20)
    
    messages = [
        {"role": "system", "content": "You are a clinical decision support AI. Provide evidence-based recommendations with citations to guidelines where applicable."},
        {"role": "user", "content": """Patient: 72-year-old male with:
- Atrial fibrillation (non-valvular)
- CHA2DS2-VASc score: 4 (age >75, HTN, DM)
- HAS-BLED score: 2
- eGFR: 35 mL/min/1.73m²
- History of GI bleed 2 years ago (on aspirin)
- Currently on no anticoagulation

Questions:
1. Should this patient be anticoagulated? Provide rationale.
2. Which anticoagulant would you recommend and why?
3. What dose adjustments are needed for renal function?
4. How do you balance the bleeding risk vs stroke risk?
5. What monitoring is recommended?"""}
    ]
    
    result = chat_completion(messages, temperature=0.3, max_tokens=1500)
    print_result("Clinical Decision Support - Anticoagulation", result)
    return result

def main():
    print("\n" + "="*80)
    print("OpenBioLLM-70B COMPREHENSIVE TEST SUITE")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # Check server health
    try:
        health = requests.get(f"{BASE_URL}/health")
        print(f"\n✅ Server Status: {health.json()}")
    except Exception as e:
        print(f"\n❌ Server not responding: {e}")
        return
    
    # Run all tests
    results = {}
    
    tests = [
        ("deep_reasoning", test_deep_reasoning),
        ("chat", test_chat_interaction),
        ("scribe", test_medical_scribe),
        ("documentation", test_medical_documentation),
        ("imaging", test_imaging_report),
        ("clinical_decision", test_clinical_decision_support),
        ("parameters", test_parameter_variations),
    ]
    
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"\n❌ Test {name} failed: {e}")
            results[name] = {"error": str(e)}
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    for name, result in results.items():
        if "error" in result:
            print(f"❌ {name}: FAILED")
        else:
            print(f"✅ {name}: {result.get('tokens', 0)} tokens in {result.get('elapsed', 0):.2f}s ({result.get('tokens_per_sec', 0):.2f} tok/s)")
    
    print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
