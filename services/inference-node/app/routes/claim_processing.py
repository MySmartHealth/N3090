"""
Enhanced Claim Processing Endpoint
Complete workflow from upload to final verdict
"""
from fastapi import APIRouter, File, UploadFile, HTTPException, Query, Body
from fastapi.responses import FileResponse, HTMLResponse
import tempfile
import zipfile
from typing import List, Optional
import os
import re
import logging
import tempfile
import httpx
import asyncio
from pdf2image import convert_from_path
import pytesseract
from typing import Dict, List

from app.services.heritage_api import HeritageAPIClient
from app.services.claim_rules import ClaimProcessingRules
try:
    from app.services.tabulation_sheet import generate_tabulation_sheet
except Exception:
    generate_tabulation_sheet = None

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/api/claim/tabulation")
async def get_tabulation_sheet(policy: str = Query(..., description="Policy number to fetch the latest tabulation PDF for")):
    """
    Return the latest tabulation PDF generated for the given policy number.
    Looks for files named tabulation_<policy>_*.pdf in output/tabulations.
    """
    try:
        # Sanitize policy to avoid path traversal; policy numbers are typically alnum
        safe_policy = "".join([c for c in (policy or "") if c.isalnum()])
        if not safe_policy:
            raise HTTPException(status_code=400, detail="Invalid policy parameter")

        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        out_dir = os.path.join(root_dir, "output", "tabulations")
        if not os.path.isdir(out_dir):
            raise HTTPException(status_code=404, detail="No tabulation outputs found yet")

        # Find matching files
        prefix = f"tabulation_{safe_policy}_"
        candidates = [
            os.path.join(out_dir, f)
            for f in os.listdir(out_dir)
            if f.startswith(prefix) and f.endswith('.pdf')
        ]
        if not candidates:
            raise HTTPException(status_code=404, detail=f"No tabulation PDF found for policy {policy}")

        # Pick latest by modification time
        latest = max(candidates, key=lambda p: os.path.getmtime(p))
        return FileResponse(latest, media_type="application/pdf", filename=os.path.basename(latest))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/claim/tabulation/list")
