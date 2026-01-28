# Insurance Policy Critical Checkpoints - Integration Guide

## Overview
This document maps all 73 critical checkpoints from `Insurance_Policy_Terms&Conditions_Checklist.docx` to the claim adjudication rules engine.

---

## 1. COVERAGE ELIGIBILITY (4 checkpoints)
**Status**: ✅ Integrated  
**Location**: `claim_rules.py::check_admissibility()`

| Checkpoint | Implementation | Validation |
|---|---|---|
| Family Definition | Member relationship validation | Coverage details → member_name matching |
| Max Entry Age | Age at enrollment check | claim_data['age'] vs policy enrollment date |
| Member eligibility | Policy active status | coverage_details['policy_status'] == 'ACTIVE' |
| Spouse/Children/Parents | Family composition verification | Heritage API response validation |

---

## 2. ROOM RENT LIMITS (4 checkpoints)
**Status**: ✅ Integrated  
**Location**: `claim_rules.py::calculate_payables()` with policy_rules overlay

| Checkpoint | YAML Configuration | Implementation |
|---|---|---|
| Room Rent Per Day | `limits.room_rent_limit_per_day` | Deduct excess above limit |
| ICU Rent Per Day | `limits.room_rent_limit_per_day['ICU']` | Apply ICU-specific limit |
| Proportionate Clause (Room) | Policy-specific overlay | Calculate shared occupancy deduction |
| Proportionate Clause (ICU) | Policy-specific overlay | Calculate ICU shared deduction |

**Example**:
```yaml
limits:
  room_rent_limit_per_day:
    GENERAL_WARD: 1500
    TWIN_SHARING: 3000
    SINGLE_PRIVATE: 5000
    ICU: 8000
```

---

## 3. WAITING PERIODS (8 checkpoints)
**Status**: ✅ Integrated  
**Location**: `claim_rules.py::check_admissibility()` and policy_rules

| Checkpoint | YAML Field | Logic |
|---|---|---|
| 30 days waiting period | `admissibility.pre_existing_waiting_days` | Check admission date ≥ policy_start + 30 days |
| First 30 Days Discount | `payables_rules.first_30_days_discount` | Apply premium reduction if within 30 days |
| 1 year waiting period | Disease-specific in exclusions | Apply if diagnosis in 1-year exclusion list |
| 2 year waiting period | `admissibility.pre_existing_waiting_years: 2` | Apply if diagnosis pre-existing < 2 years |
| 3 year waiting period | `admissibility.pre_existing_waiting_years: 3` | Apply for select conditions |
| 4 year waiting period | `admissibility.pre_existing_waiting_years: 4` | Apply for major pre-existing conditions |
| Specified disease/procedure | `exclusions.diseases` | Match diagnosis against exclusion list |
| Mid-term Addition | Policy metadata | Check family_member_addition_date |

---

## 4. PRE-EXISTING DISEASES (4 checkpoints)
**Status**: ✅ Integrated  
**Location**: `claim_rules.py::check_admissibility()` with policy overlay

| Checkpoint | Implementation | Validation |
|---|---|---|
| Pre-Existing Coverage | `policy_rules['exclusions']['diseases']` | Match claim diagnosis against exclusion list |
| PED Waiting Period | `admissibility.pre_existing_waiting_years` | Check if hospitalization after waiting period |
| Proof of Non-Disclosure | Backend validation | Cross-reference claim submission documents |
| Chronic Disease Mgmt | Policy-specific rules | Apply disease caps and frequency limits |

---

## 5. MATERNITY BENEFITS (7 checkpoints)
**Status**: ✅ Available for Policy-Specific YAML  
**Location**: Policy Rules YAML files

| Checkpoint | YAML Structure | Notes |
|---|---|---|
| Maternity Benefits | `admissibility.maternity_waiting_years` | Typical: 9 months to 2 years |
| Maternity Limits | `limits.maternity_benefit_cap` | e.g., ₹200,000 |
| Pre/Post Hospitalization | `admissibility.pre_hospitalization_days/post_hospitalization_days` | Typically 30/60 days |
| Pre/Post Natal Expenses | `limits.pre_post_natal_expenses` | Doctor visits, tests |
| New Born Baby Expenses | `limits.newborn_benefit_cap` | Delivery, pediatric care |
| Baby Covered from Day 1 | `admissibility.newborn_coverage_day` | Day 1 or Day 8 |
| Congenital Conditions | `admissibility.congenital_ailments_covered` | Internal/External flags |

