import json
import os
import copy
from typing import Any, Dict, List, Optional

from backend.utils.logger import get_logger
from backend.utils.helpers import now_iso, days_since

logger = get_logger("crm_tool")

_BASE = os.path.dirname(__file__)
CRM_DATA_PATH = os.path.join(_BASE, "../data/sample_crm.json")
USAGE_DATA_PATH = os.path.join(_BASE, "../data/usage_data.json")

_crm_cache: Optional[List[Dict]] = None
_usage_cache: Optional[List[Dict]] = None
_updates: Dict[str, Dict] = {}


def _load_crm_data() -> List[Dict]:
    global _crm_cache
    if _crm_cache is None:
        try:
            path = os.path.abspath(CRM_DATA_PATH)
            with open(path, "r", encoding="utf-8") as f:
                _crm_cache = json.load(f)
            logger.info("crm_data_loaded", count=len(_crm_cache))
        except Exception as e:
            logger.error("crm_load_failed", error=str(e))
            _crm_cache = []
    return _crm_cache


def _load_usage_data() -> List[Dict]:
    global _usage_cache
    if _usage_cache is None:
        try:
            path = os.path.abspath(USAGE_DATA_PATH)
            with open(path, "r", encoding="utf-8") as f:
                _usage_cache = json.load(f)
        except Exception as e:
            logger.error("usage_load_failed", error=str(e))
            _usage_cache = []
    return _usage_cache


def get_all_accounts() -> List[Dict]:
    accounts = _load_crm_data()
    result = []
    for acc in accounts:
        merged = copy.deepcopy(acc)       # Fix: deep copy prevents mutation of cache
        if acc["account_id"] in _updates:
            merged.update(_updates[acc["account_id"]])
        result.append(merged)
    return result


def get_account_by_id(account_id: str) -> Optional[Dict]:
    for acc in get_all_accounts():
        if acc["account_id"] == account_id:
            return acc
    return None


def get_accounts_by_stage(stage: str) -> List[Dict]:
    return [a for a in get_all_accounts() if a.get("stage", "").lower() == stage.lower()]


def get_at_risk_deals(inactivity_days: int = 10) -> List[Dict]:
    
    at_risk = []
    for acc in get_all_accounts():         # get_all_accounts() already returns copies
        if acc.get("stage") in ["Closed Won", "Closed Lost"]:
            continue
        days = days_since(acc.get("last_activity", ""))
        if days >= inactivity_days:
            acc["days_inactive"] = days    # Safe: mutating a copy
            at_risk.append(acc)
    return sorted(at_risk, key=lambda x: x.get("days_inactive", 0), reverse=True)


def get_usage_data(account_id: str) -> Optional[Dict]:
    for u in _load_usage_data():
        if u["account_id"] == account_id:
            return dict(u)
    return None


def get_all_usage_data() -> List[Dict]:
    return [dict(u) for u in _load_usage_data()]


def update_deal_stage(account_id: str, new_stage: str, notes: str = "") -> Dict:
    if account_id not in _updates:
        _updates[account_id] = {}
    _updates[account_id].update({
        "stage": new_stage,
        "last_updated": now_iso(),
        "notes": notes,
    })
    logger.info("deal_stage_updated", account_id=account_id, stage=new_stage)
    return {"success": True, "account_id": account_id, "new_stage": new_stage, "timestamp": now_iso()}


def log_activity(account_id: str, activity_type: str, description: str) -> Dict:
    if account_id not in _updates:
        _updates[account_id] = {}
    _updates[account_id].update({
        "last_activity": now_iso(),
        "last_activity_type": activity_type,
        "last_activity_desc": description,
    })
    logger.info("activity_logged", account_id=account_id, type=activity_type)
    return {"success": True, "account_id": account_id, "activity_type": activity_type, "timestamp": now_iso()}


def add_new_lead(lead_data: Dict) -> Dict:
    global _crm_cache
    if _crm_cache is None:
        _load_crm_data()
    assert _crm_cache is not None

    new_account = {
        "account_id": f"acc_{len(_crm_cache) + 100:03d}",
        "company": lead_data.get("company", "Unknown"),
        "contact_name": lead_data.get("name", "Unknown"),
        "email": lead_data.get("email", ""),
        "deal_value": lead_data.get("deal_value", 0),
        "stage": "Prospecting",
        "last_activity": now_iso(),
        "days_in_stage": 0,
        "arr": 0,
        "health_score": 50,
        "open_tickets": 0,
        "logins_last_30_days": 0,
        "nps_score": 0,
        "industry": lead_data.get("industry", "Unknown"),
        "employee_count": lead_data.get("employee_count", 0),
    }
    _crm_cache.append(new_account)
    logger.info("lead_added", account_id=new_account["account_id"])
    return new_account


def get_pipeline_stats() -> Dict:
    accounts = get_all_accounts()
    stages: Dict[str, Dict] = {}
    total_value = 0.0
    for acc in accounts:
        stage = acc.get("stage", "Unknown")
        if stage not in stages:
            stages[stage] = {"count": 0, "total_value": 0.0}
        stages[stage]["count"] += 1
        val = acc.get("deal_value", 0)
        stages[stage]["total_value"] += val
        if stage != "Closed Lost":
            total_value += val
    return {
        "stages": stages,
        "total_pipeline_value": total_value,
        "total_accounts": len(accounts),
        "timestamp": now_iso(),
    }


def search_accounts(query: str) -> List[Dict]:
    q = query.lower()
    return [
        a for a in get_all_accounts()
        if q in a.get("company", "").lower()
        or q in a.get("contact_name", "").lower()
        or q in a.get("industry", "").lower()
    ]