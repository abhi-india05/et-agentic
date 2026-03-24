import uuid
import json
import re
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
    return text[:max_len] + "..." if len(text) > max_len else text


def safe_json_loads(text: str) -> Optional[Dict[str, Any]]:
    
    if not text:
        return None
    try:
        text = text.strip()
        # Strip markdown code fences
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return json.loads(text.strip())
    except (json.JSONDecodeError, ValueError):
        return None


def extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    
    if not text:
        return None
    # Find the outermost {...} block
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        return safe_json_loads(match.group())
    return None


def compute_risk_score(factors: Dict[str, float]) -> float:
    if not factors:
        return 0.0
    values = list(factors.values())
    return round(min(1.0, sum(values) / len(values)), 4)


def format_email_body(template: str, variables: Dict[str, str]) -> str:
    for key, value in variables.items():
        template = template.replace(f"{{{{{key}}}}}", value)
    return template


def hash_company_name(name: str) -> str:
    return hashlib.md5(name.lower().encode()).hexdigest()[:8]


def parse_date(date_str: str) -> Optional[datetime]:
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def days_since(date_str: str) -> int:
    dt = parse_date(date_str)
    if not dt:
        return 0
    return max(0, (datetime.utcnow() - dt).days)


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
        "confidence": round(float(confidence), 4),
        "agent_name": agent_name,
        "timestamp": now_iso(),
        "error": error,
    }
