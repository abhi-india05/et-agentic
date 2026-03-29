from __future__ import annotations

import json
from typing import Any, Dict, Optional

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from backend.agents.guardrails import parse_llm_json
from backend.config.settings import settings
from backend.llm.client import get_llm_client
from backend.memory.vector_store import get_vector_store
from backend.models.schemas import ProspectingOutput
from backend.tools.scraping_tool import enrich_company
from backend.utils.helpers import build_agent_response, generate_id
from backend.utils.logger import get_logger, record_audit

logger = get_logger("prospecting_agent")


def _get_openai_client():
    return get_llm_client()


@retry(
    stop=stop_after_attempt(settings.max_retries + 1),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type((ValueError, RuntimeError)),
    reraise=True,
)
def _call_llm_for_leads(prompt: str) -> ProspectingOutput:
    client = _get_openai_client()
    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=1200,
    )
    return parse_llm_json(response.choices[0].message.content or "", ProspectingOutput)


def _fallback_prospecting(company: str, enriched: Dict[str, Any]) -> ProspectingOutput:
    leads = enriched.get("leads", [])[:2]
    return ProspectingOutput(
        leads=[
            {
                "name": lead.get("name", "Unknown Lead"),
                "title": lead.get("title", "Revenue Leader"),
                "company": company,
                "email": lead.get("email"),
                "linkedin": lead.get("linkedin"),
                "score": lead.get("score", 0.55),
                "signals": lead.get("signals", []),
                "pain_points": ["Pipeline visibility", "Revenue predictability"],
                "why_prioritized": "Fallback enrichment selected this lead from available firmographic data.",
            }
            for lead in leads
        ],
        company_summary=f"{company} appears to be a viable revenue intelligence prospect.",
        recommended_approach="Lead with revenue visibility, churn prevention, and pipeline risk reduction outcomes.",
        icp_fit_score=0.58,
    )


def run_prospecting_agent(
    company: str,
    industry: str,
    company_size: str,
    session_id: str,
    notes: str = "",
    user_id: str = None,
) -> Dict[str, Any]:
    if not user_id:
        raise ValueError("user_id is required")
        
    logger.info("prospecting_agent_start", company=company, session_id=session_id)
    memory = get_vector_store()
    namespace = user_id

    try:
        enriched = enrich_company(company, industry)
        prior_context = memory.get_context_for_company(company, namespace=namespace)
        prompt = f"""You are an expert B2B sales prospecting agent.

Company: {company}
Industry: {industry}
Size: {company_size}
Notes: {notes}

Enriched Data:
{json.dumps(enriched, indent=2)}

Prior Interaction Context:
{prior_context}

Identify the top 2 decision-makers most likely to champion a revenue intelligence platform.

Return ONLY JSON with:
{{
  \"leads\": [
    {{
      \"name\": \"Full Name\",
      \"title\": \"Job Title\",
      \"company\": \"{company}\",
      \"email\": \"email@company.com\",
      \"linkedin\": \"https://linkedin.com/in/profile\",
      \"score\": 0.81,
      \"signals\": [\"signal 1\"],
      \"pain_points\": [\"pain 1\"],
      \"why_prioritized\": \"reason\"
    }}
  ],
  \"company_summary\": \"brief summary\",
  \"recommended_approach\": \"how to approach\",
  \"icp_fit_score\": 0.78
}}"""

        parsed = _call_llm_for_leads(prompt)
    except Exception as exc:
        logger.warning("prospecting_llm_failed", company=company, error=str(exc))
        enriched = enrich_company(company, industry)
        parsed = _fallback_prospecting(company, enriched)

    memory.add_document(
        doc_id=generate_id("prospect"),
        content=f"Prospected {company}: {parsed.company_summary}",
        metadata={"company": company, "agent": "prospecting", "session_id": session_id, "user_id": user_id or ""},
        namespace=namespace,
    )

    confidence = float(parsed.icp_fit_score or 0.55)
    result = build_agent_response(
        status="success",
        data=parsed.model_dump(),
        reasoning=f"Identified {len(parsed.leads)} qualified leads for {company}. ICP fit: {confidence:.0%}.",
        confidence=confidence,
        agent_name="prospecting_agent",
        tools_used=["scraping_tool", "vector_memory", "llm"],
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
