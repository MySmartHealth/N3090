"""
Policy metadata versioning utility.
Tracks policy modifications such as family member changes and PPN provider updates.
Data is persisted to a JSON file under Policy Rules so non-code users can inspect/edit.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parents[2]
METADATA_PATH = ROOT_DIR / "Policy Rules" / "policy_metadata_versions.json"


def _normalize(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def _load_metadata() -> Dict:
    if not METADATA_PATH.exists():
        return {}
    try:
        return json.loads(METADATA_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _save_metadata(data: Dict) -> None:
    METADATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    METADATA_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _policy_key(company: str, product: str) -> str:
    return f"{_normalize(company)}::{_normalize(product)}"


def record_change(
    company: str,
    product: str,
    change_type: str,
    details: Dict,
    actor: str = "system"
) -> Dict:
    """Record a generic policy metadata change and increment version."""
    data = _load_metadata()
    key = _policy_key(company, product)
    entry = data.get(key, {
        "company": company,
        "product": product,
        "current_version": 0,
        "history": []
    })

    next_version = entry.get("current_version", 0) + 1
    change_record = {
        "version": next_version,
        "change_type": change_type,
        "details": details,
        "actor": actor,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

    entry.setdefault("history", []).append(change_record)
    entry["current_version"] = next_version
    data[key] = entry
    _save_metadata(data)
    return entry


def record_family_update(
    company: str,
    product: str,
    added_members: Optional[List[str]] = None,
    removed_members: Optional[List[str]] = None,
    actor: str = "system",
    note: Optional[str] = None
) -> Dict:
    """Track family additions/deletions for a policy."""
    details = {
        "added_members": added_members or [],
        "removed_members": removed_members or [],
    }
    if note:
        details["note"] = note
    return record_change(company, product, "family_update", details, actor)


def record_ppn_update(
    company: str,
    product: str,
    network_version: str,
    added_providers: Optional[List[str]] = None,
    removed_providers: Optional[List[str]] = None,
    actor: str = "system",
    note: Optional[str] = None
) -> Dict:
    """Track Preferred Provider Network (PPN) changes."""
    details = {
        "network_version": network_version,
        "added_providers": added_providers or [],
        "removed_providers": removed_providers or [],
    }
    if note:
        details["note"] = note
    return record_change(company, product, "ppn_update", details, actor)


def get_policy_history(company: str, product: str) -> Dict:
    """Return history and current version for a policy."""
    data = _load_metadata()
    return data.get(_policy_key(company, product), {})


def get_current_version(company: str, product: str) -> int:
    return get_policy_history(company, product).get("current_version", 0)


def list_all_policies() -> List[Dict]:
    data = _load_metadata()
    return list(data.values())
