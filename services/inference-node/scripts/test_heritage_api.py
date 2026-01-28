#!/usr/bin/env python3
"""
Smoke checks for Heritage TPA MobileApp API endpoints from the bundled Heritage.zip kit.

Run:
    python3 scripts/test_heritage_api.py

Endpoints (POST, JSON):
- GetClaimsList
- GetEnrollmentDetails
- GetClaimIntimationDetails
- GetMemberECardURL
- GetNetworkHospitalCount
- GetNetworkHospitals

The script uses sample payloads from the API kit and reports HTTP status and JSON shape.
"""
import json
import sys
from typing import Any, Dict, List

import requests

BASE_URL = "http://223.31.103.204/HeritageMobileAppNew/MobileAppAPI.svc"

tests: List[Dict[str, Any]] = [
    {
        "name": "GetClaimsList",
        "url": f"{BASE_URL}/GetClaimsList",
        "payload": {
            "InsCo": "NIC",
            "PolicyNumber": "261300501910006015",
            "FromDate": "01/12/2020",
            "ToDate": "02/12/2020",
            "AuthId": "",
            "EmployeeNumber": "",
            "MemberID": "",
        },
    },
    {
        "name": "GetEnrollmentDetails",
        "url": f"{BASE_URL}/GetEnrollmentDetails",
        "payload": {
            "InsCo": "NIA",
            "PolicyNumber": "51300234200500000001",
            "MemberID": "HHS2.0401671767",
            "EmployeeNumber": "",
            "AuthId": "0",
        },
    },
    {
        "name": "GetClaimIntimationDetails",
        "url": f"{BASE_URL}/GetClaimIntimationDetails",
        "payload": {
            "InsCo": "IBN",
            "PolicyNumber": "25110050201_PNB_NON_DOMI",
            "PolicyID": 5,
            "CardNo": "HHS1.0700269213",
            "InsuredDetailID": 462901,
            "InsuredName": "SOUMEN RAY",
            "EmpID": "11111",
            "ValidFrom": "01/11/2020",
            "ValidTo": "31/10/2021",
            "DOA": "01/11/2020",
            "DOD": "02/11/2020",
            "HospitalID": 3291,
            "Email": "TEST@GMAIL.COM",
            "Mobile": "8100811550",
            "ClaimAmount": "10000.00",
            "Illness": "Fever",
            "Remarks": "TEST_UPDATE",
            "HospitalName": "BAUL MON",
            "Action": "INSERT",
        },
    },
    {
        "name": "GetMemberECardURL",
        "url": f"{BASE_URL}/GetMemberECardURL",
        "payload": {
            "InsCo": "OIC",
            "PolicyNumber": "124800/48/2021/180",
            "EmployeeNumber": "11374",
            "TPAId": "",
            "MemberID": "",
            "AuthId": "",
        },
    },
    {
        "name": "GetNetworkHospitalCount",
        "url": f"{BASE_URL}/GetNetworkHospitalCount",
        "payload": {
            "InsCo": "NIC",
            "AuthId": "0",
            "Count": "true",
            "StartIndex": "0",
            "EndIndex": "0",
        },
    },
    {
        "name": "GetNetworkHospitals",
        "url": f"{BASE_URL}/GetNetworkHospitals",
        "payload": {
            "InsCo": "NIC",
            "AuthId": "0",
            "Count": "false",
            "StartIndex": "1",
            "EndIndex": "2",
        },
    },
]

def main() -> int:
    ok = True
    session = requests.Session()
    headers = {"Content-Type": "application/json"}

    for test in tests:
        name = test["name"]
        url = test["url"]
        payload = test["payload"]
        try:
            resp = session.post(url, json=payload, headers=headers, timeout=20)
            status = resp.status_code
            try:
                body = resp.json()
            except Exception:
                body = resp.text
            print(f"\n{name}: {status}")
            if isinstance(body, dict):
                keys = list(body.keys())
                print(f"  keys: {keys}")
                if "Status" in body and body.get("Status") is False:
                    ok = False
                if status >= 400:
                    ok = False
            else:
                print(f"  body (truncated): {str(body)[:200]}")
                if status >= 400:
                    ok = False
        except Exception as exc:
            ok = False
            print(f"\n{name}: ERROR {exc}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
