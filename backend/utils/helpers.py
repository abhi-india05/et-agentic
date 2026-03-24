import uuid
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import hashlib


def generate_session_id() -> str:
    return f"sess_{uuid.uuid4().hex[:12]}"


def generate_id(prefix: str = "id") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def now_iso() -> str:
    return datetime.utcnow().isoformat()


def days_ago(days: int) -> str:
    return (datetime.utcnow() - timedelta(days=days)).isoformat()


def truncate_text(text: str, max_len: int = 200) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def safe_json_loads(text: str) -> Optional[Dict[str, Any]]:
    try:
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return json.loads(text.strip())
    except Exception:
        return None


def extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    import re
    pattern = r'\{[\s\S]*\}'
    match = re.search(pattern, text)
    if match:
        return safe_json_loads(match.group())
    return None


def compute_risk_score(factors: Dict[str, float]) -> float:
    if not factors:
        return 0.0
    total_weight = sum(factors.values())
    if total_weight == 0:
        return 0.0
    return min(1.0, total_weight / len(factors))


def format_email_body(template: str, variables: Dict[str, str]) -> str:
    for key, value in variables.items():
        template = template.replace(f"{{{{{key}}}}}", value)
    return template


def hash_company_name(name: str) -> str:
    return hashlib.md5(name.lower().encode()).hexdigest()[:8]


def parse_date(date_str: str) -> Optional[datetime]:
    formats = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S.%f",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def days_since(date_str: str) -> int:
    dt = parse_date(date_str)
    if not dt:
        return 0
    return (datetime.utcnow() - dt).days


def build_agent_response(
    status: str,
    data: Dict[str, Any],
    reasoning: str,
    confidence: float,
    agent_name: str,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "status": status,
        "data": data,
        "reasoning": reasoning,
        "confidence": confidence,
        "agent_name": agent_name,
        "timestamp": now_iso(),
        "error": error,
    }
