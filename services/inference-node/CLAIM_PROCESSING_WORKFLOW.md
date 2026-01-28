# Complete Claim Processing Workflow

## Overview

This document describes the end-to-end automated claim processing pipeline that takes a PDF claim document and produces a final verdict with approved amount.

## Workflow Steps

### 1. **Upload & OCR Extraction** 📄
- Accept PDF claim document via API
- Convert each page to image (200 DPI)
- Extract text using Tesseract OCR
- Handle OCR failures gracefully per page

**Output**: Full text extraction of all pages

---

### 2. **Page Summarization** 📝
- Create summary for each page including:
  - Character count
  - Word count
  - Preview (first 300 chars)

**Output**: Structured summaries of all pages

---

### 3. **Page Categorization** 🏷️
- Categorize each page into types:
  - `claim_form` - Claim history sheets, claim forms
  - `patient_info` - Patient demographics, policy details
  - `authorization` - Pre-authorization letters
  - `discharge_summary` - Medical discharge summaries
  - `billing` - Bill breakup, final bills
  - `lab_reports` - Laboratory test reports
  - `receipts` - Payment receipts, advances
  - `other` - Uncategorized documents

**Output**: Page numbers grouped by category

---

### 4. **Claim & Claimant Identification** 🔎
Extract key information using regex patterns:
- **Patient Name**: From patient info sections
- **Age**: Patient age in years
- **Hospital**: Hospital name and details
- **Diagnosis**: Primary diagnosis/condition
- **Claim Amount**: Total claimed amount
- **Admission Date**: Date of admission
- **Discharge Date**: Date of discharge
- **Policy Number**: Insurance policy number (10+ digits)
- **TPA**: Third-party administrator details

**Additional Extraction**:
- Billing line items from billing pages
- Item names and amounts
- Page references for each item

**Output**: Structured claim data dictionary

---

### 5. **Policy Coverage Verification** ✅
**Via Heritage Health TPA API**:

```python
heritage_client.verify_policy_coverage(
    policy_number=policy_number,
    patient_name=patient_name,
    patient_age=age
)
```

**Checks**:
- ✓ Policy exists and is ACTIVE
- ✓ Patient is covered member
- ✓ Coverage details (sum insured, balance, limits)
- ✓ Policy validity period
- ✓ Room rent limits
- ✓ Co-payment and deductible amounts

**If policy not found or inactive**: → **REJECT** claim immediately

**Output**: Coverage verification object with policy details

---

### 6. **Admissibility Check** ⚖️
**Rules Engine validates**:

#### Rule 1: Policy Status
- Policy must be **ACTIVE**
- Policy must not be expired or suspended

#### Rule 2: Sum Insured Balance
- Claim amount must not exceed balance sum insured
- Check: `claim_amount <= balance_sum_insured`

#### Rule 3: Policy Period
- Admission date must fall within policy period
- Check: `policy_start_date <= admission_date <= policy_end_date`

#### Rule 4: Pre-existing Conditions
- Check if diagnosis contains pre-existing keywords
- Verify waiting period compliance
- Keywords: diabetes, hypertension, cancer, kidney disease, etc.

#### Rule 5: Patient Identity
- Verify patient name matches policy member name
- Fuzzy matching or exact match depending on configuration

**If any rule fails**: → **REJECT** claim with specific reasons

**Output**: Admissibility status + reasons if rejected

---

### 7. **Payables Calculation** 💰
**Calculate approved amount after deductions**:

#### 7.1 Identify Non-Payable Items
Items NOT covered by insurance:
- Comfort items (diapers, toiletries, cosmetics)
- Personal items (toothbrush, soap, comb)
- Administrative (admission kits, medical records)
- Non-medical (attendant, phone, TV, WiFi)
- Supplements (unless prescribed)

**Action**: Deduct non-payable amounts

