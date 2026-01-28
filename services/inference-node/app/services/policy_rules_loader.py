"""
Policy Rules Loader
Loads policy master definitions (admissibility conditions, exclusions, limits)
from YAML files in the Policy Rules directory.
"""
import os
import yaml
from typing import Dict, Optional


POLICY_RULES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "Policy Rules"
)


def _normalize(s: Optional[str]) -> str:
    if not s:
        return ""
    return s.strip().lower().replace("_", " ")


def load_all_policy_files() -> Dict[str, Dict]:
    """Load all YAML policy files in the Policy Rules directory."""
    rules = {}
    if not os.path.isdir(POLICY_RULES_DIR):
        return rules

    for fname in os.listdir(POLICY_RULES_DIR):
        if fname.endswith(".yml") or fname.endswith(".yaml"):
            fpath = os.path.join(POLICY_RULES_DIR, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                    # Key by company + product
                    company = _normalize(data.get("company"))
                    product = _normalize(data.get("product"))
                    if company and product:
                        rules[f"{company}::{product}"] = data
            except Exception:
                # Skip malformed files
                continue
    return rules


_CACHE = None


def load_policy_rules(company: Optional[str], product: Optional[str]) -> Optional[Dict]:
    """
    Load policy rules for a given company and product. Returns None if not found.
    """
    global _CACHE
    if _CACHE is None:
        _CACHE = load_all_policy_files()

    key = f"{_normalize(company)}::{_normalize(product)}"
    return _CACHE.get(key)
