from __future__ import annotations

from typing import Any, Dict, List

from backend.agents.insight_agent import evaluate_product_fit, extract_insights
from backend.memory.vector_store import get_vector_store
from backend.models.schemas import EmailSequenceResult
from backend.utils.helpers import build_agent_response, generate_id
from backend.utils.logger import get_logger, record_audit

logger = get_logger("outreach_agent")


_GENERIC_PHRASES = {
    "teams like yours often struggle",
    "just following up",
    "checking in again",
    "worth closing the loop",
    "quick bump",
    "we help companies like yours",
}


def _terminal_log(level: str, message: str) -> None:
    print(f"[BACKEND][outreach_agent][{level.upper()}] {message}")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _snippet(value: str, max_len: int = 120) -> str:
    compact = " ".join(_text(value).split())
    if len(compact) <= max_len:
        return compact
    return compact[: max_len - 3].rstrip() + "..."


def _variant_seed(lead: Dict[str, Any]) -> int:
    raw = f"{_text(lead.get('name'))}|{_text(lead.get('company'))}|{_text(lead.get('role') or lead.get('title'))}"
    return sum(ord(ch) for ch in raw) % 3


def _topic_from_insights(insights: Dict[str, Any]) -> str:
    insight_text = " ".join(
        [
            *(insights.get("explicit_signals", []) or []),
            *(insights.get("inferred_signals", []) or []),
            _text(insights.get("pain_hypothesis")),
        ]
    ).lower()

    topic_map = {
        "revenue": "revenue predictability",
        "pipeline": "pipeline visibility",
        "forecast": "forecast confidence",
        "retention": "retention",
        "operations": "operational consistency",
        "analytics": "decision analytics",
        "automation": "execution efficiency",
        "risk": "risk visibility",
    }
    for keyword, topic in topic_map.items():
        if keyword in insight_text:
            return topic
    return "current priorities"


def _cta(lead: Dict[str, Any], product_fit: Dict[str, Any], tone_hint: str) -> str:
    seed = _variant_seed(lead)
    relevant = bool(product_fit.get("is_relevant"))

    consultative = [
        "Would you be open to a short call to test whether this aligns with your current priorities?",
        "If useful, can we take 12 minutes to see whether this is relevant for your team?",
        "Open to a brief conversation next week to pressure-test fit?",
    ]
    neutral = [
        "If this is off target, what priority should I map to instead?",
        "If I am missing context, what would be the right focus area from your side?",
        "If this does not match your current agenda, I am happy to recalibrate.",
    ]

    if relevant:
        if tone_hint == "technical":
            return [
                "Would a short working session help determine whether this maps to your current workflow?",
                "Can we run a quick relevance check against your current process next week?",
                "Would you be open to reviewing fit in a short technical discussion?",
            ][seed]
        return consultative[seed]
    return neutral[seed]


def _subject(lead: Dict[str, Any], insights: Dict[str, Any]) -> str:
    role = _text(lead.get("role") or lead.get("title")) or "profile"
    company = _text(lead.get("company")) or "your team"
    name = _text(lead.get("name"))
    topic = _topic_from_insights(insights)
    seed = _variant_seed(lead)

    options = [
        f"{company}: note on {topic}",
        f"{role} at {company} - question on {topic}",
        f"{name or role}, quick context on {topic}",
    ]
    return options[seed]


def _validate_grounded_email(
    *,
    body: str,
    role: str,
    company: str,
    product_name: str,
    product_fit: Dict[str, Any],
) -> bool:
    lowered = body.lower()
    for phrase in _GENERIC_PHRASES:
        if phrase in lowered:
            return False

    if role and role.lower() not in lowered:
        return False
    if company and company.lower() not in lowered:
        return False

    if product_name and not product_fit.get("is_relevant", False):
        if product_name.lower() in lowered:
            return False

    return True


