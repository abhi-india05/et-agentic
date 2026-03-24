import json
from typing import Any, Dict

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from backend.config.settings import settings
from backend.tools.scraping_tool import enrich_company
from backend.memory.vector_store import get_vector_store
from backend.utils.helpers import build_agent_response, generate_id, safe_json_loads, extract_json_from_text
from backend.utils.logger import get_logger, record_audit

logger = get_logger("prospecting_agent")


def _get_openai_client():
    from openai import OpenAI
    return OpenAI(api_key=settings.openai_api_key)


@retry(
    stop=stop_after_attempt(settings.max_retries + 1),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type((ValueError, RuntimeError)),
    reraise=True,
)
def _call_llm_for_leads(prompt: str) -> Dict[str, Any]:
    
    client = _get_openai_client()
    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=1200,
    )
    raw = response.choices[0].message.content

    parsed = safe_json_loads(raw) or extract_json_from_text(raw)
    if not parsed or "leads" not in parsed:
        raise ValueError(f"LLM returned unparseable response: {raw[:150]}")

    return parsed


def run_prospecting_agent(
    company: str,
    industry: str,
    company_size: str,
    session_id: str,
    notes: str = "",
) -> Dict[str, Any]:
    logger.info("prospecting_agent_start", company=company, session_id=session_id)

    try:
        enriched = enrich_company(company, industry)
        memory = get_vector_store()
        prior_context = memory.get_context_for_company(company)

        prompt = f"""You are an expert B2B sales prospecting agent.

Company: {company}
Industry: {industry}
Size: {company_size}
Notes: {notes}

Enriched Data:
{json.dumps(enriched, indent=2)}

Prior Interaction Context:
{prior_context}

Identify the TOP 2 decision-makers most likely to champion a B2B SaaS revenue intelligence platform.

Return ONLY this JSON, no markdown:
{{
  "leads": [
    {{
      "name": "Full Name",
      "title": "Job Title",
      "company": "{company}",
      "email": "email@domain.com",
      "linkedin": "https://linkedin.com/in/profile",
      "score": 0.85,
      "why_prioritized": "reason",
      "pain_points": ["pain 1", "pain 2"],
      "signals": ["signal 1"]
    }}
  ],
  "company_summary": "Brief assessment",
  "recommended_approach": "How to approach",
  "icp_fit_score": 0.78
}}"""

        parsed = _call_llm_for_leads(prompt)

        memory.add_document(
            doc_id=generate_id("prospect"),
            content=f"Prospected {company}: {parsed.get('company_summary', '')}",
            metadata={"company": company, "agent": "prospecting", "session_id": session_id},
        )

        confidence = float(parsed.get("icp_fit_score", 0.75))
        result = build_agent_response(
            status="success",
            data=parsed,
            reasoning=(
                f"Identified {len(parsed.get('leads', []))} qualified leads for {company}. "
                f"ICP fit: {confidence:.0%}"
            ),
            confidence=confidence,
            agent_name="prospecting_agent",
        )

        record_audit(
            session_id=session_id,
            agent_name="prospecting_agent",
            action="identify_leads",
            input_summary=f"Company: {company}, Industry: {industry}",
            output_summary=f"Found {len(parsed.get('leads', []))} leads, confidence={confidence:.2f}",
            status="success",
            reasoning=result["reasoning"],
            confidence=confidence,
        )
        return result

    except Exception as e:
        logger.error("prospecting_agent_failed", company=company, error=str(e))
        record_audit(
            session_id=session_id,
            agent_name="prospecting_agent",
            action="identify_leads",
            input_summary=f"Company: {company}",
            output_summary=f"FAILED: {str(e)[:100]}",
            status="failure",
        )
        return build_agent_response(
            status="failure",
            data={},
            reasoning=f"Prospecting failed after retries: {str(e)}",
            confidence=0.0,
            agent_name="prospecting_agent",
            error=str(e),
        )