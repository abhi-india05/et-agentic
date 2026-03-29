from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.memory.vector_store import get_vector_store
from backend.models.schemas import ProspectingOutput
from backend.tools.scraping_tool import enrich_company
from backend.utils.helpers import build_agent_response, generate_id
from backend.utils.logger import get_logger, record_audit

logger = get_logger("prospecting_agent")


def _terminal_log(level: str, message: str) -> None:
    print(f"[BACKEND][prospecting_agent][{level.upper()}] {message}")


def _derive_pain_points(lead: Dict[str, Any]) -> List[str]:
    about_text = str(lead.get("about") or "").lower()
    activity_text = str(lead.get("activity") or "").lower()
    headline_text = str(lead.get("headline") or "").lower()
    combined = " ".join([headline_text, about_text, activity_text])

    pain_points: List[str] = []
    keyword_map = {
        "forecast": "Forecast reliability",
        "pipeline": "Pipeline visibility",
        "retention": "Customer retention",
        "automation": "Process automation",
        "analytics": "Actionable analytics",
        "risk": "Risk detection",
        "operations": "Operational consistency",
    }
    for keyword, label in keyword_map.items():
        if keyword in combined:
            pain_points.append(label)
    return pain_points[:3]


def _build_grounded_prospecting(company: str, enriched: Dict[str, Any]) -> ProspectingOutput:
    raw_leads = list(enriched.get("leads", []))
    raw_leads.sort(key=lambda item: float(item.get("score", 0.0) or 0.0), reverse=True)
    selected = raw_leads[:2]

    mapped_leads = []
    for lead in selected:
        lead_id = str(lead.get("id") or lead.get("lead_id") or generate_id("lead"))
        role = str(lead.get("role") or lead.get("title") or "").strip()
        observed_fields = []
        for field in ["headline", "about", "activity", "linkedin"]:
            if str(lead.get(field) or "").strip():
                observed_fields.append(field)

        mapped_leads.append(
            {
                "id": lead_id,
                "name": lead.get("name", "Unknown Lead"),
                "title": role,
                "role": role,
                "company": lead.get("company") or company,
                "email": lead.get("email") or "",
                "linkedin": lead.get("linkedin") or "",
                "linkedin_url": lead.get("linkedin_url") or lead.get("linkedin") or "",
                "headline": lead.get("headline") or "",
                "about": lead.get("about") or "",
                "activity": lead.get("activity") or "",
                "source_profile": lead.get("source_profile") or "",
                "raw_data": lead.get("raw_data"),
                "score": float(lead.get("score", 0.0) or 0.0),
                "signals": lead.get("signals", []) or [],
                "pain_points": _derive_pain_points(lead),
                "why_prioritized": (
                    f"Selected from LinkedIn dataset using observed fields: {', '.join(observed_fields) if observed_fields else 'role/company match only'}."
                ),
            }
        )

    data_source = enriched.get("data_source") or "LinkedIn dataset"
    if mapped_leads:
        company_summary = (
            f"Matched {len(raw_leads)} LinkedIn profile(s) for '{company}' from '{data_source}'. "
            f"Returning the top {len(mapped_leads)} by completeness score."
        )
        recommended_approach = (
            "Reference only observed profile evidence (headline/about/activity) and avoid assumptions beyond those fields."
        )
    else:
        company_summary = f"No matching LinkedIn profiles were found for '{company}' in the available dataset."
        recommended_approach = "Skip outreach generation until a grounded profile match exists in the LinkedIn dataset."

    icp_fit_score = 0.0
    if mapped_leads:
        icp_fit_score = sum(float(item.get("score", 0.0)) for item in mapped_leads) / len(mapped_leads)

    return ProspectingOutput(
        leads=mapped_leads,
        company_summary=company_summary,
        recommended_approach=recommended_approach,
        icp_fit_score=round(float(icp_fit_score), 4),
    )


def run_prospecting_agent(
    company: str,
    industry: str,
    company_size: str,
    session_id: str,
    notes: str = "",
    product_context: Optional[Dict[str, str]] = None,
    user_id: str = None,
) -> Dict[str, Any]:
    if not user_id:
        raise ValueError("user_id is required")

    _ = company_size
    _ = notes
    _ = product_context

    logger.info("prospecting_agent_start", company=company, session_id=session_id)
    memory = get_vector_store()
    namespace = user_id

    enriched = enrich_company(company, industry)
    parsed = _build_grounded_prospecting(company, enriched)

    memory.add_document(
        doc_id=generate_id("prospect"),
        content=f"Prospected {company}: {parsed.company_summary}",
        metadata={"company": company, "agent": "prospecting", "session_id": session_id, "user_id": user_id or ""},
        namespace=namespace,
    )

    confidence = float(parsed.icp_fit_score or 0.0)
    result = build_agent_response(
        status="success",
        data=parsed.model_dump(),
        reasoning=f"Identified {len(parsed.leads)} grounded lead(s) for {company}. ICP fit: {confidence:.0%}.",
        confidence=confidence,
        agent_name="prospecting_agent",
        tools_used=["scraping_tool", "vector_memory"],
    )
    _terminal_log(
        "success",
        f"Generated {len(parsed.leads)} grounded lead(s) for {company} from {enriched.get('data_source') or 'LinkedIn dataset'}",
    )
    record_audit(
        session_id=session_id,
        agent_name="prospecting_agent",
        action="identify_leads",
        input_summary=f"Company: {company}, Industry: {industry}",
        output_summary=f"Found {len(parsed.leads)} leads, confidence={confidence:.2f}",
        status="success",
        reasoning=result["reasoning"],
        confidence=confidence,
    )
    return result
