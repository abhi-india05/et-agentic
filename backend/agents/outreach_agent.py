from __future__ import annotations

from typing import Any, Dict, List, Optional

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from backend.agents.guardrails import parse_llm_json
from backend.config.settings import settings
from backend.llm.client import get_llm_client
from backend.memory.vector_store import get_vector_store
from backend.models.schemas import EmailSequenceResult
from backend.utils.helpers import build_agent_response, generate_id
from backend.utils.logger import get_logger, record_audit

logger = get_logger("outreach_agent")


def _get_openai_client():
    return get_llm_client()


@retry(
    stop=stop_after_attempt(settings.max_retries + 1),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type((ValueError, RuntimeError)),
    reraise=True,
)
def _call_llm_for_sequence(prompt: str) -> EmailSequenceResult:
    client = _get_openai_client()
    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=2000,
    )
    return parse_llm_json(response.choices[0].message.content or "", EmailSequenceResult)


def _fallback_sequence(lead: Dict[str, Any], company: str, product_context: Dict[str, str], sequence_id: str) -> EmailSequenceResult:
    product_line = product_context.get("name") or "RevOps AI"
    value_line = product_context.get("description") or "AI-powered deal risk detection, churn prediction, and revenue workflow automation."
    return EmailSequenceResult(
        lead_name=lead.get("name", "there"),
        lead_email=lead.get("email", ""),
        sequence_id=sequence_id,
        emails=[
            {
                "step": 1,
                "send_day": 1,
                "subject": f"Quick question about {company}'s revenue operations",
                "body": (
                    f"Hi {lead.get('name', 'there')},\n\n"
                    f"I’m reaching out because teams like yours often struggle to spot pipeline risk early enough.\n\n"
                    f"{product_line} helps revenue teams improve forecast confidence and reduce churn by acting on live signals. {value_line}\n\n"
                    "Would a short conversation next week be useful?"
                ),
                "cta": "Reply to schedule a 15-minute call",
                "angle": "relevance",
            },
            {
                "step": 2,
                "send_day": 4,
                "subject": f"Re: revenue visibility at {company}",
                "body": (
                    f"Hi {lead.get('name', 'there')},\n\n"
                    f"Following up with one concrete angle: {product_line} gives teams earlier visibility into stalled deals and churn signals so managers can intervene before revenue slips.\n\n"
                    "Happy to share a short example if helpful."
                ),
                "cta": "Should I send a short example?",
                "angle": "value",
            },
            {
                "step": 3,
                "send_day": 9,
                "subject": "Worth closing the loop?",
                "body": (
                    f"Hi {lead.get('name', 'there')},\n\n"
                    f"If improving predictability is on your roadmap, {product_line} may be worth a look. If not, I can close the loop here.\n\n"
                    "Either way, thanks for reading."
                ),
                "cta": "Open to a quick intro call?",
                "angle": "pattern break",
            },
        ],
        sequence_strategy="Fallback sequence anchored on product value and predictable revenue outcomes.",
        predicted_open_rate=0.23,
        predicted_reply_rate=0.07,
    )


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
        objections = [item.get("objection", "") for item in twin.get("top_objections", [])[:2]]
        sequence_id = generate_id("seq")
        prompt = f"""You are a world-class B2B sales copywriter creating a cold outreach email sequence.

Lead: {lead.get('name')} - {lead.get('title')} at {company}
Pain Points: {lead.get('pain_points', [])}
Signals: {lead.get('signals', [])}
Buyer Motivations: {twin.get('primary_motivations', [])}
Top Objections: {objections}
Recommended Tone: {twin.get('recommended_tone', 'consultative')}
Opening Hook: {twin.get('opening_hook', 'How are you improving forecast confidence this quarter?')}

Use this product context heavily in the messaging:
Product: {product_context.get("name", "Unnamed Product")}
Description: {product_context.get("description", "No product description provided")}

Return ONLY JSON with:
{{
  \"lead_name\": \"{lead.get('name', '')}\",
  \"lead_email\": \"{lead.get('email', '')}\",
  \"sequence_id\": \"{sequence_id}\",
  \"emails\": [
    {{\"step\": 1, \"send_day\": 1, \"subject\": \"subject\", \"body\": \"email\", \"cta\": \"cta\", \"angle\": \"angle\"}},
    {{\"step\": 2, \"send_day\": 4, \"subject\": \"subject\", \"body\": \"email\", \"cta\": \"cta\", \"angle\": \"angle\"}},
    {{\"step\": 3, \"send_day\": 9, \"subject\": \"subject\", \"body\": \"email\", \"cta\": \"cta\", \"angle\": \"angle\"}}
  ],
  \"sequence_strategy\": \"strategy\",
  \"predicted_open_rate\": 0.32,
  \"predicted_reply_rate\": 0.11
}}"""
        try:
            sequence = _call_llm_for_sequence(prompt)
        except Exception as exc:
            logger.warning("outreach_llm_failed", lead=lead.get("name"), error=str(exc))
            sequence = _fallback_sequence(lead, company, product_context, sequence_id)
        sequences.append(sequence.model_dump())

    average_open = sum(item.get("predicted_open_rate", 0.0) for item in sequences) / max(len(sequences), 1)
    average_reply = sum(item.get("predicted_reply_rate", 0.0) for item in sequences) / max(len(sequences), 1)
    memory.add_document(
        doc_id=generate_id("outreach"),
        content=f"Outreach generated for {company} using product context '{product_context.get("name") or 'none'}'.",
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
        },
        reasoning=f"Generated {len(sequences)} personalized 3-email sequences for {company}.",
        confidence=0.79,
        agent_name="outreach_agent",
        tools_used=["vector_memory", "llm"],
    )
    record_audit(
        session_id=session_id,
        agent_name="outreach_agent",
        action="generate_sequences",
        input_summary=f"Company: {company}, Leads: {len(leads)}",
        output_summary=f"Generated {len(sequences)} sequences",
        status="success",
        reasoning=result["reasoning"],
        confidence=0.79,
    )
    return result
