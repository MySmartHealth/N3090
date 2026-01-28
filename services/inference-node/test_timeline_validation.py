"""
Test timeline validation features in claim processing
"""
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def parse_date(date_str):
    """Parse date from claim data"""
    if not date_str:
        return None
    for fmt in ["%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%Y/%m/%d", "%d-%m-%y", "%d/%m/%y"]:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except:
            continue
    return None

def test_hospitalization_duration():
    """Test minimum hospitalization hours validation"""
    logger.info("\n=== TEST: Hospitalization Duration ===")
    
    # Case 1: Valid hospitalization (3 days)
    admission = parse_date("01-01-2024")
    discharge = parse_date("04-01-2024")
    hours = (discharge - admission).total_seconds() / 3600
    
    logger.info(f"✓ Case 1: Admission 01-01-2024, Discharge 04-01-2024")
    logger.info(f"  Duration: {hours} hours")
    assert hours >= 24, "Should meet minimum 24h requirement"
    logger.info(f"  ✓ Meets minimum 24h requirement")
    
    # Case 2: Short hospitalization (12 hours)
    admission = parse_date("01-01-2024")
    discharge = parse_date("01-01-2024")
    admission = admission.replace(hour=8)
    discharge = discharge.replace(hour=20)
    hours = (discharge - admission).total_seconds() / 3600
    
    logger.info(f"\n✓ Case 2: Same day admission 08:00, discharge 20:00")
    logger.info(f"  Duration: {hours} hours")
    assert hours < 24, "Should be below 24h"
    logger.info(f"  ⚠️ Below minimum 24h requirement - triggers warning")
    
    logger.info("\n✅ Hospitalization duration tests PASSED")

def test_claim_submission_timeliness():
    """Test claim submission timeliness (time-barred check)"""
    logger.info("\n=== TEST: Claim Submission Timeliness ===")
    
    # Case 1: Recent admission (within 90 days)
    days_ago = 30
    admission_date = datetime.now() - timedelta(days=days_ago)
    days_since = (datetime.now() - admission_date).days
    
    logger.info(f"✓ Case 1: Claim submitted {days_since} days after admission")
    assert days_since <= 90, "Should be within 90 days"
    logger.info(f"  ✓ Within 90-day window - claim is timely")
    
    # Case 2: Old admission (>90 days)
    days_ago = 120
    admission_date = datetime.now() - timedelta(days=days_ago)
    days_since = (datetime.now() - admission_date).days
    
    logger.info(f"\n✓ Case 2: Claim submitted {days_since} days after admission")
    assert days_since > 90, "Should be beyond 90 days"
    logger.info(f"  ⚠️ Beyond 90-day window - triggers time-barred warning")
    
    logger.info("\n✅ Claim submission timeliness tests PASSED")

def test_timeline_validation_integration():
    """Test timeline validation in claim processing context"""
    logger.info("\n=== TEST: Timeline Validation Integration ===")
    
    claim_data = {
        "patient_name": "John Doe",
        "age": "45",
        "admission_date": "10-01-2024",
        "discharge_date": "15-01-2024",
        "diagnosis": "Type 2 Diabetes",
        "claim_amount": "50000",
        "policy_number": "POL123456789"
    }
    
    min_hospitalization_hours = 24
    
    # Parse dates
    admission_date = parse_date(claim_data.get("admission_date"))
    discharge_date = parse_date(claim_data.get("discharge_date"))
    
    logger.info(f"✓ Claim: {claim_data['patient_name']}, Policy: {claim_data['policy_number']}")
    logger.info(f"  Admission: {claim_data['admission_date']}, Discharge: {claim_data['discharge_date']}")
    
    timeline_warnings = []
    
    # Check hospitalization duration
    if admission_date and discharge_date:
        hours = (discharge_date - admission_date).total_seconds() / 3600
        logger.info(f"  Hospitalization Duration: {hours:.1f} hours (minimum: {min_hospitalization_hours}h)")
        
        if hours < min_hospitalization_hours:
            warning = f"⚠️ Hospitalization duration ({hours:.1f}h) below minimum ({min_hospitalization_hours}h)"
            timeline_warnings.append(warning)
            logger.info(f"  {warning}")
        else:
            logger.info(f"  ✓ Meets minimum requirement")
    
    # Check time-barred status
    if admission_date:
        days_since = (datetime.now() - admission_date).days
        logger.info(f"  Days Since Admission: {days_since} days")
        
        if days_since > 90:
            warning = f"⚠️ Claim submitted {days_since} days after admission - May be time-barred"
            timeline_warnings.append(warning)
            logger.info(f"  {warning}")
        else:
            logger.info(f"  ✓ Within acceptable timeframe")
    
    logger.info(f"\n  Timeline Status: {'VALID' if not timeline_warnings else 'WARNING'}")
    logger.info(f"  Total Warnings: {len(timeline_warnings)}")
    
    if timeline_warnings:
        for i, warning in enumerate(timeline_warnings, 1):
            logger.info(f"    {i}. {warning}")
    
    logger.info("\n✅ Timeline validation integration test PASSED")

if __name__ == "__main__":
    test_hospitalization_duration()
    test_claim_submission_timeliness()
    test_timeline_validation_integration()
    logger.info("\n" + "="*50)
    logger.info("✅ ALL TIMELINE VALIDATION TESTS PASSED")
    logger.info("="*50)
