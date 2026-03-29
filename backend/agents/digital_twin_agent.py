from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.memory.vector_store import get_vector_store
from backend.models.schemas import DigitalTwinProfileOutput
from backend.utils.helpers import build_agent_response, generate_id
from backend.utils.logger import get_logger, record_audit

logger = get_logger("digital_twin_agent")


def _terminal_log(level: str, message: str) -> None:
    print(f"[BACKEND][digital_twin_agent][{level.upper()}] {message}")


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _snippet(value: str, max_len: int = 120) -> str:
    compact = " ".join(value.split())
    if len(compact) <= max_len:
        return compact
    return compact[: max_len - 3].rstrip() + "..."


def _derive_buying_style(role: str) -> str:
    role_l = role.lower()
    if any(keyword in role_l for keyword in ["founder", "owner", "director", "head"]):
        return "champion"
    if any(keyword in role_l for keyword in ["vp", "chief", "cfo", "cto", "ceo"]):
        return "consensus_builder"
    if any(keyword in role_l for keyword in ["analyst", "engineer", "manager"]):
        return "evaluator"
    return "evaluator"


def _derive_motivations(text: str) -> List[str]:
    motivations: List[str] = []
    lowered = text.lower()
    mapping = {
        "revenue": "Commercial predictability",
        "pipeline": "Pipeline clarity",
        "forecast": "Forecast confidence",
        "operations": "Operational consistency",
        "analytics": "Data-backed decision making",
        "automation": "Execution efficiency",
        "customer": "Customer continuity",
        "retention": "Retention outcomes",
    }
    for keyword, value in mapping.items():
        if keyword in lowered:
            motivations.append(value)
    if not motivations:
        motivations.append("Role-aligned execution clarity")
    return motivations[:3]


def _build_grounded_twin(lead: Dict[str, Any], company: str) -> DigitalTwinProfileOutput:
    role = _safe_text(lead.get("role") or lead.get("title")) or "Professional"
    headline = _safe_text(lead.get("headline"))
    about = _safe_text(lead.get("about"))
    activity = _safe_text(lead.get("activity"))
    combined = " ".join([role, headline, about, activity]).strip()

    buying_style = _derive_buying_style(role)
    motivations = _derive_motivations(combined)

    top_objections = [
        {
            "objection": "Need clear relevance to the priorities visible in the profile.",
            "severity": "medium",
            "counter_strategy": "Map the message to observed profile signals and avoid generic claims.",
        }
    ]
    if not headline and not about and not activity:
        top_objections[0]["severity"] = "high"
        top_objections[0]["objection"] = "Limited public context available to evaluate relevance."

    decision_criteria = ["Evidence grounded in observed profile context", "Clear next step with low commitment"]
    if "data" in combined.lower() or "analytics" in combined.lower():
        decision_criteria.append("Traceable metrics or measurable outcomes")

    likely_questions: List[str] = []
    if headline:
        likely_questions.append(f"How does this relate to: '{_snippet(headline, 90)}'?" )
    if activity:
        likely_questions.append(f"Can you connect this to: '{_snippet(activity, 90)}'?" )
    if not likely_questions:
        likely_questions.append("Can you show why this is relevant to my current focus?")

    opening_hook = ""
    if activity:
        opening_hook = f"I noticed in your profile activity: {_snippet(activity, 100)}"
    elif headline:
        opening_hook = f"Your profile headline stood out: {_snippet(headline, 100)}"
    else:
        opening_hook = f"I saw your role as {role} at {company}."

    populated = sum(bool(value) for value in [role, headline, about, activity])
    confidence = round(min(0.9, 0.35 + (0.12 * populated)), 2)

    return DigitalTwinProfileOutput(
        buyer_name=_safe_text(lead.get("name")) or "Unknown",
        buyer_title=role,
        buying_style=buying_style,
        primary_motivations=motivations,
        top_objections=top_objections,
        decision_criteria=decision_criteria,
        likely_questions=likely_questions,
        emotional_triggers=["Clarity", "Control"],
        risk_perception="high" if populated <= 1 else "medium",
        estimated_decision_timeline="2-4 weeks" if buying_style in {"champion", "consensus_builder"} else "4-8 weeks",
        recommended_tone="technical" if "engineer" in role.lower() else "consultative",
        opening_hook=opening_hook,
        confidence_score=confidence,
    )


def _fallback_twin(lead: Dict[str, Any]) -> DigitalTwinProfileOutput:
    return DigitalTwinProfileOutput(
        buyer_name=lead.get("name", "Unknown"),
        buyer_title=lead.get("title", "Revenue Leader"),
        buying_style="evaluator",
        primary_motivations=["Profile-grounded relevance"],
        top_objections=[
            {
                "objection": "Insufficient profile context to evaluate fit.",
                "severity": "high",
                "counter_strategy": "Use only explicitly observable profile details before proposing any value mapping.",
            }
        ],
        decision_criteria=["Grounded evidence", "Low-friction next step"],
        likely_questions=["What profile evidence are you using for this outreach?"],
        emotional_triggers=["Clarity"],
        risk_perception="high",
        estimated_decision_timeline="unknown",
        recommended_tone="consultative",
        opening_hook="I want to keep this grounded to what is visible on your profile.",
        confidence_score=0.35,
    )


def run_digital_twin_agent(
    leads: List[Dict[str, Any]],
    company: str,
    industry: str,
    session_id: str,
    user_id: str,
    product_context: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    if not user_id:
        raise ValueError("user_id is required")

    logger.info("digital_twin_agent_start", company=company, session_id=session_id)
    memory = get_vector_store()
    namespace = user_id
    _ = industry
    _ = product_context

    twin_profiles: List[Dict[str, Any]] = []
    for lead in leads[:2]:
        try:
            twin_profiles.append(_build_grounded_twin(lead, company).model_dump())
        except Exception as exc:
            logger.warning("digital_twin_grounded_failed", lead=lead.get("name"), error=str(exc))
            _terminal_log("failure", f"Grounded twin generation failed for lead {lead.get('name', 'unknown')}: {exc}")
            twin_profiles.append(_fallback_twin(lead).model_dump())

    avg_confidence = sum(profile.get("confidence_score", 0.5) for profile in twin_profiles) / max(len(twin_profiles), 1)
    memory.add_document(
        doc_id=generate_id("twin"),
        content=f"Digital twin profiles for {company}: {[profile.get('buyer_name') for profile in twin_profiles]}",
        metadata={"company": company, "agent": "digital_twin", "session_id": session_id, "user_id": user_id or ""},
        namespace=namespace,
    )

    result = build_agent_response(
        status="success",
        data={"twin_profiles": twin_profiles, "company": company},
        reasoning=f"Simulated {len(twin_profiles)} buyer personas for {company}.",
        confidence=avg_confidence,
        agent_name="digital_twin_agent",
        tools_used=["vector_memory"],
    )
    _terminal_log("success", f"Generated {len(twin_profiles)} digital twin profiles for {company}")
    record_audit(
        session_id=session_id,
        agent_name="digital_twin_agent",
        action="simulate_buyers",
        input_summary=f"Company: {company}, Leads: {len(leads)}",
        output_summary=f"Simulated {len(twin_profiles)} buyer twins",
        status="success",
        reasoning=result["reasoning"],
        confidence=avg_confidence,
    )
    return result
