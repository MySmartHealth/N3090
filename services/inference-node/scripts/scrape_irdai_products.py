#!/usr/bin/env python3
"""
Scrape IRDAI Health Insurance Products and generate policy master YAMLs.
URL: https://irdai.gov.in/health-insurance-products

Notes:
- Uses requests + BeautifulSoup to fetch and parse insurer-wise products.
- Generates YAML files under Policy Rules/ with placeholder admissibility/exclusions/limits.
- Be polite: sets a custom User-Agent and basic rate limiting.

Usage:
    python scripts/scrape_irdai_products.py --dry-run
    python scripts/scrape_irdai_products.py --out "services/inference-node/Policy Rules"
    python scripts/scrape_irdai_products.py --insurer "Oriental Insurance"

"""
import os
import re
import time
import argparse
import requests
from bs4 import BeautifulSoup
import yaml
try:
    from PyPDF2 import PdfReader
except Exception:
    PdfReader = None

IRDAI_URL = "https://irdai.gov.in/health-insurance-products"
DEFAULT_OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Policy Rules")
HEADERS = {
    "User-Agent": "N3090-PolicyScraper/1.0 (+https://mysmarthealth.example)"
}


def normalize_text(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def to_filename(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_\- ]", "", name)
    safe = safe.strip().lower().replace(" ", "_")
    return safe


def fetch_page(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_products(html: str):
    """
    Parse insurer-wise products from the IRDAI page.
    Target a table with headers including 'Name of the Insurer' and 'Product Name'.
    Returns list of dicts: {company, products: [ {name, uin?, type?, year?} ]}
    """
    soup = BeautifulSoup(html, "html.parser")

    # Find the main products table by header labels
    target_tables = []
    for table in soup.find_all("table"):
        headers = [normalize_text(th.get_text()) for th in table.find_all("th")]
        header_text = " ".join(headers).lower()
        if (
            "name of the insurer" in header_text and
            "product name" in header_text
        ):
            target_tables.append(table)

    companies = {}
    # Prefer targeted tables; if none found, scan all tables for row pattern
    search_tables = target_tables if target_tables else soup.find_all("table")
    for t in search_tables:
        for tr in t.find_all("tr"):
            cols = tr.find_all("td")
            if len(cols) < 5:
                continue
            # Try mapping by typical order observed on site
            texts = [normalize_text(c.get_text()) for c in cols]
            # UIN is typically alphanumeric with pattern like XXXHLIP23020V012223
            uin = None
            uin_idx = None
            for i, txt in enumerate(texts):
                if re.match(r"^[A-Z]{3}[A-Z]{3}[A-Z]{2}\d{5}V\d{6}$", txt):
                    uin = txt
                    uin_idx = i
                    break

            company_name = None
            product_name = None

            if uin_idx is not None:
                # Insurer is usually the column before UIN
                if uin_idx - 1 >= 0:
                    company_name = texts[uin_idx - 1]
                # Product is usually the column after UIN
                if uin_idx + 1 < len(texts):
                    product_name = texts[uin_idx + 1]
            else:
                # Fallback: choose insurer by presence of 'Insurance Company' patterns
                insurer_idx = None
                for i, txt in enumerate(texts):
                    if re.search(r"(general|health).*insurance.*(company|co\.|limited|ltd\.)", txt, re.IGNORECASE):
                        insurer_idx = i
                        break
                if insurer_idx is None:
                    continue
                company_name = texts[insurer_idx]
                # Product name likely near insurer cell; choose the next non-date/non-status cell
                for j in range(insurer_idx + 1, len(texts)):
                    cand = texts[j]
                    if re.match(r"\d{2}-\d{2}-\d{4}", cand):
                        continue
                    if cand.lower() in ("non-archived", "archived"):
                        continue
                    if len(cand) >= 4 and not re.match(r"^\d{4}-\d{4}$", cand):
                        product_name = cand
                        break
            # Type of product: last column often contains 'Individual', 'Group', 'Add on', 'Revision'
            prod_type = texts[-1] if texts else None
            # Financial year: any token like '2022-2023'
            year = None
            for txt in texts:
                if re.match(r"^\d{4}-\d{4}$", txt):
                    year = txt
                    break
            # Try to capture PDF link within the row
            pdf_url = None
            for a in tr.find_all("a", href=True):
                href = a["href"]
                if href and href.lower().endswith('.pdf'):
                    pdf_url = href
                    break

            if not company_name or not product_name:
                continue

            companies.setdefault(company_name, [])
            companies[company_name].append({
                "name": product_name,
                "uin": uin,
                "type": prod_type,
                "year": year,
                "pdf_url": pdf_url,
            })

    # Convert to list format
    result = []
    for company, products in companies.items():
        # Deduplicate products by name
        seen = set()
        unique = []
        for p in products:
            key = p["name"].lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(p)
        result.append({"company": company, "products": unique})

    return result


def build_yaml(company: str, product: str, meta: dict | None = None) -> dict:
    return {
        "company": company,
        "product": product,
        "version": "scraped",
        "effective_from": None,
        "policy_type": "health",  # 'health', 'corporate_floater', 'group'
        "meta": meta or {},
        "admissibility": {
            "min_hospitalization_hours": 24,
            "first_year_waiting_days": 30,
            "daycare_procedures_allowed": True,
            "pre_hospitalization_days": 30,
            "post_hospitalization_days": 60,
            "pre_existing_waiting_years": 4,
            "maternity_waiting_years": 2,
            "newborn_coverage_day": 1,
            "opd_covered": False,
            "psychiatry_covered": False,
            "infertility_covered": False,
            "internal_congenital_covered": True,
            "external_congenital_covered": False,
            "domiciliary_hospitalization": False,
            "cashless_allowed": True,
            "job_loss_continuity_cover": False,
            "suicide_coverage_after_years": 1
        },
        "exclusions": {
            "diseases": [
                "cosmetic surgery",
                "fertility treatment",
                "congenital external diseases",
                "HIV/AIDS",
                "obesity treatment"
            ],
            "items": [
                "diapers",
                "toiletries",
                "sanitary napkins",
                "registration charges",
                "dental treatment",
                "orthodontic treatment"
            ],
            "special": []
        },
        "limits": {
            "room_rent_limit_per_day": {
                "GENERAL_WARD": 1500,
                "TWIN_SHARING": 3000,
                "SINGLE_PRIVATE": 5000,
                "ICU": 8000,
                "ICCU": 7000
            },
            "sub_limits": {
                "cataract_per_eye": 25000,
                "ambulance_charges": 2000,
                "air_ambulance": 200000,
                "lasik_eye_surgery": 50000
            },
            "maternity_benefit_cap": 200000,
            "newborn_benefit_cap": 100000,
            "pre_post_natal_expenses": 50000,
            "organ_donor_expenses_cap": 500000,
            "organ_receiver_expenses_cap": 500000,
            "non_medical_expenses_cap": 10000,
            "package_treatment_caps": {}
        },
        "payables_rules": {
            "co_payment_percent": 0,
            "copay_ceiling_annual": 100000,
            "deductible_amount": 0,
            "aggregate_deductible_annual": 0,
            "first_30_days_discount": 0,
            "disease_caps": {},
            "si_reload_mechanism": False
        }
    }


def download_pdf(url: str, out_dir: str) -> str | None:
    try:
        os.makedirs(out_dir, exist_ok=True)
        # Resolve relative base
        if url.startswith('/'):
            full_url = f"https://irdai.gov.in{url}"
        else:
            full_url = url
        fname = to_filename(os.path.basename(full_url)) or f"policy_{int(time.time())}.pdf"
        path = os.path.join(out_dir, fname)
        resp = requests.get(full_url, headers=HEADERS, timeout=60)
        resp.raise_for_status()
        with open(path, 'wb') as f:
            f.write(resp.content)
        return path
    except Exception:
        return None


def extract_text_from_pdf(path: str) -> str:
    try:
        if PdfReader is None:
            return ''
        reader = PdfReader(path)
        texts = []
        for page in reader.pages:
            t = page.extract_text() or ''
            texts.append(t)
        return "\n".join(texts)
    except Exception:
        return ''


def parse_rules_from_text(text: str) -> dict:
    rules = {
        "limits": {"room_rent_limit_per_day": {}},
        "payables_rules": {},
        "exclusions": {"items": [], "diseases": []}
    }
    lower = text.lower()
    m = re.search(r"co\s*[- ]?payment\s*[:\-]?\s*(\d{1,2})\s*%", lower)
    if m:
        rules["payables_rules"]["co_payment_percent"] = int(m.group(1))
    m = re.search(r"deductible\s*[:\-]?\s*(?:rs\.?|₹)?\s*([\d,]+)", lower)
    if m:
        try:
            rules["payables_rules"]["deductible_amount"] = int(m.group(1).replace(',', ''))
        except Exception:
            pass
    room_types = {
        "GENERAL_WARD": ["general ward", "general"],
        "TWIN_SHARING": ["twin sharing", "double sharing"],
        "SINGLE_PRIVATE": ["single room", "private room", "single private"],
        "ICU": ["icu"],
    }
    for key, phrases in room_types.items():
        for ph in phrases:
            mm = re.search(rf"{ph}[^\n]*\b(?:room\s*rent|charges?)\b[^\n]*?(?:rs\.?|₹)?\s*([\d,]+)", lower)
            if mm:
                try:
                    rules["limits"]["room_rent_limit_per_day"][key] = int(mm.group(1).replace(',', ''))
                    break
                except Exception:
                    pass
    for item in ["diapers", "toiletries", "sanitary", "registration"]:
        if item in lower:
            rules["exclusions"]["items"].append(item)
    mm = re.search(r"cataract[^\n]*?(?:limit|cap|per\s*eye)\s*[:\-]?\s*(?:rs\.?|₹)?\s*([\d,]+)", lower)
    if mm:
        try:
            rules.setdefault("limits", {}).setdefault("sub_limits", {})["cataract_per_eye"] = int(mm.group(1).replace(',', ''))
        except Exception:
            pass
    mm = re.search(r"ambulance[^\n]*?(?:charge|limit|cap)\s*[:\-]?\s*(?:rs\.?|₹)?\s*([\d,]+)", lower)
    if mm:
        try:
            rules.setdefault("limits", {}).setdefault("sub_limits", {})["ambulance_charges"] = int(mm.group(1).replace(',', ''))
        except Exception:
            pass
    return rules


def write_yaml(out_dir: str, company: str, product: str, data: dict):
    os.makedirs(out_dir, exist_ok=True)
    fname = f"{to_filename(company)}_{to_filename(product)}.yml"
    path = os.path.join(out_dir, fname)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
    return path


def main():
    parser = argparse.ArgumentParser(description="Scrape IRDAI Health Insurance Products")
    parser.add_argument("--url", default=IRDAI_URL, help="IRDAI products URL")
    parser.add_argument("--insurer", help="Filter to a specific insurer/company name")
    parser.add_argument("--out", default=DEFAULT_OUT_DIR, help="Output directory for YAML files")
    parser.add_argument("--dry-run", action="store_true", help="Do not write files; just print summary")
    parser.add_argument("--page-urls", nargs="*", help="Additional page URLs for pagination")
    parser.add_argument("--with-pdf", action="store_true", help="Download product PDFs and extract rules heuristically")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of products processed (0 = all)")
    args = parser.parse_args()

    companies = []
    urls = [args.url] + (args.page_urls or [])
    for u in urls:
        try:
            html = fetch_page(u)
            companies.extend(parse_products(html))
            time.sleep(0.5)
        except Exception:
            continue

    total_products = 0
    written = []
    pdf_dir = os.path.join(os.path.dirname(DEFAULT_OUT_DIR), "data", "irdai_pdfs")

    for entry in companies:
        company = normalize_text(entry["company"])
        if args.insurer and args.insurer.lower() not in company.lower():
            continue
        for p in entry.get("products", []):
            product = normalize_text(p["name"])
            if not product:
                continue
            total_products += 1
            meta = {k: v for k, v in p.items() if k != "name"}
            data = build_yaml(company, product, meta=meta)
            if args.with_pdf and p.get("pdf_url"):
                pdf_path = download_pdf(p["pdf_url"], out_dir=pdf_dir)
                if pdf_path:
                    txt = extract_text_from_pdf(pdf_path)
                    parsed = parse_rules_from_text(txt)
                    if parsed.get("limits"):
                        data.setdefault("limits", {}).update(parsed["limits"])
                    if parsed.get("payables_rules"):
                        data.setdefault("payables_rules", {}).update(parsed["payables_rules"])
                    if parsed.get("exclusions"):
                        ex = data.setdefault("exclusions", {"items": [], "diseases": []})
                        ex["items"] = sorted(set(ex.get("items", []) + parsed["exclusions"].get("items", [])))
                        ex["diseases"] = sorted(set(ex.get("diseases", []) + parsed["exclusions"].get("diseases", [])))
            if args.dry_run:
                meta_str = ", ".join([f"{k}={v}" for k, v in meta.items() if v])
                print(f"DRY-RUN: {company} -> {product}{(' ('+meta_str+')') if meta_str else ''}")
                if args.limit and total_products >= args.limit:
                    break
            else:
                path = write_yaml(args.out, company, product, data)
                written.append(path)
                time.sleep(0.2)  # Polite pacing
                if args.limit and len(written) >= args.limit:
                    break

    print(f"Found products: {total_products}")
    if not args.dry_run:
        print(f"Wrote YAML files: {len(written)}")
        for p in written[:10]:
            print(f" - {p}")


if __name__ == "__main__":
    main()
