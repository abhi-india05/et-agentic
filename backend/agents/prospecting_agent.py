import json
from typing import Any, Dict

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.config.settings import settings
from backend.tools.scraping_tool import enrich_company
from backend.memory.vector_store import get_vector_store
from backend.utils.helpers import build_agent_response, generate_id, safe_json_loads
from backend.utils.logger import get_logger, record_audit

logger = get_logger("prospecting_agent")
client = OpenAI(api_key=settings.openai_api_key)


@retry(stop=stop_after_attempt(settings.max_retries + 1), wait=wait_exponential(min=1, max=4))
def run_prospecting_agent(
    company: str,
    industry: str,
    company_size: str,
    session_id: str,
    notes: str = "",
) -> Dict[str, Any]:
    logger.info("Prospecting agent starting", company=company, session_id=session_id)

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

Your task: Identify the TOP 2 decision-makers most likely to be the buying champions for a B2B SaaS revenue intelligence platform.

Return a JSON object with this EXACT structure:
{{
  "leads": [
    {{
      "name": "Full Name",
      "title": "Job Title",
      "company": "{company}",
      "email": "email@company.com",
      "linkedin": "https://linkedin.com/in/profile",
      "score": 0.85,
      "why_prioritized": "Reason this person is the right buyer",
      "pain_points": ["pain 1", "pain 2"],
      "signals": ["signal 1", "signal 2"]
    }}
  ],
  "company_summary": "Brief assessment of the company as a prospect",
  "recommended_approach": "How to approach this account",
  "icp_fit_score": 0.78
}}

Return ONLY valid JSON, no markdown.
"""

        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=1200,
        )

        raw = response.choices[0].message.content
        parsed = safe_json_loads(raw)

        if not parsed:
            raise ValueError(f"Failed to parse LLM response: {raw[:200]}")

        memory.add_document(
            doc_id=generate_id("prospect"),
            content=f"Prospected {company}: {parsed.get('company_summary', '')}",
            metadata={"company": company, "agent": "prospecting", "session_id": session_id},
        )

        result = build_agent_response(
            status="success",
            data=parsed,
            reasoning=f"Identified {len(parsed.get('leads', []))} qualified leads for {company} with ICP fit score {parsed.get('icp_fit_score', 0)}",
            confidence=parsed.get("icp_fit_score", 0.75),
            agent_name="prospecting_agent",
        )

        record_audit(
            session_id=session_id,
            agent_name="prospecting_agent",
            action="identify_leads",
            input_summary=f"Company: {company}, Industry: {industry}",
            output_summary=f"Found {len(parsed.get('leads', []))} leads",
            status="success",
            reasoning=result["reasoning"],
            confidence=result["confidence"],
        )

        logger.info("Prospecting agent completed", company=company, leads=len(parsed.get("leads", [])))
        return result

    except Exception as e:
        logger.error("Prospecting agent failed", error=str(e), company=company)
        record_audit(
            session_id=session_id,
            agent_name="prospecting_agent",
            action="identify_leads",
            input_summary=f"Company: {company}",
            output_summary="FAILED",
            status="failure",
        )
        return build_agent_response(
            status="failure",
            data={},
            reasoning=f"Prospecting failed: {str(e)}",
            confidence=0.0,
            agent_name="prospecting_agent",
            error=str(e),
        )