#### 7.2 Room Rent Excess
- Check daily room charge vs. policy limit
- Calculate excess per day
- Formula: `excess = (daily_charge - room_limit) × days`

**Example**:
```
Daily charge: ₹6,000
Policy limit: ₹5,000
Days: 3
Excess = (6,000 - 5,000) × 3 = ₹3,000
```

**Action**: Deduct room rent excess

#### 7.3 Apply Co-payment
- Co-payment is a percentage of eligible amount
- Formula: `co_payment = subtotal × (co_payment_% / 100)`

**Example**:
```
Subtotal: ₹100,000
Co-payment: 10%
Deduction = 100,000 × 0.10 = ₹10,000
```

**Action**: Deduct co-payment amount

#### 7.4 Apply Deductible
- Deductible is a fixed amount per claim
- Applied after all other deductions

**Formula**:
```
Approved Amount = Total Billed
                  - Non-Payable Items
                  - Room Rent Excess
                  - Co-payment
                  - Deductible
```

**Output**: Detailed payables breakdown

---

### 8. **Final Verdict** 🎯
**Generate decision based on all checks**:

#### If Policy Invalid:
```json
{
  "decision": "REJECTED",
  "approved_amount": 0,
  "status": "POLICY_INVALID",
  "reasons": ["Policy not found or inactive"]
}
```

#### If Not Admissible:
```json
{
  "decision": "REJECTED",
  "approved_amount": 0,
  "status": "NOT_ADMISSIBLE",
  "reasons": [
    "Claim amount exceeds balance sum insured",
    "Admission outside policy period"
  ]
}
```

#### If All Deductions Exceed Billed Amount:
```json
{
  "decision": "REJECTED",
  "approved_amount": 0,
  "status": "CLAIM_REJECTED",
  "reasons": ["All charges are non-payable"]
}
```

#### If Approved:
```json
{
  "decision": "APPROVED",
  "approved_amount": 350000.00,
  "billed_amount": 375000.00,
  "total_deductions": 25000.00,
  "status": "CLAIM_APPROVED",
  "payment_instruction": "Approve payment of ₹3,50,000.00",
  "deduction_breakdown": [
    {
      "type": "NON_PAYABLE",
      "amount": 5000,
      "description": "Non-covered items"
    },
    {
      "type": "ROOM_RENT_EXCESS",
      "amount": 10000,
      "description": "Room rent excess"
    },
    {
      "type": "CO_PAYMENT",
      "amount": 10000,
      "description": "10% co-payment"
    }
  ]
}
```

**Output**: Final verdict with decision and approved amount

---

## API Endpoints

### New Complete Workflow Endpoint

```
POST /api/claim/process-complete
```

**Request**:
```bash
curl -X POST \
  -F "file=@claim_document.pdf" \
  http://localhost:8000/api/claim/process-complete
```

**Response** (Success):
```json
{
  "success": true,
  "filename": "claim_12345.pdf",
  "total_pages": 27,
  "categories": {
    "claim_form": [1, 2, 3],
    "billing": [15, 16, 17],
    "discharge_summary": [8, 9]
  },
  "claim_data": {
    "patient_name": "RANGANAYAKI V",
    "age": "59",
    "hospital": "APOLLO HOSPITAL",
    "diagnosis": "Metastatic Breast Cancer",
    "claim_amount": "375000",
    "policy_number": "2809204492174700",
    "tpa": "HERITAGE HEALTH INSURANCE TPA PVT. LTD."
  },
  "coverage_verification": {
    "is_covered": true,
    "policy_status": "ACTIVE",
    "coverage_details": {
      "sum_insured": 500000,
      "balance_sum_insured": 350000,
      "room_rent_limit": 5000,
      "co_payment": 0,
      "deductible": 0
    }
  },
  "admissibility_check": {
    "is_admissible": true,
    "reasons": []
  },
  "payables_calculation": {
    "total_billed": 375000,
    "non_payable_amount": 5000,
    "room_rent_excess": 7000,
    "co_payment": 0,
    "deductible": 0,
    "total_deductions": 12000,
    "approved_amount": 363000
  },
  "final_verdict": {
    "decision": "APPROVED",
    "approved_amount": 363000,
    "billed_amount": 375000,
    "status": "CLAIM_APPROVED",
    "payment_instruction": "Approve payment of ₹3,63,000.00"
  },
  "processing_steps": [
    {"step": 1, "name": "OCR Extraction", "status": "COMPLETED"},
    {"step": 2, "name": "Page Summaries", "status": "COMPLETED"},
    {"step": 3, "name": "Page Categorization", "status": "COMPLETED"},
    {"step": 4, "name": "Claim Identification", "status": "COMPLETED"},
    {"step": 5, "name": "Policy Verification", "status": "COMPLETED"},
    {"step": 6, "name": "Admissibility Check", "status": "COMPLETED"},
    {"step": 7, "name": "Payables Calculation", "status": "COMPLETED"},
    {"step": 8, "name": "Final Verdict", "status": "COMPLETED"}
  ]
}
```

