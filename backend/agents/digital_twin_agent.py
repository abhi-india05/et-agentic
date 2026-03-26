import json
from typing import Any, Dict, List

from tenacity import retry, stop_after_attempt, wait_exponential

from backend.config.settings import settings
from backend.llm.client import get_llm_client
from backend.memory.vector_store import get_vector_store
from backend.utils.helpers import build_agent_response, generate_id, safe_json_loads
from backend.utils.logger import get_logger, record_audit

logger = get_logger("digital_twin_agent")
client = get_llm_client()


@retry(stop=stop_after_attempt(settings.max_retries + 1), wait=wait_exponential(min=1, max=4))
def run_digital_twin_agent(
    leads: List[Dict[str, Any]],
    company: str,
    industry: str,
    session_id: str,
) -> Dict[str, Any]:
    logger.info("Digital twin agent starting", company=company, session_id=session_id)

    try:
        memory = get_vector_store()
        prior_context = memory.get_context_for_company(company)

        twin_profiles = []
        for lead in leads[:2]:
            prompt = f"""You are a Buyer Digital Twin simulation engine for B2B sales.

Simulate the internal decision-making process of this buyer:

Buyer Profile:
- Name: {lead.get('name')}
- Title: {lead.get('title')}
- Company: {company}
- Industry: {industry}
- Known Pain Points: {lead.get('pain_points', [])}
- Signals: {lead.get('signals', [])}

Prior Context: {prior_context}

Simulate this buyer's likely responses, objections, and decision factors when approached about a Revenue Intelligence & Sales Automation platform.

Return a JSON object:
{{
  "buyer_name": "{lead.get('name')}",
  "buyer_title": "{lead.get('title')}",
  "buying_style": "consensus_builder | champion | blocker | evaluator",
  "primary_motivations": ["motivation 1", "motivation 2"],
  "top_objections": [
    {{"objection": "text", "severity": "high|medium|low", "counter_strategy": "how to handle"}}
  ],
  "decision_criteria": ["criterion 1", "criterion 2", "criterion 3"],
  "likely_questions": ["question 1", "question 2"],
  "emotional_triggers": ["trigger 1", "trigger 2"],
  "risk_perception": "high | medium | low",
  "estimated_decision_timeline": "X weeks",
  "recommended_tone": "consultative | challenger | value-focused | technical",
  "opening_hook": "Best opening line for this specific buyer",
  "confidence_score": 0.82
}}

Return ONLY valid JSON.
"""
            response = client.chat.completions.create(
                model=settings.openai_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=1000,
            )

            raw = response.choices[0].message.content
            parsed = safe_json_loads(raw)
            if parsed:
                twin_profiles.append(parsed)
            else:
                twin_profiles.append({
                    "buyer_name": lead.get("name"),
                    "buyer_title": lead.get("title"),
                    "error": "Failed to parse twin profile",
                    "confidence_score": 0.3,
                })

        avg_confidence = sum(
            p.get("confidence_score", 0.5) for p in twin_profiles
        ) / max(len(twin_profiles), 1)

        memory.add_document(
            doc_id=generate_id("twin"),
            content=f"Digital twin profiles for {company}: {[p.get('buyer_name') for p in twin_profiles]}",
            metadata={"company": company, "agent": "digital_twin", "session_id": session_id},
        )

        result = build_agent_response(
            status="success",
            data={"twin_profiles": twin_profiles, "company": company},
            reasoning=f"Simulated {len(twin_profiles)} buyer personas for {company}. "
                      f"Key insight: primary buying style is {twin_profiles[0].get('buying_style', 'unknown') if twin_profiles else 'N/A'}",
            confidence=avg_confidence,
            agent_name="digital_twin_agent",
        )

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

        logger.info("Digital twin agent completed", twins=len(twin_profiles))
        return result

    except Exception as e:
        logger.error("Digital twin agent failed", error=str(e))
        record_audit(
            session_id=session_id,
            agent_name="digital_twin_agent",
            action="simulate_buyers",
            input_summary=f"Company: {company}",
            output_summary="FAILED",
            status="failure",
        )
        return build_agent_response(
            status="failure",
            data={},
            reasoning=f"Digital twin simulation failed: {str(e)}",
            confidence=0.0,
            agent_name="digital_twin_agent",
            error=str(e),
        )
