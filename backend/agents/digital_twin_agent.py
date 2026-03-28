from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from tenacity import retry, stop_after_attempt, wait_exponential

from backend.agents.guardrails import parse_llm_json
from backend.config.settings import settings
from backend.llm.client import get_llm_client
from backend.memory.vector_store import get_vector_store
from backend.models.schemas import DigitalTwinProfileOutput
from backend.utils.helpers import build_agent_response, generate_id
from backend.utils.logger import get_logger, record_audit

logger = get_logger("digital_twin_agent")


def _fallback_twin(lead: Dict[str, Any]) -> DigitalTwinProfileOutput:
    return DigitalTwinProfileOutput(
        buyer_name=lead.get("name", "Unknown"),
        buyer_title=lead.get("title", "Revenue Leader"),
        buying_style="evaluator",
        primary_motivations=["Pipeline efficiency", "Forecast accuracy"],
        top_objections=[
            {"objection": "Implementation risk", "severity": "medium", "counter_strategy": "Offer guided rollout and measurable milestones."}
        ],
        decision_criteria=["Time to value", "Ease of adoption", "Measurable revenue impact"],
        likely_questions=["How quickly can we deploy?", "How accurate are the risk signals?"],
        emotional_triggers=["Predictability", "Control"],
        risk_perception="medium",
        estimated_decision_timeline="4-6 weeks",
        recommended_tone="consultative",
        opening_hook="How are you improving forecast confidence this quarter?",
        confidence_score=0.52,
    )


@retry(stop=stop_after_attempt(settings.max_retries + 1), wait=wait_exponential(min=1, max=4))
def _call_llm(prompt: str) -> DigitalTwinProfileOutput:
    response = get_llm_client().chat.completions.create(
        model=settings.openai_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5,
        max_tokens=1000,
    )
    return parse_llm_json(response.choices[0].message.content or "", DigitalTwinProfileOutput)


def run_digital_twin_agent(
    leads: List[Dict[str, Any]],
    company: str,
    industry: str,
    session_id: str,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    logger.info("digital_twin_agent_start", company=company, session_id=session_id)
    memory = get_vector_store()
    namespace = user_id or "global"
    prior_context = memory.get_context_for_company(company, namespace=namespace)

    twin_profiles: List[Dict[str, Any]] = []
    for lead in leads[:2]:
        prompt = f"""You are a Buyer Digital Twin simulation engine for B2B sales.

Buyer Profile:
{json.dumps(lead, indent=2)}

Company: {company}
Industry: {industry}
Prior Context: {prior_context}

Return ONLY valid JSON with:
{{
  \"buyer_name\": \"{lead.get('name', '')}\",
  \"buyer_title\": \"{lead.get('title', '')}\",
  \"buying_style\": \"consensus_builder | champion | blocker | evaluator\",
  \"primary_motivations\": [\"motivation 1\"],
  \"top_objections\": [{{\"objection\": \"text\", \"severity\": \"high|medium|low\", \"counter_strategy\": \"how to handle\"}}],
  \"decision_criteria\": [\"criterion 1\"],
  \"likely_questions\": [\"question 1\"],
  \"emotional_triggers\": [\"trigger 1\"],
  \"risk_perception\": \"high | medium | low\",
  \"estimated_decision_timeline\": \"X weeks\",
  \"recommended_tone\": \"consultative | challenger | value-focused | technical\",
  \"opening_hook\": \"Best opening line\",
  \"confidence_score\": 0.82
}}"""
        try:
            twin_profiles.append(_call_llm(prompt).model_dump())
        except Exception as exc:
            logger.warning("digital_twin_llm_failed", lead=lead.get("name"), error=str(exc))
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
        tools_used=["vector_memory", "llm"],
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
    return result