---

## Testing

### Test with Demo Script

```bash
cd /home/dgs/N3090/services/inference-node
python3 test_claim_workflow.py
```

### Test with cURL

```bash
curl -X POST \
  -F "file=@data/training/2ef67e09-51d4-49f0-9441-d27fa4508ada.pdf" \
  http://localhost:8000/api/claim/process-complete \
  | python3 -m json.tool
```

---

## Components

### 1. Heritage API Client
**File**: `app/services/heritage_api.py`
- Policy verification
- Coverage details retrieval
- Claim history lookup

### 2. Claim Processing Rules Engine
**File**: `app/services/claim_rules.py`
- Admissibility checks
- Non-payable item detection
- Payables calculation
- Final verdict generation

### 3. Claim Processing Route
**File**: `app/routes/claim_processing.py`
- Main workflow orchestration
- API endpoint handler

---

## Configuration

### Heritage API Credentials
```python
HERITAGE_API_URL = "https://api.heritagehealth.in"
HERITAGE_API_KEY = "your_api_key_here"
```

### Non-Payable Items Patterns
Edit in `app/services/claim_rules.py`:
```python
NON_PAYABLE_ITEMS = [
    r"diaper", r"toiletries",
    r"attendant", r"visitor"
]
```

### Room Rent Limits
```python
ROOM_RENT_LIMITS = {
    "SINGLE_PRIVATE": 5000,
    "TWIN_SHARING": 3000,
    "ICU": 8000
}
```

---

## Error Handling

### Scenario 1: Policy Not Found
```json
{
  "success": false,
  "final_verdict": {
    "decision": "REJECTED",
    "status": "POLICY_INVALID"
  }
}
```

### Scenario 2: OCR Failure
- Gracefully handle per-page failures
- Continue processing remaining pages
- Log warnings for failed pages

### Scenario 3: Heritage API Timeout
- Return policy verification error
- Suggest manual verification
- Log for retry

---

## Performance

### Metrics (27-page claim):
- OCR Extraction: ~2-3 minutes
- Policy Verification: ~1 second
- Rule Processing: <1 second
- **Total**: ~3-4 minutes

### Optimization:
- Parallel OCR processing (future)
- Cache policy verifications
- Batch billing item extraction

---

## Next Steps

1. ✅ Complete workflow implemented
2. ✅ Heritage API integration (mock)
3. ✅ Rules engine created
4. ✅ Payables calculation
5. 🔄 Frontend integration needed
6. 🔄 Real Heritage API credentials
7. 🔄 Advanced OCR (table extraction)
8. 🔄 ML-based item classification

---

## Support

For issues or questions:
- Check logs: `/var/log/inference-node/`
- API docs: `http://localhost:8000/docs`
- Test endpoint: `http://localhost:8000/api/claim/process-complete`
