"""
Claim Processing Rules Engine
Defines rules for admissibility, denial criteria, and payables calculation
"""
import re
import logging
from typing import Dict, List, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

from .policy_rules_loader import load_policy_rules


class ClaimProcessingRules:
    """Rule engine for claim adjudication and payables calculation"""
    
    # Mandatory documents checklist - ALL 7 documents are required
    MANDATORY_DOCUMENTS = {
        'discharge_summary': {'label': 'Discharge Summary', 'mandatory': True},
        'billing': {'label': 'Hospital Bill', 'mandatory': True},
        'claim_form': {'label': 'Claim Form', 'mandatory': True},
        'patient_info': {'label': 'Patient ID/Information', 'mandatory': True},
        'authorization': {'label': 'Pre-authorization Letter', 'mandatory': True},
        'lab_reports': {'label': 'Investigation/Lab Reports', 'mandatory': True},
        'receipts': {'label': 'Payment Receipts', 'mandatory': True},
    }
    
    # Optional documents (none - all documents are mandatory)
    OPTIONAL_DOCUMENTS = {}
    
    # Non-payable items (items not covered by insurance)
    NON_PAYABLE_ITEMS = [
        # Comfort items
        r"diaper", r"sanitary", r"baby food", r"toiletries", r"cosmetic",
        # Personal items
        r"tooth\s*brush", r"tooth\s*paste", r"soap", r"shampoo", r"comb",
        # Administrative
        r"admission\s*kit", r"registration", r"medical\s*records",
        # Non-medical
        r"attendant", r"visitor", r"guest", r"phone", r"television", r"wifi",
        # Supplements (unless prescribed)
        r"vitamin(?!.*prescribed)", r"protein\s*powder", r"health\s*drink",
    ]
    
    # Room rent limits (per day)
    ROOM_RENT_LIMITS = {
        "SINGLE_PRIVATE": 5000,
        "TWIN_SHARING": 3000,
        "GENERAL_WARD": 1500,
        "ICU": 8000,
        "ICCU": 7000
    }
    
    def __init__(self, company: str = None, product: str = None):
        self.denial_reasons = []
        self.warnings = []
        self.deductions = []
        # Load product-specific policy rules if available
        self.policy_rules = load_policy_rules(company, product)
    
    def check_document_completeness(self, categories: Dict) -> Dict:
        """
        Check if all mandatory documents are present based on page categorization
        
        Args:
            categories: Dict of page categories with page numbers
            
        Returns:
            Dict with document completeness status
        """
        present_docs = []
        missing_mandatory = []
        missing_optional = []
        
        # Check mandatory documents
        for doc_type, doc_info in self.MANDATORY_DOCUMENTS.items():
            pages = categories.get(doc_type, [])
            if pages and len(pages) > 0:
                present_docs.append({
                    'type': doc_type,
                    'label': doc_info['label'],
                    'mandatory': True,
                    'pages': len(pages),
                    'status': 'PRESENT'
                })
            else:
                missing_mandatory.append({
                    'type': doc_type,
                    'label': doc_info['label'],
                    'mandatory': True,
                    'status': 'MISSING'
                })
        
        # Check optional documents
        for doc_type, doc_info in self.OPTIONAL_DOCUMENTS.items():
            pages = categories.get(doc_type, [])
            if pages and len(pages) > 0:
                present_docs.append({
                    'type': doc_type,
                    'label': doc_info['label'],
                    'mandatory': False,
                    'pages': len(pages),
                    'status': 'PRESENT'
                })
            else:
                missing_optional.append({
                    'type': doc_type,
                    'label': doc_info['label'],
                    'mandatory': False,
                    'status': 'MISSING'
                })
        
        # Calculate completeness
        total_mandatory = len(self.MANDATORY_DOCUMENTS)
        present_mandatory = total_mandatory - len(missing_mandatory)
        completeness_percentage = (present_mandatory / total_mandatory * 100) if total_mandatory > 0 else 0
        
        is_complete = len(missing_mandatory) == 0
        
        result = {
            'is_complete': is_complete,
            'completeness_percentage': completeness_percentage,
            'total_mandatory': total_mandatory,
            'present_mandatory': present_mandatory,
            'missing_mandatory_count': len(missing_mandatory),
            'present_documents': present_docs,
            'missing_mandatory_documents': missing_mandatory,
            'missing_optional_documents': missing_optional,
            'summary': f"{present_mandatory}/{total_mandatory} mandatory documents present"
        }
        
        if not is_complete:
            result['warning'] = f"Missing {len(missing_mandatory)} mandatory document(s)"
            self.warnings.append(result['warning'])
        
        logger.info(f"Document completeness: {completeness_percentage:.1f}% ({result['summary']})")
        
        return result
    
    def check_admissibility(self, claim_data: Dict, coverage_details: Dict) -> Tuple[bool, List[str]]:
        """
        Check if claim is admissible
        
        Returns:
            Tuple of (is_admissible, list of reasons)
        """
        reasons = []
        
        # Check 1: Policy must be active
        if coverage_details.get("policy_status") != "ACTIVE":
            reasons.append(f"Policy status is {coverage_details.get('policy_status')}, not ACTIVE")
        
        # Check 2: Sufficient balance sum insured
        claim_amount = self._extract_amount(claim_data.get("claim_amount", "0"))
        balance_si = coverage_details.get("coverage_details", {}).get("balance_sum_insured", 0)
        
        if claim_amount > balance_si:
            reasons.append(f"Claim amount (₹{claim_amount:,.2f}) exceeds balance sum insured (₹{balance_si:,.2f})")
        
        # Check 3: Dates must be within policy period
        admission_date = claim_data.get("admission_date")
        if admission_date:
            policy_start = coverage_details.get("coverage_details", {}).get("policy_start_date")
            policy_end = coverage_details.get("coverage_details", {}).get("policy_end_date")
            
            if policy_start and policy_end:
                # Simple date comparison (you may want to use proper date parsing)
                if admission_date < policy_start or admission_date > policy_end:
                    reasons.append(f"Admission date {admission_date} is outside policy period ({policy_start} to {policy_end})")
        
        # Check 4: Pre-existing disease waiting period
        diagnosis = claim_data.get("diagnosis", "").lower()
        pre_existing_keywords = ["diabetes", "hypertension", "heart disease", "cancer", "kidney disease"]
        
        if any(keyword in diagnosis for keyword in pre_existing_keywords):
            if not coverage_details.get("coverage_details", {}).get("pre_existing_covered", False):
                reasons.append("Pre-existing disease not covered under policy")
                self.warnings.append("Pre-existing condition detected - verify waiting period")
        
        # Apply policy master exclusions (disease-level)
        if self.policy_rules:
            excluded = [d.lower() for d in self.policy_rules.get("exclusions", {}).get("diseases", [])]
            for ex in excluded:
                if ex and ex in diagnosis:
                    reasons.append(f"Excluded under product policy: {ex}")
                    break

            # Minimum hospitalization hours check
            adm = claim_data.get("admission_date")
            dis = claim_data.get("discharge_date")
            try:
                if adm and dis:
                    # Expect dd-mm-yyyy or dd/mm/yyyy
                    def _parse(d):
                        return datetime.strptime(d.replace('/', '-'), "%d-%m-%Y")
                    stay_hours = abs((_parse(dis) - _parse(adm)).days) * 24
                    min_hours = self.policy_rules.get("admissibility", {}).get("min_hospitalization_hours", 0)
                    if min_hours and stay_hours < min_hours:
                        reasons.append(f"Hospitalization less than required {min_hours} hours")
            except Exception:
                # Ignore date parse errors, rely on other checks
                pass

        # Check 5: Verify patient identity matches policy
        claim_patient = claim_data.get("patient_name", "").lower().strip()
        policy_member = coverage_details.get("coverage_details", {}).get("member_name", "").lower().strip()
        
        # Simple name matching (in production, use fuzzy matching)
        if claim_patient and policy_member:
            if claim_patient not in policy_member and policy_member not in claim_patient:
                self.warnings.append(f"Patient name mismatch: Claim={claim_patient}, Policy={policy_member}")
        
        is_admissible = len(reasons) == 0
        return is_admissible, reasons
    
    def calculate_payables(
        self, 
        billing_items: List[Dict],
        coverage_details: Dict,
        room_details: Dict = None
    ) -> Dict:
        """
        Calculate payable amount after applying deductions
        
        Args:
            billing_items: List of billing line items
            coverage_details: Coverage/policy details
            room_details: Room type and charges
            
        Returns:
            Dict with payable calculation breakdown
        """
        total_billed = 0
        total_non_payable = 0
        total_room_excess = 0
        total_co_payment = 0
        total_deductible = 0
        
        payable_items = []
        non_payable_items = []
        
        # Process each billing item
        for item in billing_items:
            item_name = item.get("name", "").lower()
            item_amount = item.get("amount", 0)
            total_billed += item_amount
            
            # Check if item is non-payable
            is_non_payable = False
            for pattern in self.NON_PAYABLE_ITEMS:
                if re.search(pattern, item_name, re.IGNORECASE):
                    is_non_payable = True
                    non_payable_items.append({
                        "name": item.get("name"),
                        "amount": item_amount,
                        "reason": f"Non-covered item: matches pattern '{pattern}'"
                    })
                    total_non_payable += item_amount
                    break
            
            if not is_non_payable:
                payable_items.append(item)
        
        # Calculate room rent excess
        if room_details:
            room_type = room_details.get("type", "").upper()
            daily_charge = room_details.get("daily_charge", 0)
            days = room_details.get("days", 0)
            
            # Overlay room rent limit from policy rules if available
            room_limit = coverage_details.get("coverage_details", {}).get("room_rent_limit", 5000)
            if self.policy_rules:
                per_day_limits = self.policy_rules.get("limits", {}).get("room_rent_limit_per_day", {})
                if room_type in per_day_limits:
                    room_limit = per_day_limits.get(room_type, room_limit)
            
            if daily_charge > room_limit:
                excess_per_day = daily_charge - room_limit
                total_room_excess = excess_per_day * days
                self.deductions.append({
                    "type": "ROOM_RENT_EXCESS",
                    "amount": total_room_excess,
                    "description": f"Room rent excess: ₹{daily_charge}/day exceeds limit ₹{room_limit}/day for {days} days"
                })
        
        # Calculate subtotal after non-payables and room excess
        subtotal = total_billed - total_non_payable - total_room_excess
        
        # Apply co-payment (overlay from policy rules if provided)
        co_payment_pct = coverage_details.get("coverage_details", {}).get("co_payment", 0)
        if self.policy_rules:
            pr_cp = self.policy_rules.get("payables_rules", {}).get("co_payment_percent")
            if isinstance(pr_cp, (int, float)):
                co_payment_pct = pr_cp
        if co_payment_pct > 0:
            total_co_payment = subtotal * (co_payment_pct / 100)
            self.deductions.append({
                "type": "CO_PAYMENT",
                "amount": total_co_payment,
                "description": f"Co-payment: {co_payment_pct}% of eligible amount"
            })
        
        # Apply deductible (overlay from policy rules if provided)
        deductible = coverage_details.get("coverage_details", {}).get("deductible", 0)
        if self.policy_rules:
            pr_dd = self.policy_rules.get("payables_rules", {}).get("deductible_amount")
            if isinstance(pr_dd, (int, float)):
                deductible = pr_dd
        if deductible > 0:
            total_deductible = deductible
            self.deductions.append({
                "type": "DEDUCTIBLE",
                "amount": total_deductible,
                "description": f"Policy deductible: ₹{deductible:,.2f}"
            })
        
        # Final payable amount
        final_payable = subtotal - total_co_payment - total_deductible
        final_payable = max(0, final_payable)  # Cannot be negative
        
        return {
            "total_billed": total_billed,
            "non_payable_amount": total_non_payable,
            "non_payable_items": non_payable_items,
            "room_rent_excess": total_room_excess,
            "co_payment": total_co_payment,
            "deductible": total_deductible,
            "total_deductions": total_non_payable + total_room_excess + total_co_payment + total_deductible,
            "approved_amount": final_payable,
            "payable_items": payable_items,
            "deduction_breakdown": self.deductions
        }
    
    def _extract_amount(self, amount_str: str) -> float:
        """Extract numeric amount from string"""
        if isinstance(amount_str, (int, float)):
            return float(amount_str)
        
        # Remove currency symbols and commas
        cleaned = re.sub(r'[₹$,\s]', '', str(amount_str))
        try:
            return float(cleaned)
        except:
            return 0.0
    
    def get_final_verdict(
        self, 
        is_admissible: bool,
        admissibility_reasons: List[str],
        payables: Dict
    ) -> Dict:
        """
        Generate final claim verdict
        
        Returns:
            Dict with decision, amount, and reasoning
        """
        if not is_admissible:
            return {
                "decision": "REJECTED",
                "approved_amount": 0,
                "reasons": admissibility_reasons,
                "status": "CLAIM_REJECTED"
            }
        
        # Check if any deductions bring amount to zero
        if payables["approved_amount"] <= 0:
            return {
                "decision": "REJECTED",
                "approved_amount": 0,
                "reasons": ["All charges are non-payable or deductions exceed billed amount"],
                "billed_amount": payables["total_billed"],
                "deductions": payables["total_deductions"],
                "status": "CLAIM_REJECTED"
            }
        
        # Claim is approved with payable amount
        return {
            "decision": "APPROVED",
            "approved_amount": payables["approved_amount"],
            "billed_amount": payables["total_billed"],
            "total_deductions": payables["total_deductions"],
            "deduction_breakdown": payables["deduction_breakdown"],
            "non_payable_items": payables.get("non_payable_items", []),
            "status": "CLAIM_APPROVED",
            "payment_instruction": f"Approve payment of ₹{payables['approved_amount']:,.2f}"
        }
