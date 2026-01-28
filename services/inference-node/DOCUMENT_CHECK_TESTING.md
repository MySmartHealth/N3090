# Document Completeness Feature - Testing Guide

## Quick Test Scenarios

### ✅ Scenario 1: Complete Claim (All Documents Present)

**Upload:** Claim PDF with all 7 document types

**Expected Results:**
- Completeness: 100%
- Status: ✅ Green
- Message: "All 7 documents present"
- Missing: None
- Workflow: Proceeds to admissibility without warnings

**Visual:**
```
✅ Document Completeness Check
Completeness: 100.0%
[████████████████████] 100%

All 7 documents present (All mandatory documents present)

Present Documents (7):
✅ DISCHARGE SUMMARY (Mandatory)
✅ HOSPITAL BILL (Mandatory)
✅ CLAIM FORM (Mandatory)
✅ PATIENT ID/INFORMATION (Mandatory)
📋 PRE-AUTHORIZATION LETTER (Optional)
📋 INVESTIGATION/LAB REPORTS (Optional)
📋 PAYMENT RECEIPTS (Optional)

Missing Documents: None
```

---

### ⚠️ Scenario 2: Missing Optional Documents Only

**Upload:** Claim PDF missing authorization and receipts (5/7 documents)

**Expected Results:**
- Completeness: 71.4%
- Status: ⚠️ Yellow/Red
- Message: "5 out of 7 documents present"
- Missing Mandatory: None
- Missing Optional: 2
- Workflow: Proceeds with warning logged

**Visual:**
```
⚠️ Document Completeness Check
Completeness: 71.4%
[████████████░░░░░░░░] 71%

5 out of 7 documents present (All mandatory documents present)

Present Documents (5):
✅ DISCHARGE SUMMARY (Mandatory)
✅ HOSPITAL BILL (Mandatory)
✅ CLAIM FORM (Mandatory)
✅ PATIENT ID/INFORMATION (Mandatory)
📋 INVESTIGATION/LAB REPORTS (Optional)

Missing Documents:
❌ Missing Optional:
  - AUTHORIZATION
  - RECEIPTS
```

---

### ❌ Scenario 3: Missing Mandatory Documents

**Upload:** Claim PDF missing discharge summary (3/7 documents)

**Expected Results:**
- Completeness: 42.8%
- Status: ❌ Red
- Message: "3 out of 7 documents present (Missing 1 mandatory document)"
- Missing Mandatory: discharge_summary
- Warning: "⚠️ Missing mandatory documents: Discharge Summary"
- Workflow: Continues but flagged for manual review

**Visual:**
```
❌ Document Completeness Check
Completeness: 42.8%
[████████░░░░░░░░░░░░] 43%

3 out of 7 documents present (Missing 1 mandatory document)

Present Documents (3):
✅ HOSPITAL BILL (Mandatory)
✅ CLAIM FORM (Mandatory)
✅ PATIENT ID/INFORMATION (Mandatory)

Missing Documents:
❌ Missing Mandatory:
  - DISCHARGE SUMMARY
  
❌ Missing Optional:
  - AUTHORIZATION
  - LAB REPORTS
  - RECEIPTS

⚠️ Missing mandatory documents: Discharge Summary
```

---

### 🔍 Scenario 4: Empty/No Categories Detected

**Upload:** PDF with no recognizable document types

**Expected Results:**
- Completeness: 0%
- Status: ❌ Red
- Message: "No documents found"
- Warning: "⚠️ No document categories detected in uploaded claim"
- Workflow: Proceeds but needs manual intervention

**Visual:**
```
❌ Document Completeness Check
Completeness: 0.0%
[░░░░░░░░░░░░░░░░░░░░] 0%

No documents found

Present Documents: None

Missing Documents:
❌ Missing Mandatory:
  - DISCHARGE SUMMARY
  - HOSPITAL BILL
  - CLAIM FORM
  - PATIENT ID/INFORMATION
  
❌ Missing Optional:
  - AUTHORIZATION
  - LAB REPORTS
  - RECEIPTS

⚠️ No document categories detected in uploaded claim
```

---

## API Testing

### Test 1: Complete Workflow Request

```bash
curl -X POST "http://localhost:8000/api/claim/process-complete" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@test_claim_complete.pdf"
```

