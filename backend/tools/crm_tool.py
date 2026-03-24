import json
import os
from typing import Any, Dict, List, Optional
from datetime import datetime

from backend.utils.logger import get_logger
from backend.utils.helpers import now_iso, days_since

logger = get_logger("crm_tool")

CRM_DATA_PATH = os.path.join(os.path.dirname(__file__), "../data/sample_crm.json")
USAGE_DATA_PATH = os.path.join(os.path.dirname(__file__), "../data/usage_data.json")

_crm_cache: Optional[List[Dict]] = None
_usage_cache: Optional[List[Dict]] = None
_updates: Dict[str, Dict] = {}


def _load_crm_data() -> List[Dict]:
    global _crm_cache
    if _crm_cache is None:
        try:
            with open(CRM_DATA_PATH, "r") as f:
                _crm_cache = json.load(f)
        except Exception as e:
            logger.error("Failed to load CRM data", error=str(e))
            _crm_cache = []
    return _crm_cache


def _load_usage_data() -> List[Dict]:
    global _usage_cache
    if _usage_cache is None:
        try:
            with open(USAGE_DATA_PATH, "r") as f:
                _usage_cache = json.load(f)
        except Exception as e:
            logger.error("Failed to load usage data", error=str(e))
            _usage_cache = []
    return _usage_cache


def get_all_accounts() -> List[Dict]:
    accounts = _load_crm_data()
    result = []
    for acc in accounts:
        merged = {**acc}
        if acc["account_id"] in _updates:
            merged.update(_updates[acc["account_id"]])
        result.append(merged)
    return result


def get_account_by_id(account_id: str) -> Optional[Dict]:
    accounts = get_all_accounts()
    for acc in accounts:
        if acc["account_id"] == account_id:
            return acc
    return None


def get_accounts_by_stage(stage: str) -> List[Dict]:
    accounts = get_all_accounts()
    return [a for a in accounts if a.get("stage", "").lower() == stage.lower()]


def get_at_risk_deals(inactivity_days: int = 10) -> List[Dict]:
    accounts = get_all_accounts()
    at_risk = []
    for acc in accounts:
        if acc.get("stage") in ["Closed Won", "Closed Lost"]:
            continue
        days = days_since(acc.get("last_activity", ""))
        if days >= inactivity_days:
            acc["days_inactive"] = days
            at_risk.append(acc)
    return sorted(at_risk, key=lambda x: x.get("days_inactive", 0), reverse=True)


def get_usage_data(account_id: str) -> Optional[Dict]:
    usage = _load_usage_data()
    for u in usage:
        if u["account_id"] == account_id:
            return u
    return None


def get_all_usage_data() -> List[Dict]:
    return _load_usage_data()


def update_deal_stage(account_id: str, new_stage: str, notes: str = "") -> Dict:
    if account_id not in _updates:
        _updates[account_id] = {}
    _updates[account_id]["stage"] = new_stage
    _updates[account_id]["last_updated"] = now_iso()
    _updates[account_id]["notes"] = notes

    logger.info("Deal stage updated", account_id=account_id, new_stage=new_stage)
    return {
        "success": True,
        "account_id": account_id,
        "new_stage": new_stage,
        "timestamp": now_iso(),
    }


def log_activity(account_id: str, activity_type: str, description: str) -> Dict:
    if account_id not in _updates:
        _updates[account_id] = {}
    _updates[account_id]["last_activity"] = now_iso()
    _updates[account_id]["last_activity_type"] = activity_type
    _updates[account_id]["last_activity_desc"] = description

    logger.info(
        "Activity logged",
        account_id=account_id,
        activity_type=activity_type,
    )
    return {
        "success": True,
        "account_id": account_id,
        "activity_type": activity_type,
        "timestamp": now_iso(),
    }


def add_new_lead(lead_data: Dict) -> Dict:
    global _crm_cache
    if _crm_cache is None:
        _load_crm_data()

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
    logger.info("New lead added to CRM", account_id=new_account["account_id"])
    return new_account


def get_pipeline_stats() -> Dict:
    accounts = get_all_accounts()
    stages = {}
    total_value = 0
    for acc in accounts:
        stage = acc.get("stage", "Unknown")
        if stage not in stages:
            stages[stage] = {"count": 0, "total_value": 0}
        stages[stage]["count"] += 1
        stages[stage]["total_value"] += acc.get("deal_value", 0)
        if stage not in ["Closed Lost"]:
            total_value += acc.get("deal_value", 0)

    return {
        "stages": stages,
        "total_pipeline_value": total_value,
        "total_accounts": len(accounts),
        "timestamp": now_iso(),
    }


def search_accounts(query: str) -> List[Dict]:
    accounts = get_all_accounts()
    q = query.lower()
    return [
        a for a in accounts
        if q in a.get("company", "").lower()
        or q in a.get("contact_name", "").lower()
        or q in a.get("industry", "").lower()
    ]
