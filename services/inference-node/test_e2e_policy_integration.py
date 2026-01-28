#!/usr/bin/env python3
"""
End-to-end test for complete claim processing with policy rule overlays.
Tests:
  1. Insurer/product inference from claim text
  2. YAML policy rule loading
  3. Rule overlay on admissibility and payables
  4. Final verdict calculation
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.services.claim_rules import ClaimProcessingRules
from app.services.policy_rules_loader import load_policy_rules, load_all_policy_files
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_policy_loading():
    """Test 1: Verify policy masters load correctly"""
    logger.info("\n=== TEST 1: Policy Masters Loading ===")
    
    all_policies = load_all_policy_files()
    logger.info(f"✓ Loaded {len(all_policies)} policy master files")
    
    # Check specific policies
    oriental = load_policy_rules("Oriental Insurance", "Happy Family Floater 2021")
    assert oriental, "Failed to load Oriental Insurance policy"
    assert oriental.get("company") == "Oriental Insurance"
    assert "admissibility" in oriental
    assert "exclusions" in oriental
    assert "limits" in oriental
    assert "payables_rules" in oriental
    logger.info("✓ Oriental Insurance Happy Family Floater 2021 structure valid")
    
    national = load_policy_rules("National Insurance", "Parivar Mediclaim Policy")
    assert national, "Failed to load National Insurance policy"
    logger.info("✓ National Insurance Parivar Mediclaim structure valid")
    
    return True


def test_insurer_detection():
    """Test 2: Verify insurer/product detection from text"""
    logger.info("\n=== TEST 2: Insurer/Product Detection ===")
    
    # Test cases with different claim texts
    test_cases = [
        {
            "text": "Oriental Insurance Happy Family Floater 2021 Policy No. 123456789",
            "expected_company": "Oriental Insurance",
            "expected_product": "Happy Family Floater 2021"
        },
        {
            "text": "National Insurance Parivar Mediclaim Policy coverage",
            "expected_company": "National Insurance",
            "expected_product": "Parivar Mediclaim Policy"
        },
        {
            "text": "HDFC ERGO Health Insurance claim form",
            "expected_company": "HDFC ERGO General Insurance Company Limited.",
            "expected_product": None
        },
        {
            "text": "Star Health and Allied Insurance Ltd coverage",
            "expected_company": "Star Health And Allied Insurance Co. Ltd",
            "expected_product": None
        }
    ]
    
    for i, case in enumerate(test_cases):
        text = case["text"].lower()
        detected_company = None
        detected_product = None
        
        if "oriental" in text and "insurance" in text:
            detected_company = "Oriental Insurance"
            if "happy family floater" in text or "hff" in text:
                detected_product = "Happy Family Floater 2021"
        elif "national insurance" in text:
            detected_company = "National Insurance"
            if "parivar mediclaim" in text or "parivar" in text:
                detected_product = "Parivar Mediclaim Policy"
        elif "hdfc" in text or "hdfc ergo" in text:
            detected_company = "HDFC ERGO General Insurance Company Limited."
        elif "star health" in text:
            detected_company = "Star Health And Allied Insurance Co. Ltd"
        
        assert detected_company == case["expected_company"], \
            f"Case {i}: Expected company={case['expected_company']}, got {detected_company}"
        logger.info(f"✓ Case {i+1}: Detected {detected_company} / {detected_product}")
    
    return True


def test_policy_rule_overlay():
    """Test 3: Verify policy rules overlay in admissibility and payables"""
    logger.info("\n=== TEST 3: Policy Rule Overlay Application ===")
    
    # Create a rules engine with Oriental Insurance policy
    rules_engine = ClaimProcessingRules(
        company="Oriental Insurance",
        product="Happy Family Floater 2021"
    )
    
    assert rules_engine.policy_rules, "Failed to load policy rules"
    logger.info("✓ Policy rules loaded for Oriental Insurance")
    
    # Verify exclusions are applied
    exclusions = rules_engine.policy_rules.get("exclusions", {})
    assert "cosmetic surgery" in exclusions.get("diseases", [])
    logger.info("✓ Product exclusions (diseases) loaded")
    
    # Verify room rent limits are available
    limits = rules_engine.policy_rules.get("limits", {})
    room_limits = limits.get("room_rent_limit_per_day", {})
    assert room_limits.get("SINGLE_PRIVATE") == 5000
    assert room_limits.get("ICU") == 8000
    logger.info(f"✓ Room rent limits loaded: {room_limits}")
    
    # Verify payables rules
    payables = rules_engine.policy_rules.get("payables_rules", {})
    assert "co_payment_percent" in payables
    assert "deductible_amount" in payables
    logger.info(f"✓ Payables rules loaded: co-payment={payables.get('co_payment_percent')}%, deductible=₹{payables.get('deductible_amount')}")
    
    return True


def test_admissibility_with_policy():
    """Test 4: Admissibility check with policy-specific rules"""
    logger.info("\n=== TEST 4: Admissibility Check with Policy Rules ===")
    
    rules_engine = ClaimProcessingRules(
        company="Oriental Insurance",
        product="Happy Family Floater 2021"
    )
    
    # Test case 1: Valid claim
    claim_data = {
        "patient_name": "John Doe",
        "age": "45",
        "diagnosis": "Type 2 Diabetes with complications",
        "claim_amount": "50000",
        "admission_date": "01-01-2024",
        "discharge_date": "05-01-2024",
        "policy_number": "ORI123456789",
        "hospital": "Apollo Hospital"
    }
    
    coverage = {
        "is_covered": True,
        "policy_status": "ACTIVE",
        "coverage_details": {
            "member_name": "John Doe",
            "balance_sum_insured": 500000,
            "policy_start_date": "01-01-2023",
            "policy_end_date": "31-12-2024",
            "room_rent_limit": 5000,
            "co_payment": 0,
            "deductible": 0,
            "pre_existing_covered": True
        }
    }
    
    is_admissible, reasons = rules_engine.check_admissibility(claim_data, coverage)
    logger.info(f"✓ Valid claim: Admissible={is_admissible}, Reasons={reasons}")
    
    # Test case 2: Excluded diagnosis
    claim_data_excluded = claim_data.copy()
    claim_data_excluded["diagnosis"] = "Cosmetic surgery for facial reconstruction"
    
    is_admissible_exc, reasons_exc = rules_engine.check_admissibility(claim_data_excluded, coverage)
    assert not is_admissible_exc, "Cosmetic surgery should be excluded under Oriental policy"
    assert any("excluded" in r.lower() for r in reasons_exc), "Should mention exclusion"
    logger.info(f"✓ Excluded diagnosis: Admissible={is_admissible_exc}, Reasons={reasons_exc}")
    
    return True


def test_payables_calculation():
    """Test 5: Payables calculation with policy overlays"""
    logger.info("\n=== TEST 5: Payables Calculation with Policy Overlays ===")
    
    rules_engine = ClaimProcessingRules(
        company="Oriental Insurance",
        product="Happy Family Floater 2021"
    )
    
    billing_items = [
        {"name": "Room rent (Single Private)", "amount": 6000},  # Exceeds limit
        {"name": "Consultation - Physician", "amount": 5000},
        {"name": "Lab tests (ECG, Blood work)", "amount": 3000},
        {"name": "Medications", "amount": 8000},
        {"name": "Diapers (non-payable)", "amount": 1500},  # Should be excluded
        {"name": "Surgical procedure", "amount": 25000},
    ]
    
    coverage = {
        "coverage_details": {
            "room_rent_limit": 5000,
            "co_payment": 0,
            "deductible": 500,  # Will be overridden by policy rules
        }
    }
    
    room_details = {
        "type": "SINGLE_PRIVATE",
        "daily_charge": 6000,
        "days": 3
    }
    
    payables = rules_engine.calculate_payables(billing_items, coverage, room_details)
    
    logger.info(f"  Total Billed: ₹{payables['total_billed']:,.2f}")
    logger.info(f"  Non-payable Items: ₹{payables['non_payable_amount']:,.2f}")
    logger.info(f"  Room Rent Excess: ₹{payables['room_rent_excess']:,.2f}")
    logger.info(f"  Co-payment: ₹{payables['co_payment']:,.2f}")
    logger.info(f"  Deductible: ₹{payables['deductible']:,.2f}")
    logger.info(f"  Final Payable: ₹{payables['approved_amount']:,.2f}")
    
    # Verify deductions
    assert payables['non_payable_amount'] == 1500, "Diapers should be non-payable"
    assert payables['room_rent_excess'] > 0, "Room rent should have excess"
    
    logger.info("✓ Payables calculation applied policy overlays correctly")
    
    return True


def test_final_verdict():
    """Test 6: Final verdict with all adjustments"""
    logger.info("\n=== TEST 6: Final Verdict Generation ===")
    
    rules_engine = ClaimProcessingRules(
        company="Oriental Insurance",
        product="Happy Family Floater 2021"
    )
    
    verdict = rules_engine.get_final_verdict(
        is_admissible=True,
        admissibility_reasons=[],
        payables={
            "total_billed": 47500,
            "non_payable_amount": 1500,
            "room_rent_excess": 3000,
            "co_payment": 0,
            "deductible": 0,
            "total_deductions": 4500,
            "approved_amount": 43000,
            "non_payable_items": [],
            "deduction_breakdown": []
        }
    )
    
    logger.info(f"  Decision: {verdict['decision']}")
    logger.info(f"  Approved Amount: ₹{verdict.get('approved_amount', 0):,.2f}")
    logger.info(f"  Rejection Reasons: {verdict.get('rejection_reasons', [])}")
    
    assert verdict['decision'] == "APPROVED", "Claim should be approved"
    assert verdict['approved_amount'] == 43000, "Approved amount should match payables"
    
    logger.info("✓ Final verdict generated correctly")
    
    return True


def main():
    """Run all tests"""
    logger.info("\n" + "="*60)
    logger.info("COMPREHENSIVE E2E POLICY INTEGRATION TEST SUITE")
    logger.info("="*60)
    
    tests = [
        test_policy_loading,
        test_insurer_detection,
        test_policy_rule_overlay,
        test_admissibility_with_policy,
        test_payables_calculation,
        test_final_verdict,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
        except AssertionError as e:
            logger.error(f"✗ FAILED: {str(e)}")
            failed += 1
        except Exception as e:
            logger.error(f"✗ ERROR: {str(e)}")
            failed += 1
    
    logger.info("\n" + "="*60)
    logger.info(f"TEST SUMMARY: {passed} PASSED, {failed} FAILED")
    logger.info("="*60 + "\n")
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