**Expected Response (Partial):**
```json
{
  "success": true,
  "document_completeness": {
    "is_complete": true,
    "completeness_percentage": 100.0,
    "summary": "All 7 documents present (All mandatory documents present)",
    "present_documents": [
      "discharge_summary",
      "billing",
      "claim_form",
      "patient_info",
      "authorization",
      "lab_reports",
      "receipts"
    ],
    "mandatory_found": [
      "discharge_summary",
      "billing",
      "claim_form",
      "patient_info"
    ],
    "missing_mandatory_documents": [],
    "missing_optional_documents": [],
    "warning": null
  },
  "processing_steps": [
    {"step": 1, "name": "OCR Extraction", "status": "COMPLETED"},
    {"step": 2, "name": "Page Summaries", "status": "COMPLETED"},
    {"step": 3, "name": "Page Categorization", "status": "COMPLETED"},
    {"step": 4, "name": "Claim Identification", "status": "COMPLETED"},
    {"step": 5, "name": "Policy Verification", "status": "COMPLETED"},
    {"step": 6, "name": "Document Completeness", "status": "COMPLETED", "completeness": "100%"},
    {"step": 7, "name": "Admissibility Check", "status": "COMPLETED"},
    {"step": 8, "name": "Payables Calculation", "status": "COMPLETED"},
    {"step": 9, "name": "Final Verdict", "status": "COMPLETED"}
  ]
}
```

---

### Test 2: Incomplete Claim Request

```bash
curl -X POST "http://localhost:8000/api/claim/process-complete" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@test_claim_incomplete.pdf"
```

**Expected Response (Partial):**
```json
{
  "success": true,
  "document_completeness": {
    "is_complete": false,
    "completeness_percentage": 57.1,
    "summary": "4 out of 7 documents present (Missing 1 mandatory document)",
    "present_documents": [
      "billing",
      "claim_form",
      "patient_info",
      "lab_reports"
    ],
    "mandatory_found": [
      "billing",
      "claim_form",
      "patient_info"
    ],
    "missing_mandatory_documents": [
      "discharge_summary"
    ],
    "missing_optional_documents": [
      "authorization",
      "receipts"
    ],
    "warning": "⚠️ Missing mandatory documents: Discharge Summary"
  }
}
```

---

## Backend Logging

### Console Output for Complete Claim:
```
INFO: 📋 STEP 6: Checking document completeness...
INFO: ✓ Document Completeness: 100.0% - All 7 documents present (All mandatory documents present)
```

### Console Output for Incomplete Claim:
```
INFO: 📋 STEP 6: Checking document completeness...
INFO: ✓ Document Completeness: 71.4% - 5 out of 7 documents present (All mandatory documents present)
```

### Console Output for Missing Mandatory:
```
INFO: 📋 STEP 6: Checking document completeness...
INFO: ✓ Document Completeness: 42.8% - 3 out of 7 documents present (Missing 1 mandatory document)
WARNING: ⚠️ ⚠️ Missing mandatory documents: Discharge Summary
```

---

## Frontend Testing Checklist

### Visual Display Tests:
- [ ] Progress bar renders correctly
- [ ] Color changes based on percentage:
  - [ ] Green for 100%
  - [ ] Yellow for 75-99%
  - [ ] Red for <75%
- [ ] Present documents list displays properly
- [ ] Missing documents separated (mandatory vs optional)
- [ ] Mandatory/Optional labels visible
- [ ] Warning message shows when incomplete

### Interaction Tests:
- [ ] Panel appears after Step 5 (Policy Verification)
- [ ] Panel appears before Step 7 (Admissibility Check)
- [ ] Scrolling works for long document lists
- [ ] Responsive layout on different screen sizes

### Data Integrity Tests:
- [ ] All present documents listed accurately
- [ ] All missing documents identified correctly
- [ ] Percentage calculation matches expected value
- [ ] Step 6 shows in processing timeline

---

## Manual Testing Steps

