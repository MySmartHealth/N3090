"""
Data preparation script for fine-tuning Claims OCR agent
Converts historical claims data into training datasets for BiMediX and OpenInsurance
"""
import json
import pandas as pd
import argparse
from pathlib import Path
from typing import List, Dict
from datetime import datetime


def prepare_bimedix_dataset(claims_df: pd.DataFrame, output_path: str):
    """
    Prepare training data for BiMediX medical entity validation
    
    Args:
        claims_df: DataFrame with columns: claim_id, diagnosis_codes, procedure_codes,
                   service_date, medical_analysis_expert
        output_path: Path to save JSONL training file
    """
    training_examples = []
    
    for idx, row in claims_df.iterrows():
        instruction = f"""Analyze these medical entities for clinical accuracy:

**Extracted Medical Data:**
- Diagnosis Codes (ICD-10): {row['diagnosis_codes']}
- Procedure Codes (CPT): {row['procedure_codes']}
- Service Date: {row['service_date']}

**Assess the following:**
1. ICD-10 Code Validity: Are the diagnosis codes clinically appropriate?
2. CPT Code Accuracy: Do procedure codes match the diagnoses?
3. Medical Necessity: Is the treatment medically necessary for these diagnoses?
4. Coding Specificity: Are codes specific enough or too general?
5. Clinical Coherence: Do diagnoses and procedures make clinical sense together?

Provide:
- Clinical assessment of medical necessity
- Any concerns about coding accuracy
- Potential medical flags or inconsistencies
- Recommendations for clinical review
"""

        # Expert's medical analysis (ground truth label)
        response = row['medical_analysis_expert']
        
        training_examples.append({
            "instruction": instruction.strip(),
            "output": response.strip(),
            "metadata": {
                "claim_id": row['claim_id'],
                "diagnosis_codes": row['diagnosis_codes'],
                "procedure_codes": row['procedure_codes'],
                "final_decision": row.get('final_decision', 'unknown')
            }
        })
    
    # Save as JSONL
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        for example in training_examples:
            f.write(json.dumps(example, ensure_ascii=False) + '\n')
    
    print(f"✅ Created {len(training_examples)} BiMediX training examples")
    print(f"   Saved to: {output_path}")
    return len(training_examples)


def prepare_openinsurance_dataset(claims_df: pd.DataFrame, output_path: str):
    """
    Prepare training data for OpenInsurance claims adjudication
    
    Args:
        claims_df: DataFrame with columns: claim_id, policy_id, diagnosis_codes,
                   procedure_codes, claim_amount, service_date, medical_analysis_expert,
                   adjudication_decision_expert
        output_path: Path to save JSONL training file
    """
    training_examples = []
    
    for idx, row in claims_df.iterrows():
        # Use BiMediX analysis as context (simulating dual-model approach)
        medical_context = row.get('medical_analysis_expert', 'Not available')
        
        instruction = f"""Review this insurance claim for admissibility.

**Claim Information:**
- Claim Number: {row.get('claim_number', 'N/A')}
- Policy Number: {row.get('policy_number', 'N/A')}
- Policy ID: {row['policy_id']}
- Diagnosis Codes: {row['diagnosis_codes']}
- Procedure Codes: {row['procedure_codes']}
- Claim Amount: ${row['claim_amount']}
- Service Date: {row['service_date']}

**Medical Analysis (from clinical AI):**
{medical_context}

**Adjudication Criteria:**
1. Coverage Verification: Are the diagnosis/procedure codes covered under policy {row['policy_id']}?
2. Medical Necessity: Is the treatment medically necessary based on the diagnosis?
3. Coding Accuracy: Are ICD-10 and CPT codes appropriate and properly documented?
4. Prior Authorization: Does this claim require prior authorization?
5. Network Status: Is this an in-network or out-of-network claim?

**Provide:**
- Decision: APPROVED / DENIED / PENDING
- Confidence: 0-100%
- Detailed reasoning for decision
- Missing information (if any)
- Recommendations for provider or patient
"""

        # Expert's adjudication decision (ground truth label)
        response = row['adjudication_decision_expert']
        
        training_examples.append({
            "instruction": instruction.strip(),
            "output": response.strip(),
            "metadata": {
                "claim_id": row['claim_id'],
                "policy_id": row['policy_id'],
                "claim_amount": float(row['claim_amount']),
                "final_decision": row.get('final_decision', 'unknown')
            }
        })
    
    # Save as JSONL
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        for example in training_examples:
            f.write(json.dumps(example, ensure_ascii=False) + '\n')
    
    print(f"✅ Created {len(training_examples)} OpenInsurance training examples")
    print(f"   Saved to: {output_path}")
    return len(training_examples)


