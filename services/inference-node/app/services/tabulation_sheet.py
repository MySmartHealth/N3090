"""
Generates a tabulation PDF for a processed claim using ReportLab.
"""
import os
from datetime import datetime
from typing import Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


def _kv_rows(d: Dict, keys: List[List[str]]) -> List[List[str]]:
    rows = []
    for label, value in keys:
        rows.append([label, value if value is not None else "-"])
    return rows


def _safe_get(d: Dict, path: List[str], default=""):
    cur = d
    for p in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(p)
        if cur is None:
            return default
    return cur


def generate_tabulation_sheet(result: Dict, out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    base_name = _safe_get(result, ["coverage_verification", "policy_number"], "claim")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"tabulation_{base_name}_{ts}.pdf".replace("/", "_")
    out_path = os.path.join(out_dir, fname)

    styles = getSampleStyleSheet()
    story = []

    title = Paragraph("MEDICAL OFFICER REVIEW SHEET", styles["Title"]) 
    story.append(title)
    story.append(Spacer(1, 8))

    # Administrative summary (aligns with blue sheet headings when data available)
    ccn = result.get("ccn", "-")
    policy_type = _safe_get(result, ["coverage_verification", "policy_type"], "-")
    bill_type = result.get("bill_type", result.get("claim_type", "-"))
    card_no = result.get("card_no", "-")
    intimation_date = result.get("intimation_date", "-")
    file_receipt_date = result.get("file_receipt_date", "-")
    bo_do_code = result.get("bo_do_code", "-")
    policy_valid_from = _safe_get(result, ["coverage_verification", "coverage_details", "policy_start_date"], "-")
    policy_valid_to = _safe_get(result, ["coverage_verification", "coverage_details", "policy_end_date"], "-")
    proposer_name = result.get("proposer_name", "-")
    cumulative_bonus = result.get("cumulative_bonus", "-")

    patient = _safe_get(result, ["claim_data", "patient_name"]) or "-"
    policy_no = _safe_get(result, ["coverage_verification", "policy_number"]) or _safe_get(result, ["claim_data", "policy_number"]) or "-"
    policy_status = _safe_get(result, ["coverage_verification", "policy_status"], "-")
    sum_insured = _safe_get(result, ["coverage_verification", "coverage_details", "sum_insured"], "-")
    balance_si = _safe_get(result, ["coverage_verification", "coverage_details", "balance_sum_insured"], "-")
    hospital = _safe_get(result, ["claim_data", "hospital"], "-")
    diagnosis = _safe_get(result, ["claim_data", "diagnosis"], "-")
    doa = _safe_get(result, ["claim_data", "admission_date"], "-")
    dod = _safe_get(result, ["claim_data", "discharge_date"], "-")

    top_rows = _kv_rows(result, [
        ["CCN", str(ccn)],
        ["Policy Type", str(policy_type)],
        ["Bill Type", str(bill_type)],
        ["Card No", str(card_no)],
        ["Intimation Date", str(intimation_date)],
        ["File Receipt Date", str(file_receipt_date)],
        ["Policy No", str(policy_no)],
        ["BO/Do Code", str(bo_do_code)],
        ["Policy Valid From", str(policy_valid_from)],
        ["Policy Valid To", str(policy_valid_to)],
        ["Proposer Name", str(proposer_name)],
        ["Patient's Name", str(patient)],
        ["Sum Insured", f"{sum_insured}"],
        ["Cummulative Bonus", f"{cumulative_bonus}"],
        ["Hospital Name", str(hospital)],
        ["Illness", str(diagnosis)],
        ["DOA", str(doa)],
        ["DOD", str(dod)],
        ["Balance Available", f"{balance_si}"],
    ])
    t1 = Table(top_rows, colWidths=[130, 350])
    t1.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ("BACKGROUND", (0,0), (0,-1), colors.whitesmoke),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ]))
    story.append(t1)
    story.append(Spacer(1, 10))

    # Document completeness
    doc = result.get("document_completeness", {})
    completeness = f"{doc.get('completeness_percentage', 0):.0f}%"
    missing = doc.get("missing_mandatory_documents", [])
    missing_names = ", ".join([m.get("label", m.get("type", "")) for m in missing]) or "None"
    dc_rows = _kv_rows(doc, [
        ["Documents Completeness", completeness],
        ["Missing Mandatory", missing_names],
        ["Warning", doc.get("warning", "-")],
    ])
    t2 = Table(dc_rows, colWidths=[130, 350])
    t2.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.5, colors.lightgrey),
        ("BACKGROUND", (0,0), (0,-1), colors.whitesmoke),
    ]))
    story.append(Paragraph("Documents", styles["Heading3"]))
    story.append(t2)
    story.append(Spacer(1, 10))

    # Payables summary
    pay = result.get("payables_calculation", {})
    pay_rows = [
        ["Total Billed", f"{pay.get('total_billed', 0):,.2f}"],
        ["Non-payable Items", f"{pay.get('non_payable_amount', 0):,.2f}"],
        ["Room Rent Excess", f"{pay.get('room_rent_excess', 0):,.2f}"],
        ["Co-payment", f"{pay.get('co_payment', 0):,.2f}"],
        ["Deductible", f"{pay.get('deductible', 0):,.2f}"],
        ["Total Deductions", f"{pay.get('total_deductions', 0):,.2f}"],
        ["Final Payable", f"{pay.get('approved_amount', 0):,.2f}"],
    ]
    t3 = Table(pay_rows, colWidths=[130, 350])
    t3.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ("BACKGROUND", (0,0), (0,-1), colors.whitesmoke),
    ]))
    story.append(Paragraph("Financial Summary", styles["Heading3"]))
    story.append(t3)
    story.append(Spacer(1, 10))

    # Deduction breakdown table
    ded = pay.get("deduction_breakdown", []) or []
    if ded:
        data = [["Type", "Amount", "Reason"]]
        for d in ded:
            data.append([
                str(d.get("type", "-")),
                f"{d.get('amount', 0):,.2f}",
                str(d.get("reason", "-"))
            ])
        t4 = Table(data, colWidths=[120, 80, 280])
        t4.setStyle(TableStyle([
            ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
            ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ]))
        story.append(Paragraph("Deduction Breakdown", styles["Heading3"]))
        story.append(t4)
        story.append(Spacer(1, 10))

    # Non-payable items table
    npi = pay.get("non_payable_items", []) or []

    # Billing items (consolidated view akin to blue sheet's expense lines)
    items = []
    for it in (pay.get("payable_items", []) or []):
        items.append([str(it.get("name", "-")), f"{it.get('amount', 0):,.2f}", str(it.get("page", "-"))])
    for it in (npi or []):
        items.append([str(it.get("name", "-")) + " (Non-payable)", f"{it.get('amount', 0):,.2f}", "-"])
    if items:
        tbl = Table([["Item", "Amount (Rs.)", "Page"]] + items, colWidths=[280, 120, 80])
        tbl.setStyle(TableStyle([
            ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
            ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ]))
        story.append(Paragraph("Billing Items", styles["Heading3"]))
        story.append(tbl)

    if npi:
        data = [["Item", "Amount", "Reason"]]
        for it in npi:
            data.append([
                str(it.get("name", "-")),
                f"{it.get('amount', 0):,.2f}",
                str(it.get("reason", "-"))
            ])
        t5 = Table(data, colWidths=[200, 80, 200])
        t5.setStyle(TableStyle([
            ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
            ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ]))
        story.append(Paragraph("Non-payable Items", styles["Heading3"]))
        story.append(t5)

    doc = SimpleDocTemplate(out_path, pagesize=A4, rightMargin=24, leftMargin=24, topMargin=24, bottomMargin=24)
    doc.build(story)
    return out_path
