from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

_SIGNAL_KEYWORDS = {
    "growth",
    "pipeline",
    "forecast",
    "sales",
    "revenue",
    "customer",
    "retention",
    "operations",
    "analytics",
    "automation",
    "risk",
    "quality",
    "delivery",
    "scale",
    "performance",
}

_INFERENCE_RULES: List[Tuple[Set[str], str, str]] = [
    (
        {"revenue", "sales", "pipeline", "forecast"},
        "Commercial outcomes and predictability are visible priorities.",
        "keeping predictable commercial performance is likely a current pressure.",
    ),
    (
        {"operations", "delivery", "quality", "process"},
        "Operational consistency and execution quality are emphasized.",
        "reducing operational variability may be an active concern.",
    ),
    (
        {"analytics", "data", "insight", "reporting"},
        "Data-backed decision making appears in the profile language.",
        "turning fragmented signals into decision-ready insight may matter.",
    ),
    (
        {"customer", "retention", "support", "experience"},
        "Customer continuity and account health are mentioned or implied.",
        "protecting customer continuity is likely relevant.",
    ),
    (
        {"automation", "productivity", "efficiency", "scale"},
        "Efficiency and scalable execution themes are present.",
        "maintaining throughput without adding process overhead may matter.",
    ),
]


def _norm(value: Optional[str]) -> str:
    return (value or "").strip()


def _tokens(value: str) -> Set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", value.lower()) if len(token) >= 4}


def _sentences(value: str) -> List[str]:
    parts = [part.strip() for part in re.split(r"[\n\r\.\!\?;]+", value) if part.strip()]
    return parts


def _snippet(value: str, max_len: int = 140) -> str:
    compact = re.sub(r"\s+", " ", value).strip()
    if len(compact) <= max_len:
        return compact
    return compact[: max_len - 3].rstrip() + "..."


def extract_insights(lead: dict) -> dict:
    role = _norm(lead.get("role") or lead.get("title"))
    company = _norm(lead.get("company"))
    headline = _norm(lead.get("headline"))
    about = _norm(lead.get("about"))
    activity = _norm(lead.get("activity"))

    used_fields: List[str] = []
    for field_name, field_value in {
        "role": role,
        "company": company,
        "headline": headline,
        "about": about,
        "activity": activity,
    }.items():
        if field_value:
            used_fields.append(field_name)

    explicit_signals: List[str] = []
    for source_name, source_text in (("headline", headline), ("about", about), ("activity", activity)):
        if not source_text:
            continue
        for sentence in _sentences(source_text):
            sentence_tokens = _tokens(sentence)
            if sentence_tokens.intersection(_SIGNAL_KEYWORDS):
                explicit_signals.append(f"{source_name}: {_snippet(sentence)}")
            if len(explicit_signals) >= 4:
                break
        if len(explicit_signals) >= 4:
            break

    if not explicit_signals:
        if headline:
            explicit_signals.append(f"headline: {_snippet(headline)}")
        if activity:
            explicit_signals.append(f"activity: {_snippet(activity)}")

    combined_text = " ".join(part for part in [role, company, headline, about, activity] if part)
    combined_tokens = _tokens(combined_text)

    inferred_signals: List[str] = []
    pain_hypothesis: Optional[str] = None
    for rule_terms, signal_text, pain_text in _INFERENCE_RULES:
        if combined_tokens.intersection(rule_terms):
            inferred_signals.append(signal_text)
            if pain_hypothesis is None:
                pain_hypothesis = pain_text

    populated_count = len([value for value in [role, company, headline, about, activity] if value])
    depth_score = min(1.0, (len(explicit_signals) + len(inferred_signals)) / 6.0)
    confidence = round(min(0.95, 0.18 + (0.11 * populated_count) + (0.42 * depth_score)), 2)

    reasoning = (
        f"Used fields: {', '.join(used_fields) if used_fields else 'none'}. "
        "Explicit signals are verbatim snippets from headline/about/activity. "
        "Inferred signals are keyword-derived only from role/company/headline/about/activity."
    )

    if not explicit_signals and not inferred_signals:
        pain_hypothesis = None

    return {
        "role": role,
        "explicit_signals": explicit_signals,
        "inferred_signals": inferred_signals,
        "pain_hypothesis": pain_hypothesis,
        "confidence": confidence,
        "reasoning": reasoning,
    }


def evaluate_product_fit(product: dict, insights: dict) -> dict:
    product_name = _norm((product or {}).get("name"))
    product_description = _norm((product or {}).get("description"))
    product_text = f"{product_name} {product_description}".strip()

    if not product_text:
        return {
            "is_relevant": False,
            "reason": "No product context provided.",
            "confidence": 0.0,
        }

    insight_text_parts: List[str] = []
    insight_text_parts.extend(insights.get("explicit_signals", []) or [])
    insight_text_parts.extend(insights.get("inferred_signals", []) or [])
    if insights.get("pain_hypothesis"):
        insight_text_parts.append(insights["pain_hypothesis"])
    insight_text = " ".join(insight_text_parts).strip()

    if not insight_text:
        return {
            "is_relevant": False,
            "reason": "Insufficient insight evidence to link product value.",
            "confidence": 0.0,
        }

    product_terms = _tokens(product_text)
    insight_terms = _tokens(insight_text)
    overlap = sorted(product_terms.intersection(insight_terms))

    if not overlap:
        return {
            "is_relevant": False,
            "reason": "No direct term overlap between product context and extracted lead signals.",
            "confidence": 0.21,
        }

    coverage = len(overlap) / max(1, min(len(product_terms), 8))
    confidence = round(min(0.95, 0.45 + (0.5 * coverage)), 2)
    return {
        "is_relevant": True,
        "reason": f"Direct overlap on terms: {', '.join(overlap[:6])}.",
        "confidence": confidence,
    }