---

## 6. SPECIAL CONDITIONS (7 checkpoints)
**Status**: ✅ Partially Integrated  
**Location**: Policy Rules YAML + rules engine

| Checkpoint | YAML Field | Current Status |
|---|---|---|
| Day Care Procedures | `admissibility.daycare_procedures_allowed` | ✅ Implemented |
| Cataract Surgery | `limits.sub_limits.cataract_per_eye` | ✅ Implemented (₹25,000 typical) |
| Internal Congenital | `admissibility.internal_congenital_covered` | ⏳ Need policy-level flag |
| External Congenital | `admissibility.external_congenital_covered` | ⏳ Need policy-level flag |
| Organ Donor Expenses | `limits.organ_donor_expenses_cap` | ⏳ To be added to policy YAML |
| Domiciliary Hospital | `admissibility.domiciliary_hospitalization` | ⏳ To be added to policy YAML |
| Package Treatments | `limits.package_treatment_caps` | ⏳ To be added to policy YAML |

---

## 7. TREATMENT TYPES (8 checkpoints)
**Status**: ⏳ Expandable  
**Location**: Policy Rules YAML (treatment-specific exclusions/limits)

| Checkpoint | YAML Field | Implementation Notes |
|---|---|---|
| Ayurvedic/AYUSH | `exclusions.treatment_types: ['ayurveda']` | Exclude if not covered |
| Modern Treatment | Default coverage | Include unless excluded |
| OPD (Outpatient) | `admissibility.opd_covered` | Usually excluded or sub-limited |
| IPD (Inpatient) | Default coverage | Primary coverage |
| Lasik Surgery | `limits.sub_limits.lasik_eye_surgery` | Typical cap: ₹50,000 per eye |
| Psychiatry Treatment | `admissibility.psychiatry_covered` | May have visit limits |
| Infertility Treatment | `admissibility.infertility_covered` | Usually excluded |
| Air Ambulance | `limits.sub_limits.air_ambulance` | Typical cap: ₹200,000 |

---

## 8. ANCILLARY COVERAGE (6 checkpoints)
**Status**: ⏳ Partially Integrated  
**Location**: Policy Rules YAML

| Checkpoint | YAML Field | Current Status |
|---|---|---|
| Ambulance Charges | `limits.sub_limits.ambulance_charges` | ✅ In YAML (₹2,000 typical) |
| Non-Medical Expenses | `limits.non_medical_expenses_cap` | ⏳ To be added |
| Cashless Facility | `admissibility.cashless_allowed` | ⏳ Flag to be added |
| PPN (Preferred Network) | `admissibility.ppn_network_list` | ⏳ Provider list to be added |
| Organ Donor Expenses | `limits.organ_donor_cap` | ⏳ To be added |
| Organ Receiver Expenses | `limits.organ_receiver_cap` | ⏳ To be added |

---

## 9. DEDUCTIBLES & CO-PAY (4 checkpoints)
**Status**: ✅ Integrated  
**Location**: `claim_rules.py::calculate_payables()` with policy overlay

| Checkpoint | YAML Field | Implementation |
|---|---|---|
| Per-Claim Deductible | `payables_rules.deductible_amount` | Applied on every claim |
| Aggregate Deductible | `payables_rules.aggregate_deductible_annual` | Yearly cap on deductibles |
| Co-Payment % | `payables_rules.co_payment_percent` | Percentage of eligible amount |
| Co-Payment Cap | `payables_rules.copay_ceiling_annual` | Maximum copay per year |

**Example**:
```yaml
payables_rules:
  co_payment_percent: 10
  deductible_amount: 500
  aggregate_deductible_annual: 5000
  copay_ceiling_annual: 50000
```

---

## 10. POLICY LIMITS (5 checkpoints)
**Status**: ✅ Core checks integrated  
**Location**: `claim_rules.py::check_admissibility()` and payables