def prepare_scribe_dataset(documents_df: pd.DataFrame, output_path: str):
    """
    Prepare training data for AI Scribe clinical documentation
    
    Args:
        documents_df: DataFrame with columns: dictation, document_type, final_document,
                      physician_edits (optional)
        output_path: Path to save JSONL training file
    """
    training_examples = []
    
    for idx, row in documents_df.iterrows():
        doc_type = row['document_type']
        
        # Build type-specific instruction
        if doc_type == 'prescription':
            task_desc = """Generate a properly formatted prescription based on the doctor's dictation.

Include:
1. Patient name and DOB (if available)
2. Medication name
3. Dosage and form
4. Frequency and route
5. Quantity and refills
6. Special instructions
7. Prescriber signature line"""

        elif doc_type == 'discharge_summary':
            task_desc = """Generate a comprehensive discharge summary based on the doctor's dictation.

Include standard sections:
1. Patient Demographics
2. Admission Date & Discharge Date
3. Admitting Diagnosis
4. Discharge Diagnosis
5. Hospital Course (brief narrative)
6. Procedures Performed
7. Discharge Medications
8. Discharge Instructions
9. Follow-up Appointments"""

        elif doc_type == 'soap_note':
            task_desc = """Generate a SOAP note from the doctor's dictation.

Format as:
- S (Subjective): Patient's complaints, history
- O (Objective): Vital signs, exam findings
- A (Assessment): Diagnosis, clinical impression
- P (Plan): Treatment plan, medications, follow-up"""

        else:
            task_desc = f"Generate a {doc_type} document from the doctor's dictation."
        
        instruction = f"""You are an AI medical scribe. {task_desc}

**Doctor's Dictation:**
{row['dictation']}

**Output a professional medical document with proper formatting and medical terminology.**
"""

        # Final document (ground truth)
        response = row['final_document']
        
        training_examples.append({
            "instruction": instruction.strip(),
            "output": response.strip(),
            "metadata": {
                "document_type": doc_type,
                "has_edits": bool(row.get('physician_edits')),
                "quality_score": row.get('quality_score', None)
            }
        })
    
    # Save as JSONL
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        for example in training_examples:
            f.write(json.dumps(example, ensure_ascii=False) + '\n')
    
    print(f"✅ Created {len(training_examples)} AI Scribe training examples")
    print(f"   Saved to: {output_path}")
    return len(training_examples)


def split_train_test(input_file: str, train_ratio: float = 0.8):
    """Split dataset into train and test sets"""
    import random
    
    with open(input_file, 'r', encoding='utf-8') as f:
        examples = [json.loads(line) for line in f]
    
    # Shuffle
    random.seed(42)
    random.shuffle(examples)
    
    # Split
    split_idx = int(len(examples) * train_ratio)
    train_examples = examples[:split_idx]
    test_examples = examples[split_idx:]
    
    # Save splits
    base_path = Path(input_file)
    train_path = base_path.parent / f"{base_path.stem}_train.jsonl"
    test_path = base_path.parent / f"{base_path.stem}_test.jsonl"
    
    with open(train_path, 'w', encoding='utf-8') as f:
        for ex in train_examples:
            f.write(json.dumps(ex, ensure_ascii=False) + '\n')
    
    with open(test_path, 'w', encoding='utf-8') as f:
        for ex in test_examples:
            f.write(json.dumps(ex, ensure_ascii=False) + '\n')
    
    print(f"✅ Split into train ({len(train_examples)}) and test ({len(test_examples)})")
    print(f"   Train: {train_path}")
    print(f"   Test: {test_path}")


def main():
    parser = argparse.ArgumentParser(description="Prepare training data for medical AI agents")
    parser.add_argument("--claims_csv", help="Path to historical claims CSV file")
    parser.add_argument("--documents_csv", help="Path to clinical documents CSV file")
    parser.add_argument("--output_dir", default="data/training", help="Output directory for training files")
    parser.add_argument("--split", action="store_true", help="Split into train/test sets")
    
    args = parser.parse_args()
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("MEDICAL AI TRAINING DATA PREPARATION")
    print("=" * 60)
    
    # Prepare Claims OCR datasets
    if args.claims_csv:
        print("\n📋 Processing claims data...")
        claims_df = pd.read_csv(args.claims_csv)
        
        print(f"   Loaded {len(claims_df)} claims from {args.claims_csv}")
        print(f"   Columns: {', '.join(claims_df.columns)}")
        
        # BiMediX dataset
        bimedix_path = output_dir / "bimedix_medical_analysis.jsonl"
        prepare_bimedix_dataset(claims_df, str(bimedix_path))
        
        # OpenInsurance dataset
        openins_path = output_dir / "openins_adjudication.jsonl"
        prepare_openinsurance_dataset(claims_df, str(openins_path))
        
        # Split datasets
        if args.split:
            print("\n🔀 Splitting datasets...")
            split_train_test(str(bimedix_path))
            split_train_test(str(openins_path))
    
    # Prepare AI Scribe dataset
    if args.documents_csv:
        print("\n📝 Processing clinical documents...")
        docs_df = pd.read_csv(args.documents_csv)
        
        print(f"   Loaded {len(docs_df)} documents from {args.documents_csv}")
        print(f"   Columns: {', '.join(docs_df.columns)}")
        
        scribe_path = output_dir / "scribe_clinical_docs.jsonl"
        prepare_scribe_dataset(docs_df, str(scribe_path))
        
        if args.split:
            print("\n🔀 Splitting dataset...")
            split_train_test(str(scribe_path))
    
    print("\n" + "=" * 60)
    print("✅ DATA PREPARATION COMPLETE!")
    print("=" * 60)
    print(f"\nTraining files saved to: {output_dir}")
    print("\nNext steps:")
    print("1. Review the generated .jsonl files")
    print("2. Run fine-tuning: python training/finetune_lora.py")
    print("3. Evaluate models: python training/evaluate.py")


if __name__ == "__main__":
    main()
