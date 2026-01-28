"""
Demo script to test the complete claim processing workflow
"""
import requests
import json
import sys

# Test file (small PDF for quick testing)
TEST_FILE = "test_claim.pdf"
API_URL = "http://localhost:8000/api/claim/process-complete"

def test_claim_processing():
    print("=" * 80)
    print("CLAIM PROCESSING WORKFLOW TEST")
    print("=" * 80)
    
    print("\n📄 Testing with file:", TEST_FILE)
    
    try:
        with open(TEST_FILE, 'rb') as f:
            files = {'file': (TEST_FILE, f, 'application/pdf')}
            print("\n🚀 Sending claim to processing pipeline...")
            
            response = requests.post(API_URL, files=files, timeout=300)
            
            if response.status_code == 200:
                result = response.json()
                
                print("\n✅ PROCESSING COMPLETE")
                print("=" * 80)
                
                print(f"\n📊 Basic Info:")
                print(f"  • File: {result.get('filename')}")
                print(f"  • Total Pages: {result.get('total_pages')}")
                print(f"  • Success: {result.get('success')}")
                
                print(f"\n👤 Claim Data:")
                claim_data = result.get('claim_data', {})
                for key, value in claim_data.items():
                    print(f"  • {key.replace('_', ' ').title()}: {value}")
                
                print(f"\n✅ Policy Verification:")
                coverage = result.get('coverage_verification', {})
                print(f"  • Covered: {coverage.get('is_covered')}")
                print(f"  • Status: {coverage.get('policy_status')}")
                if coverage.get('coverage_details'):
                    details = coverage['coverage_details']
                    print(f"  • Sum Insured: ₹{details.get('sum_insured', 0):,.2f}")
                    print(f"  • Balance: ₹{details.get('balance_sum_insured', 0):,.2f}")
                
                print(f"\n⚖️  Admissibility Check:")
                admiss = result.get('admissibility_check', {})
                print(f"  • Admissible: {admiss.get('is_admissible')}")
                if not admiss.get('is_admissible'):
                    print(f"  • Reasons: {', '.join(admiss.get('reasons', []))}")
                
                print(f"\n💰 Payables Calculation:")
                payables = result.get('payables_calculation', {})
                print(f"  • Total Billed: ₹{payables.get('total_billed', 0):,.2f}")
                print(f"  • Non-Payable: ₹{payables.get('non_payable_amount', 0):,.2f}")
                print(f"  • Room Excess: ₹{payables.get('room_rent_excess', 0):,.2f}")
                print(f"  • Co-Payment: ₹{payables.get('co_payment', 0):,.2f}")
                print(f"  • Deductible: ₹{payables.get('deductible', 0):,.2f}")
                print(f"  • APPROVED AMOUNT: ₹{payables.get('approved_amount', 0):,.2f}")
                
                print(f"\n🎯 FINAL VERDICT:")
                verdict = result.get('final_verdict', {})
                print(f"  • Decision: {verdict.get('decision')}")
                print(f"  • Status: {verdict.get('status')}")
                print(f"  • Approved Amount: ₹{verdict.get('approved_amount', 0):,.2f}")
                if verdict.get('payment_instruction'):
                    print(f"  • Instruction: {verdict.get('payment_instruction')}")
                
                print(f"\n📝 Processing Steps:")
                for step in result.get('processing_steps', []):
                    print(f"  {step['step']}. {step['name']}: {step['status']}")
                
                print("\n" + "=" * 80)
                return True
                
            else:
                print(f"\n❌ Error: HTTP {response.status_code}")
                print(response.text[:500])
                return False
                
    except FileNotFoundError:
        print(f"\n❌ Error: File '{TEST_FILE}' not found")
        print("Please provide a test PDF file")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = test_claim_processing()
    sys.exit(0 if success else 1)