| Checkpoint | Implementation | Validation |
|---|---|---|
| Sum Insured (SI) | `coverage_details.balance_sum_insured` | Claim amount ≤ remaining SI |
| Disease-wise Sub-limits | `limits.disease_caps` | Apply diagnosis-specific caps |
| Mid-Term SI Increase | Policy modification flag | Check if increase applied |
| Reload of SI | `payables_rules.si_reload_mechanism` | Restore used benefits if enabled |
| Continuity (Pink Slip) | `admissibility.job_loss_continuity_cover` | Job loss coverage flag |

---

## 11. EXCLUSIONS (7 checkpoints)
**Status**: ✅ Integrated  
**Location**: `claim_rules.py` and policy_rules['exclusions']

| Checkpoint | YAML Field | Implementation |
|---|---|---|
| 1st Year Exclusion | `admissibility.first_year_waiting_days: 30` | Standard 30-day waiting |
| Terrorism | `exclusions.items: ['terrorism', 'war', 'civil unrest']` | Exclude if listed |
| Consumable Charges | `NON_PAYABLE_ITEMS` regex patterns | Match non-reusable items |
| Dental Treatment | `exclusions.items: ['dental', 'orthodontic']` | Exclude routine dentistry |
| Surgery | `exclusions.items: ['cosmetic surgery', 'laser']` | Surgery-specific exclusions |
| Waived Suicide | `admissibility.suicide_coverage_after_years: 1` | Cover after 1-year waiting |
| Special Conditions | `exclusions.special` | Policy-specific exceptions |

---

## 12. CLAIMS PROCESS (5 checkpoints)
**Status**: ⏳ Partially Integrated  
**Location**: Backend validation + logging

| Checkpoint | Current Implementation | To-Do |
|---|---|---|
| Claim Intimation | Timestamp on file upload | Add 48-72 hour validation |
| Claim Submission | File upload completion | Validate mandatory documents |
| Hospitalization Requirement | Extracted from billing | Min stay hour check (24-72 hrs) |
| Consumable Charges | Non-payable item detection | Require itemized receipt |
| Supporting Documents | Category detection in OCR | Enforce document completeness |

---

## 13. ADDITIONS/MODIFICATIONS (4 checkpoints)
**Status**: ⏳ Requires Policy Enhancement  
**Location**: Policy metadata

| Checkpoint | YAML Structure | Notes |
|---|---|---|
| Add/Del Members | `policy_metadata.family_modifications` | Track add/delete dates |
| PPN Changes | `policy_metadata.network_changes` | Provider list versioning |
| Corporate Floater | `policy_type: 'corporate_floater'` | Special group policy rules |
| Mid-Term Changes | Policy amendment dates | Version control for modifications |

---

## Integration Checklist

### ✅ Complete (27 checkpoints)
- All 4 Coverage Eligibility checks
- All 4 Room Rent Limits checks
- All 8 Waiting Period checks
- All 4 Pre-Existing Disease checks
- All 4 Deductibles & Co-Pay checks
- All 4 Policy Limits checks
- All 7 Exclusion checks

### ⏳ Partial (32 checkpoints)
- 5/7 Special Conditions (need congenital, organ, domiciliary, package treatment flags)
- 7/8 Treatment Types (need policy-level flags for ayurveda, OPD, psychiatry, infertility)
- 3/6 Ancillary Coverage (need non-medical, cashless, organ flags)
- 5/5 Claims Process (need 48-72 hour intimation, hospitalization min-hour checks)

### ❌ Not Started (14 checkpoints)
- Maternity Benefits (7) - needs maternity-specific policy YAML
- Additions/Modifications (4) - needs policy metadata versioning
- Some ancillary services (3)

---

## Next Steps

1. **Enhance YAML Template**: Add missing fields for maternity, special conditions, treatment types
2. **Implement Claim Timeline Validation**: Add 48-72 hour intimation check
3. **Add Hospitalization Duration Check**: Minimum stay hour requirements per policy
4. **Expand Policy Masters**: Update IRDAI-scraped YAML files with complete field coverage
5. **Test Against Real Claims**: Validate all checkpoints with actual claim documents

---

**Last Updated**: January 9, 2026  
**Document Source**: Insurance_Policy_Terms&Conditions_Checklist.docx  
**Integration Status**: 37% Complete / 63% To-Do