### 1. Start Backend Service
```bash
cd /home/dgs/N3090/services/inference-node
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Open Frontend
```
http://localhost:8000/static/claim_processing_frontend.html
```

### 3. Upload Test PDF
- Click "Choose PDF File"
- Select a test claim PDF
- Wait for processing (45-60 seconds)

### 4. Verify Display Order:
1. ✅ File upload confirmation
2. ✅ OCR extraction complete
3. ✅ Page categories displayed
4. ✅ Claim data extracted
5. ✅ **Policy Verification panel**
6. ✅ **Document Completeness panel** ← NEW
7. ✅ **Admissibility Check panel**
8. ✅ **Payables Calculation panel**
9. ✅ **Final Verdict panel**
10. ✅ **Processing Steps timeline**

### 5. Check Console Logs:
```javascript
// Browser DevTools Console
console.log('Document Completeness:', result.document_completeness);
```

Expected output:
```javascript
{
  is_complete: true,
  completeness_percentage: 100,
  summary: "All 7 documents present",
  present_documents: [...],
  missing_mandatory_documents: [],
  missing_optional_documents: []
}
```

---

## Automated Testing (Future)

### Unit Tests (claim_rules.py):
```python
def test_document_completeness_all_present():
    """Test with all documents present"""
    rules = ClaimProcessingRules()
    categories = {
        'discharge_summary': [1],
        'billing': [2],
        'claim_form': [3],
        'patient_info': [4],
        'authorization': [5],
        'lab_reports': [6],
        'receipts': [7]
    }
    
    result = rules.check_document_completeness(categories)
    
    assert result['is_complete'] == True
    assert result['completeness_percentage'] == 100.0
    assert len(result['missing_mandatory_documents']) == 0
    assert len(result['missing_optional_documents']) == 0

def test_document_completeness_missing_mandatory():
    """Test with missing mandatory documents"""
    rules = ClaimProcessingRules()
    categories = {
        'billing': [1],
        'claim_form': [2]
    }
    
    result = rules.check_document_completeness(categories)
    
    assert result['is_complete'] == False
    assert 'discharge_summary' in result['missing_mandatory_documents']
    assert 'patient_info' in result['missing_mandatory_documents']
```

### Integration Tests (claim_processing.py):
```python
async def test_complete_workflow_with_documents():
    """Test complete workflow includes document check"""
    # Upload test PDF
    # Verify response has document_completeness field
    # Verify processing_steps includes step 6
```

---

## Troubleshooting

### Issue 1: Document completeness not showing
**Solution:** Check browser console for errors, verify API response contains `document_completeness` field

### Issue 2: Wrong documents detected
**Solution:** Verify Step 3 (Page Categorization) results, check OCR quality

### Issue 3: Percentage calculation incorrect
**Solution:** Review MANDATORY_DOCUMENTS and OPTIONAL_DOCUMENTS definitions in claim_rules.py

### Issue 4: Frontend display not rendering
**Solution:** 
- Clear browser cache
- Check displayDocumentCompleteness() function exists
- Verify function call in processClaim()

---

## Test Data Requirements

### Minimal Test PDF (4 pages - all mandatory):
1. Page 1: Discharge Summary
2. Page 2: Hospital Bill
3. Page 3: Claim Form
4. Page 4: Patient ID Card

### Complete Test PDF (7 pages - all docs):
1. Page 1: Discharge Summary
2. Page 2-3: Hospital Bill (2 pages)
3. Page 4: Claim Form
4. Page 5: Patient ID Card
5. Page 6: Pre-authorization Letter
6. Page 7-8: Lab Reports (2 pages)
7. Page 9: Payment Receipts

### Incomplete Test PDF (2 pages - missing mandatory):
1. Page 1: Hospital Bill
2. Page 2: Claim Form

---

## Success Criteria

✅ **Backend Integration:**
- [ ] Step 6 executes between policy verification and admissibility
- [ ] Response includes document_completeness object
- [ ] Logging shows completeness percentage
- [ ] Warning logged for missing mandatory documents
- [ ] Workflow continues regardless of completeness

✅ **Frontend Display:**
- [ ] Document completeness panel renders correctly
- [ ] Progress bar shows accurate percentage
- [ ] Present/missing documents listed accurately
- [ ] Color coding matches completeness level
- [ ] Warning message displays when applicable

✅ **End-to-End:**
- [ ] Complete workflow executes in correct order
- [ ] All 9 steps complete successfully
- [ ] Processing timeline shows step 6
- [ ] Final verdict generates properly

---

**Testing Status:** Ready for manual and automated testing

**Next Steps:** 
1. Upload test PDFs with varying document combinations
2. Verify display accuracy
3. Test edge cases (empty PDFs, single page, 100+ pages)
4. Performance test with large files

---

**Last Updated:** 2024 - Testing Guide Complete