def generate_outreach_email(lead: Dict[str, Any], insights: Dict[str, Any], product_context: Dict[str, str]) -> Dict[str, Any]:
    name = _text(lead.get("name")) or "there"
    role = _text(lead.get("role") or lead.get("title")) or "professional"
    company = _text(lead.get("company")) or "your organization"
    headline = _text(lead.get("headline"))
    about = _text(lead.get("about"))
    activity = _text(lead.get("activity"))

    product_name = _text((product_context or {}).get("name"))
    product_description = _text((product_context or {}).get("description"))
    product_fit = evaluate_product_fit(product_context or {}, insights)

    explicit_signals = insights.get("explicit_signals", []) or []
    inferred_signals = insights.get("inferred_signals", []) or []
    pain_hypothesis = _text(insights.get("pain_hypothesis"))

    signal_line = ""
    if explicit_signals:
        signal_line = f"I noticed this profile signal: {_snippet(explicit_signals[0], 140)}."
    elif activity:
        signal_line = f"I noticed from your profile activity: {_snippet(activity, 140)}."
    elif headline:
        signal_line = f"I noticed from your profile headline: {_snippet(headline, 140)}."
    elif about:
        signal_line = f"I noticed from your summary: {_snippet(about, 140)}."
    else:
        signal_line = f"I saw your role as {role} at {company}."

    insight_line = ""
    if pain_hypothesis:
        insight_line = f"My grounded read is that {pain_hypothesis}"
    elif inferred_signals:
        insight_line = f"From that, one inferred signal is: {_snippet(inferred_signals[0], 140)}."
    else:
        insight_line = "I may not have enough profile evidence yet, so I am keeping this tightly scoped."

    product_line = ""
    if product_name and product_fit.get("is_relevant", False):
        capability = _snippet(product_description, 140) if product_description else ""
        if capability:
            product_line = f"{product_name} may be relevant here because {product_fit.get('reason', '').rstrip('.').lower()}. {capability}."
        else:
            product_line = f"{product_name} may be relevant here because {product_fit.get('reason', '').rstrip('.').lower()}."
    else:
        product_line = f"I am not forcing product messaging here because {product_fit.get('reason', 'relevance is not established').rstrip('.').lower()}."

    used_fields: List[str] = []
    for field_name, value in {
        "role": role,
        "company": company,
        "headline": headline,
        "about": about,
        "activity": activity,
    }.items():
        if value:
            used_fields.append(field_name)

    confidence = float(insights.get("confidence") or 0.0)
    fit_confidence = float(product_fit.get("confidence") or 0.0)
    blended_confidence = confidence
    if product_fit.get("is_relevant", False):
        blended_confidence = min(0.98, (0.7 * confidence) + (0.3 * fit_confidence))

    explanation = {
        "used_fields": used_fields,
        "insight": pain_hypothesis or (inferred_signals[0] if inferred_signals else "No strong inferred signal"),
        "reasoning": f"{_text(insights.get('reasoning'))} Product relevance check: {_text(product_fit.get('reason'))}",
        "confidence": round(blended_confidence, 2),
    }

    return {
        "subject": _subject(lead, insights),
        "greeting": f"Hi {name},",
        "signal_line": signal_line,
        "insight_line": insight_line,
        "product_line": product_line,
        "explanation": explanation,
        "product_fit": product_fit,
    }