async def list_tabulation_sheets(policy: str = Query(None, description="Optional policy number to filter. If omitted, lists all tabulations.")):
    """
    List available tabulation PDFs. If a policy is provided, only matching PDFs are returned.
    """
    try:
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        out_dir = os.path.join(root_dir, "output", "tabulations")
        if not os.path.isdir(out_dir):
            return {"files": []}

        files = []
        for f in os.listdir(out_dir):
            if not f.endswith('.pdf'):
                continue
            if policy:
                safe_policy = "".join([c for c in (policy or "") if c.isalnum()])
                if not f.startswith(f"tabulation_{safe_policy}_"):
                    continue
            p = os.path.join(out_dir, f)
            try:
                files.append({
                    "filename": f,
                    "path": p,
                    "size": os.path.getsize(p),
                    "mtime": os.path.getmtime(p)
                })
            except Exception:
                continue
        # Sort newest first
        files.sort(key=lambda x: x.get("mtime", 0), reverse=True)
        return {"files": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/claim/tabulation/by-file")
async def get_tabulation_by_file(name: str = Query(..., description="Exact tabulation filename (e.g., tabulation_<policy>_<timestamp>.pdf)")):
    """
    Return a tabulation PDF by exact filename. Only basenames within output/tabulations are allowed.
    """
    try:
        if not name or "/" in name or ".." in name:
            raise HTTPException(status_code=400, detail="Invalid filename")
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        out_dir = os.path.join(root_dir, "output", "tabulations")
        full = os.path.join(out_dir, name)
        if not (os.path.isfile(full) and name.endswith('.pdf')):
            raise HTTPException(status_code=404, detail="File not found")
        return FileResponse(full, media_type="application/pdf", filename=name)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/claim/tabulation/generate")
async def generate_tabulation_from_result(result: dict = Body(..., description="Full claim processing result JSON to render as a tabulation PDF")):
    """
    Generate a tabulation PDF from a provided claim processing result JSON and return the output path.
    """
    try:
        if not generate_tabulation_sheet:
            raise HTTPException(status_code=500, detail="Tabulation generator unavailable")
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        out_dir = os.path.join(root_dir, "output", "tabulations")
        pdf_path = generate_tabulation_sheet(result, out_dir)
        return {"tabulation_sheet": pdf_path}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/claim/tabulation/zip")
async def zip_tabulations(
    policy: Optional[str] = Query(None, description="Optional policy number to filter tabulations"),
    names: Optional[str] = Query(None, description="Optional comma-separated list of exact filenames to include")
):
    """
    Download a ZIP containing tabulation PDFs.
    - If `names` is provided (comma-separated), only those filenames are included.
    - Else if `policy` is provided, include all tabulations for that policy.
    - Else include all available tabulations.
    """
    try:
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        out_dir = os.path.join(root_dir, "output", "tabulations")
        if not os.path.isdir(out_dir):
            raise HTTPException(status_code=404, detail="No tabulation outputs found yet")

        # Build candidate list
        candidates: List[str] = []
        all_pdfs = [f for f in os.listdir(out_dir) if f.endswith('.pdf')]
        if names:
            requested = [n.strip() for n in names.split(',') if n.strip()]
            # sanitize basenames only
            safe_requested = [n for n in requested if '/' not in n and '..' not in n]
            for n in safe_requested:
                fp = os.path.join(out_dir, n)
                if os.path.isfile(fp):
                    candidates.append(fp)
        else:
            if policy:
                safe_policy = "".join([c for c in (policy or "") if c.isalnum()])
                prefix = f"tabulation_{safe_policy}_"
                for f in all_pdfs:
                    if f.startswith(prefix):
                        candidates.append(os.path.join(out_dir, f))
            else:
                candidates = [os.path.join(out_dir, f) for f in all_pdfs]

        if not candidates:
            raise HTTPException(status_code=404, detail="No matching tabulation PDFs found")

        # Create temp zip
        label = (policy or 'all')
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{label}.zip") as tmp:
            zip_path = tmp.name
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for fp in candidates:
                    zf.write(fp, arcname=os.path.basename(fp))
        except Exception:
            # Ensure tmp cleaned on failure
            try:
                os.unlink(zip_path)
            except Exception:
                pass
            raise

        filename = f"tabulations_{label}.zip"
        return FileResponse(zip_path, media_type="application/zip", filename=filename)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/claim/process-complete")
async def process_claim_complete(file: UploadFile = File(...)):
    """
    Complete claim processing pipeline:
    1. OCR extraction of all pages
    2. Create summary of each page
    3. Categorize pages by type
    4. Identify claim, claimant, and TPA
    5. Verify policy coverage via Heritage API
    6. Check claim admissibility rules
    7. Calculate payables (deduct non-payable items)
    8. Generate final verdict with approved amount
    """
    
    try:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        
        logger.info(f"🔍 Processing claim: {file.filename} ({len(content)} bytes)")
        
        # ============= STEP 1: OCR EXTRACTION =============
        logger.info("📄 STEP 1: OCR extraction...")
        try:
            images = convert_from_path(tmp_path, dpi=200)
        except Exception as e:
            logger.error(f"Failed to convert PDF to images: {e}")
            os.unlink(tmp_path)
            raise HTTPException(status_code=400, detail=f"Failed to process PDF: {str(e)}")
        
        if not images:
            os.unlink(tmp_path)
            raise HTTPException(status_code=400, detail="PDF has no pages")
        
        pages = []
        for i, img in enumerate(images):
            try:
                text = pytesseract.image_to_string(img)
                pages.append({"page": i + 1, "text": text, "chars": len(text)})
            except Exception as e:
                logger.warning(f"OCR failed for page {i + 1}: {e}")
                pages.append({"page": i + 1, "text": "", "chars": 0})
        
        logger.info(f"✓ Extracted {len(pages)} pages")
        
        # ============= STEP 2: CREATE PAGE SUMMARIES =============
        logger.info("📝 STEP 2: Creating page summaries...")
        page_summaries = []
        for p in pages:
            summary = {
                "page": p['page'],
                "chars": p['chars'],
                "preview": p['text'][:300] if p['text'] else "",
                "word_count": len(p['text'].split()) if p['text'] else 0
            }
            page_summaries.append(summary)
        
        # ============= STEP 3: CATEGORIZE PAGES =============
        logger.info("🏷️  STEP 3: Categorizing pages...")
        categories = {
            "claim_form": [], "patient_info": [], "authorization": [],
            "discharge_summary": [], "billing": [], "lab_reports": [],
            "receipts": [], "other": []
        }
        
        for p in pages:
            text = p['text'].lower()
            page_num = p['page']
            
            if 'claim' in text and ('form' in text or 'history' in text):
                cat = "claim_form"
            elif 'authorization' in text or 'pre-auth' in text:
                cat = "authorization"
            elif 'discharge' in text and ('summary' in text or 'diagnosis' in text):
                cat = "discharge_summary"
            elif 'bill' in text and ('final' in text or 'amount' in text or 'charges' in text):
                cat = "billing"
            elif 'receipt' in text or 'payment' in text:
                cat = "receipts"
            elif 'report' in text and 'lab' in text:
                cat = "lab_reports"
            elif 'patient' in text:
                cat = "patient_info"
            else:
                cat = "other"
            
            categories[cat].append(page_num)
            page_summaries[page_num - 1]["category"] = cat
        
        logger.info(f"✓ Categorized: {', '.join([f'{k}={len(v)}' for k,v in categories.items() if v])}")

        # ============= STEP 4: IDENTIFY CLAIM, CLAIMANT & TPA =============
        logger.info("🔎 STEP 4: Identifying claim, claimant & TPA...")
        full_text = "\n".join([p['text'] for p in pages])
        
        # Initialize rules engine with inferred company/product based on document text
        company = None
        product = None
        lower_text = full_text.lower()
        
        # Enhanced insurer/product detection
        if "oriental" in lower_text and "insurance" in lower_text:
            company = "Oriental Insurance"
            if "happy family floater" in lower_text or "hff" in lower_text:
                product = "Happy Family Floater 2021"
        elif "national insurance" in lower_text:
            company = "National Insurance"
            if "parivar mediclaim" in lower_text or "parivar" in lower_text:
                product = "Parivar Mediclaim Policy"
        elif "hdfc" in lower_text or "hdfc ergo" in lower_text:
            company = "HDFC ERGO General Insurance Company Limited."
            if "health" in lower_text:
                product = lower_text  # Will match available HDFC ERGO products
        elif "star health" in lower_text:
            company = "Star Health And Allied Insurance Co. Ltd"
        elif "navi" in lower_text and "insurance" in lower_text:
            company = "Navi General Insurance Ltd."
        elif "sbi" in lower_text and "insurance" in lower_text:
            company = "SBI General Insurance Company Limited"
        elif "manipal cigna" in lower_text or "manipal" in lower_text:
            company = "Manipal Cigna Health Insurance Co. Ltd."
        elif "niva bupa" in lower_text or "niva" in lower_text:
            company = "Niva Bupa Health Insurance Company Limited"
        elif "bajaj allianz" in lower_text or "bajaj" in lower_text:
            company = "Bajaj Allianz General Insurance Co. Ltd."

        # Initialize rules engine with inferred company/product
        rules_engine = ClaimProcessingRules(company=company, product=product)
        logger.info(f"✓ Inferred Insurer: {company}, Product: {product}")
        
        
        def extract_field(patterns, text, default=""):
            for pattern in patterns:
                try:
                    match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
                    if match:
                        return match.group(1).strip()
                except:
                    pass
            return default
        
        claim_data = {
            "patient_name": extract_field([
                r"patient\s*(?:name)?\s*:?\s*(?:mrs?\.?\s*)?([A-Z][A-Za-z\s\.]+)",
                r"name\s*:?\s*(?:mrs?\.?\s*)?([A-Z][A-Za-z\s\.]+)"
            ], full_text),
            "age": extract_field([r"age\s*:?\s*(\d+)"], full_text),
            "hospital": extract_field([
                r"(apollo\s*hospital[^\n]*)",
                r"hospital\s*:?\s*([^\n]+)"
            ], full_text),
            "diagnosis": extract_field([
                r"diagnosis\s*:?\s*([^\n]+)",
                r"final\s*diagnosis\s*:?\s*([^\n]+)"
            ], full_text),
            "claim_amount": extract_field([
                r"(?:total|final|grand)\s*(?:bill|amount)\s*:?\s*rs\.?\s*([\d,]+)",
            ], full_text),
            "admission_date": extract_field([
                r"(?:admission|admitted)\s*(?:on|date)?\s*:?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})"
            ], full_text),
            "discharge_date": extract_field([
                r"(?:discharge|discharged)\s*(?:on|date)?\s*:?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})"
            ], full_text),
            "policy_number": extract_field([
                r"policy\s*(?:no|number)?\s*:?\s*(\d{10,})"
            ], full_text),
            "tpa": extract_field([
                r"(heritage\s*health[^\n]*)",
                r"(hdfc\s*ergo[^\n]*)"
            ], full_text)
        }
        
        logger.info(f"✓ Patient: {claim_data['patient_name']}, Policy: {claim_data['policy_number']}")

        # ============= STEP 4.5: VALIDATE TIMELINE & HOSPITALIZATION =============
        logger.info("⏱️  STEP 4.5: Validating claim timeline and hospitalization requirements...")

        from datetime import datetime, timedelta

        timeline_warnings = []

        # Parse dates from claim data
        def parse_date(date_str):
            if not date_str:
                return None
            for fmt in ["%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%Y/%m/%d", "%d-%m-%y", "%d/%m/%y"]:
                try:
                    return datetime.strptime(date_str.strip(), fmt)
                except:
                    continue
            return None

        admission_date = parse_date(claim_data.get("admission_date"))
        discharge_date = parse_date(claim_data.get("discharge_date"))

        # Check minimum hospitalization hours (policy requirement: typically 24-72 hours)
        if admission_date and discharge_date:
            hospitalization_hours = (discharge_date - admission_date).total_seconds() / 3600
            min_hours = 24  # Default requirement

            # Override with policy requirement if available
            if company and product and rules_engine and rules_engine.policy_rules:
                policy_rules = rules_engine.policy_rules.get("admissibility", {})
                min_hours = policy_rules.get("min_hospitalization_hours", min_hours)

            if hospitalization_hours < min_hours:
                timeline_warnings.append(f"⚠️ Hospitalization duration ({hospitalization_hours:.1f}h) below minimum ({min_hours}h) - May affect admissibility")
                logger.warning(f"⚠️ Short hospitalization: {hospitalization_hours:.1f} hours (minimum: {min_hours})")
            else:
                logger.info(f"✓ Hospitalization duration: {hospitalization_hours:.1f} hours (meets minimum {min_hours}h)")

        # Note: Claim intimation deadline (48-72 hours) would require hospitalization_date from system
        # This would be validated against current datetime when claim is processed
        if admission_date:
            days_since_admission = (datetime.now() - admission_date).days
            if days_since_admission > 90:
                timeline_warnings.append(f"⚠️ Claim submitted {days_since_admission} days after admission - May be time-barred per policy")
                logger.warning(f"⚠️ Old claim: {days_since_admission} days post-admission")
        
        # Extract billing items
        billing_items = []
        for page_num in categories.get("billing", []):
            page_text = pages[page_num - 1]['text']
            item_matches = re.findall(r'([A-Z][A-Za-z\s\-&()]+)\s+(?:Rs\.?|₹)\s*([\d,]+)', page_text)
            for item_name, amount in item_matches:
                try:
                    billing_items.append({
                        "name": item_name.strip(),
                        "amount": float(amount.replace(',', '')),
                        "page": page_num
                    })
                except:
                    pass
        
        logger.info(f"✓ Extracted {len(billing_items)} billing items")
        
        # ============= STEP 5: VERIFY POLICY COVERAGE =============
        logger.info("✅ STEP 5: Verifying policy coverage...")
        heritage_client = HeritageAPIClient()
        
        coverage_verification = await heritage_client.verify_policy_coverage(
            policy_number=claim_data.get("policy_number", ""),
            patient_name=claim_data.get("patient_name", ""),
            patient_age=int(claim_data.get("age", 0)) if claim_data.get("age") else None
        )
        
        is_covered = coverage_verification.get("is_covered", False)
        logger.info(f"✓ Policy Coverage: {'ACTIVE' if is_covered else 'INVALID'}")
        
        if not is_covered:
            os.unlink(tmp_path)
            return {
                "success": False,
                "filename": file.filename,
                "total_pages": len(pages),
                "claim_data": claim_data,
                "coverage_verification": coverage_verification,
                "final_verdict": {
                    "decision": "REJECTED",
                    "approved_amount": 0,
                    "reasons": ["Policy not found or inactive"],
                    "status": "POLICY_INVALID"
                }
            }
        
        # ============= STEP 6: CHECK DOCUMENT COMPLETENESS =============
        logger.info("📋 STEP 6: Checking document completeness...")
        
        document_check = rules_engine.check_document_completeness(categories)
        
        logger.info(f"✓ Document Completeness: {document_check['completeness_percentage']:.1f}% - {document_check['summary']}")
        
        # Document incompleteness is a warning, not a rejection (can proceed with manual review)
        if not document_check['is_complete']:
            logger.warning(f"⚠️ {document_check['warning']}")
        
        # ============= STEP 7: CHECK ADMISSIBILITY =============
        logger.info("⚖️  STEP 7: Checking claim admissibility...")
        
        is_admissible, admissibility_reasons = rules_engine.check_admissibility(
            claim_data,
            coverage_verification
        )
        
        logger.info(f"✓ Admissible: {is_admissible}")
        
        if not is_admissible:
            os.unlink(tmp_path)
            return {
                "success": False,
                "filename": file.filename,
                "total_pages": len(pages),
                "categories": categories,
                "claim_data": claim_data,
                "coverage_verification": coverage_verification,
                "document_completeness": document_check,
                "admissibility_check": {
                    "is_admissible": False,
                    "reasons": admissibility_reasons
                },
                "final_verdict": {
                    "decision": "REJECTED",
                    "approved_amount": 0,
                    "reasons": admissibility_reasons,
                    "status": "NOT_ADMISSIBLE"
                }
            }
        
        # ============= STEP 8: CALCULATE PAYABLES =============
        logger.info("💰 STEP 8: Calculating payables...")
        
        # Extract room details if available
        room_details = None
        room_match = re.search(r'room\s*(?:rent|charge)\s*:?\s*(?:rs\.?|₹)?\s*([\d,]+)', full_text, re.IGNORECASE)
        if room_match:
            room_details = {
                "type": "SINGLE_PRIVATE",
                "daily_charge": float(room_match.group(1).replace(',', '')),
                "days": 3  # Default, should extract from discharge-admission date diff
            }
        
        payables = rules_engine.calculate_payables(
            billing_items,
            coverage_verification,
            room_details
        )
        
        logger.info(f"✓ Billed: ₹{payables['total_billed']:,.2f}, Payable: ₹{payables['approved_amount']:,.2f}")
        
        # ============= STEP 9: FINAL VERDICT =============
        logger.info("🎯 STEP 9: Generating final verdict...")
        
        final_verdict = rules_engine.get_final_verdict(
            is_admissible,
            admissibility_reasons,
            payables
        )
        
        logger.info(f"✓ Final Decision: {final_verdict['decision']} - ₹{final_verdict.get('approved_amount', 0):,.2f}")
        
        # Build response
        response = {
            "success": True,
            "filename": file.filename,
            "total_pages": len(pages),
            "categories": {k: v for k, v in categories.items() if v},
            "page_summaries": page_summaries[:10],  # First 10 pages
            "claim_data": claim_data,
            "coverage_verification": coverage_verification,
            "document_completeness": document_check,
            "admissibility_check": {
                "is_admissible": is_admissible,
                "reasons": admissibility_reasons
            },
            "payables_calculation": payables,
            "final_verdict": final_verdict,
            "processing_steps": [
                {"step": 1, "name": "OCR Extraction", "status": "COMPLETED", "pages": len(pages)},
                {"step": 2, "name": "Page Summaries", "status": "COMPLETED", "count": len(page_summaries)},
                {"step": 3, "name": "Page Categorization", "status": "COMPLETED", "categories": len([k for k,v in categories.items() if v])},
                {"step": 4, "name": "Claim Identification", "status": "COMPLETED", "patient": claim_data.get("patient_name")},
                {"step": 5, "name": "Policy Verification", "status": "COMPLETED", "covered": is_covered},
                {"step": 6, "name": "Document Completeness", "status": "COMPLETED", "completeness": f"{document_check['completeness_percentage']:.0f}%"},
                {"step": 7, "name": "Admissibility Check", "status": "COMPLETED", "admissible": is_admissible},
                {"step": 8, "name": "Payables Calculation", "status": "COMPLETED", "amount": payables["approved_amount"]},
                {"step": 9, "name": "Final Verdict", "status": "COMPLETED", "decision": final_verdict["decision"]}
            ],
            "timeline_validation": {
                "admission_date": claim_data.get("admission_date"),
                "discharge_date": claim_data.get("discharge_date"),
                "warnings": timeline_warnings,
                "status": "VALID" if not timeline_warnings else "WARNING"
            }
        }

        # Generate tabulation sheet PDF if available
        try:
            if generate_tabulation_sheet:
                root_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                out_dir = os.path.join(root_dir, "output", "tabulations")
                pdf_path = generate_tabulation_sheet(response, out_dir)
                response["artifacts"] = {"tabulation_sheet": pdf_path}
        except Exception as _e:
            # Non-fatal if PDF generation fails
            response["artifacts"] = {"tabulation_sheet_error": str(_e)}

        # Clean up
        os.unlink(tmp_path)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in claim processing: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/claim/tabulation/view", response_class=HTMLResponse)
async def view_tabulation(
    policy: str = Query(..., description="Policy number to view the latest tabulation for"),
    filename: Optional[str] = Query(None, description="Optional exact filename; if omitted, uses latest for policy")
):
    """
    Render an HTML page with an embedded PDF viewer and a download button.
    """
    try:
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        out_dir = os.path.join(root_dir, "output", "tabulations")
        
        pdf_file = None
        if filename:
            # Use exact filename
            if "/" in filename or ".." in filename:
                raise HTTPException(status_code=400, detail="Invalid filename")
            fp = os.path.join(out_dir, filename)
            if os.path.isfile(fp) and filename.endswith('.pdf'):
                pdf_file = fp
            else:
                raise HTTPException(status_code=404, detail=f"File not found: {filename}")
        else:
            # Find latest for policy
            safe_policy = "".join([c for c in (policy or "") if c.isalnum()])
            if not safe_policy:
                raise HTTPException(status_code=400, detail="Invalid policy")
            prefix = f"tabulation_{safe_policy}_"
            candidates = [
                os.path.join(out_dir, f)
                for f in os.listdir(out_dir)
                if f.startswith(prefix) and f.endswith('.pdf')
            ]
            if candidates:
                pdf_file = max(candidates, key=lambda p: os.path.getmtime(p))
            else:
                raise HTTPException(status_code=404, detail=f"No tabulation PDF found for policy {policy}")
        
        base_name = os.path.basename(pdf_file)
        download_url = f"/api/claim/tabulation/by-file?name={base_name}"
        
        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tabulation Sheet - {policy}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
        .header {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; }}
        .title {{ font-size: 20px; font-weight: 600; color: #333; }}
        .policy-info {{ font-size: 14px; color: #666; margin-top: 4px; }}
        .button {{ padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; font-weight: 500; text-decoration: none; display: inline-block; transition: all 0.2s; }}
        .btn-download {{ background: #0066cc; color: white; }}
        .btn-download:hover {{ background: #0052a3; }}
        .pdf-viewer {{ background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); overflow: hidden; }}
        iframe {{ width: 100%; height: 800px; border: none; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <div class="title">Tabulation Sheet - Medical Officer Review</div>
                <div class="policy-info">Policy: {policy}</div>
            </div>
            <a href="{download_url}" class="button btn-download" download="{base_name}">⬇ Download PDF</a>
        </div>
        <div class="pdf-viewer">
            <iframe src="data:application/pdf;base64," type="application/pdf"></iframe>
        </div>
        <script>
            // Fetch PDF and embed it
            fetch('{download_url}')
                .then(r => r.blob())
                .then(blob => {{
                    const url = URL.createObjectURL(blob);
                    document.querySelector('iframe').src = url;
                }})
                .catch(e => {{
                    document.querySelector('.pdf-viewer').innerHTML = '<p style="padding: 20px; color: #d32f2f;">Error loading PDF: ' + e.message + '</p>';
                }});
        </script>
    </div>
</body>
</html>
        """
        return html
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