def run_outreach_agent(
    leads: List[Dict[str, Any]],
    twin_profiles: List[Dict[str, Any]],
    company: str,
    product_context: Dict[str, str],
    session_id: str,
    user_id: str,
) -> Dict[str, Any]:
    if not user_id:
        raise ValueError("user_id is required")

    logger.info("outreach_agent_start", company=company, session_id=session_id)
    memory = get_vector_store()
    namespace = user_id
    sequences: List[Dict[str, Any]] = []

    for index, lead in enumerate(leads[:2]):
        twin = twin_profiles[index] if index < len(twin_profiles) else {}
        tone_hint = _text(twin.get("recommended_tone")) or "consultative"
        lead_id = _text(lead.get("id") or lead.get("lead_id") or lead.get("source_profile"))

        insights = extract_insights(lead)
        generated = generate_outreach_email(lead, insights, product_context)
        cta = _cta(lead, generated["product_fit"], tone_hint)

        role = _text(lead.get("role") or lead.get("title"))
        lead_company = _text(lead.get("company")) or company
        lead_name = _text(lead.get("name")) or "there"

        body = "\n\n".join(
            [
                generated["greeting"],
                f"I am reaching out because your role as {role or 'professional'} at {lead_company} stood out.",
                generated["signal_line"],
                generated["insight_line"],
                generated["product_line"],
                cta,
            ]
        )

        product_name = _text((product_context or {}).get("name"))
        if not _validate_grounded_email(
            body=body,
            role=role,
            company=lead_company,
            product_name=product_name,
            product_fit=generated["product_fit"],
        ):
            _terminal_log("failure", f"Grounding validation failed for lead {lead_name}; applying constrained fallback body")
            body = "\n\n".join(
                [
                    generated["greeting"],
                    f"I saw your role as {role or 'professional'} at {lead_company}.",
                    generated["signal_line"],
                    generated["insight_line"],
                    cta,
                ]
            )

        sequence_id = generate_id("seq")
        confidence = float(generated["explanation"].get("confidence") or 0.0)
        predicted_open = round(min(0.65, max(0.05, 0.12 + (0.35 * confidence))), 4)
        if generated["product_fit"].get("is_relevant", False):
            predicted_reply = round(min(0.35, max(0.01, 0.04 + (0.22 * confidence))), 4)
        else:
            predicted_reply = round(min(0.2, max(0.01, 0.02 + (0.1 * confidence))), 4)

        sequence = EmailSequenceResult(
            lead_id=lead_id or None,
            lead_name=lead_name,
            lead_email=_text(lead.get("email")),
            sequence_id=sequence_id,
            emails=[
                {
                    "step": 1,
                    "send_day": 1,
                    "subject": generated["subject"],
                    "body": body,
                    "email": body,
                    "cta": cta,
                    "angle": f"insight-grounded/{tone_hint}",
                    "explanation": generated["explanation"],
                }
            ],
            sequence_strategy="Insight-first outreach grounded in LinkedIn profile fields with product relevance gating.",
            predicted_open_rate=predicted_open,
            predicted_reply_rate=predicted_reply,
        )
        sequences.append(sequence.model_dump())

    average_open = sum(item.get("predicted_open_rate", 0.0) for item in sequences) / max(len(sequences), 1)
    average_reply = sum(item.get("predicted_reply_rate", 0.0) for item in sequences) / max(len(sequences), 1)

    memory.add_document(
        doc_id=generate_id("outreach"),
        content=f"Grounded outreach generated for {company} from LinkedIn dataset profiles.",
        metadata={"company": company, "agent": "outreach", "session_id": session_id, "user_id": user_id or ""},
        namespace=namespace,
    )

    result = build_agent_response(
        status="success",
        data={
            "sequences": sequences,
            "total_sequences": len(sequences),
            "avg_predicted_open_rate": round(average_open, 4),
            "avg_predicted_reply_rate": round(average_reply, 4),
            "company": company,
            "product_context": product_context,
            "grounding_mode": "linkedin_dataset_only",
        },
        reasoning=(
            f"Generated {len(sequences)} grounded outreach sequence(s) for {company} using "
            "Prospecting -> Digital Twin -> Insight Extraction -> Outreach."
        ),
        confidence=0.82,
        agent_name="outreach_agent",
        tools_used=["vector_memory"],
    )
    _terminal_log("success", f"Generated {len(sequences)} grounded outreach sequence(s) for {company}")
    record_audit(
        session_id=session_id,
        agent_name="outreach_agent",
        action="generate_sequences",
        input_summary=f"Company: {company}, Leads: {len(leads)}",
        output_summary=f"Generated {len(sequences)} grounded sequences",
        status="success",
        reasoning=result["reasoning"],
        confidence=0.82,
    )
    return result
