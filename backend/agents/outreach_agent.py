import json
from typing import Any, Dict, List

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from backend.config.settings import settings
from backend.llm.client import get_llm_client
from backend.memory.vector_store import get_vector_store
from backend.utils.helpers import build_agent_response, generate_id, safe_json_loads, extract_json_from_text
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
def _call_llm_for_sequence(prompt: str) -> Dict[str, Any]:
    client = _get_openai_client()
    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=2000,
    )
    raw = response.choices[0].message.content
    parsed = safe_json_loads(raw) or extract_json_from_text(raw)
    if not parsed or "emails" not in parsed:
        raise ValueError(f"Unparseable sequence response: {raw[:120]}")
    return parsed


def _generate_sequence_for_lead(
    lead: Dict[str, Any],
    twin: Dict[str, Any],
    company: str,
    sequence_id: str,
    session_id: str,
) -> Dict[str, Any]:

    objections = [o.get("objection", "") for o in twin.get("top_objections", [])[:2]]

    prompt = f"""You are a world-class B2B sales copywriter creating a cold outreach email sequence.

Lead: {lead.get('name')} — {lead.get('title')} at {company}
Pain Points: {lead.get('pain_points', [])}
Signals: {lead.get('signals', [])}

Buyer Psychology:
- Buying Style: {twin.get('buying_style', 'evaluator')}
- Motivations: {twin.get('primary_motivations', [])}
- Top Objections: {objections}
- Emotional Triggers: {twin.get('emotional_triggers', [])}
- Recommended Tone: {twin.get('recommended_tone', 'consultative')}
- Opening Hook: {twin.get('opening_hook', 'How are you tackling revenue efficiency this quarter?')}

Product: RevOps AI — autonomous revenue intelligence that detects deal risks, predicts churn, and executes sales actions.

Create a 3-email cold outreach sequence. Each email must have a distinct angle and timing.

Return ONLY this JSON, no markdown:
{{
  "lead_name": "{lead.get('name')}",
  "lead_email": "{lead.get('email', '')}",
  "sequence_id": "{sequence_id}",
  "emails": [
    {{
      "step": 1,
      "send_day": 1,
      "subject": "subject line",
      "body": "full 3-4 paragraph email body",
      "cta": "clear call to action",
      "angle": "strategic angle name"
    }},
    {{
      "step": 2,
      "send_day": 4,
      "subject": "follow-up subject",
      "body": "shorter follow-up adding value or social proof",
      "cta": "call to action",
      "angle": "value-add or case study"
    }},
    {{
      "step": 3,
      "send_day": 9,
      "subject": "final touch subject",
      "body": "short pattern-break final email",
      "cta": "final call to action",
      "angle": "pattern break or FOMO"
    }}
  ],
  "sequence_strategy": "brief explanation of overall strategy",
  "predicted_open_rate": 0.34,
  "predicted_reply_rate": 0.12
}}"""

    try:
        return _call_llm_for_sequence(prompt)
    except Exception as e:
        logger.warning(
            "sequence_llm_failed",
            lead=lead.get("name"),
            error=str(e),
        )
        return {
            "lead_name": lead.get("name"),
            "lead_email": lead.get("email", ""),
            "sequence_id": sequence_id,
            "emails": [
                {
                    "step": 1, "send_day": 1,
                    "subject": f"Quick question about {company}'s revenue operations",
                    "body": (
                        f"Hi {lead.get('name', 'there')},\n\n"
                        f"I noticed {company} is growing quickly and wanted to reach out directly.\n\n"
                        "We help revenue teams like yours eliminate blind spots in the sales pipeline — "
                        "automatically surfacing at-risk deals and predicting churn before it happens.\n\n"
                        "Worth a 15-minute conversation?\n\nBest,"
                    ),
                    "cta": "Reply to schedule a call",
                    "angle": "Pattern interrupt / relevance",
                },
                {
                    "step": 2, "send_day": 4,
                    "subject": f"Re: Revenue ops at {company}",
                    "body": (
                        f"Hi {lead.get('name', 'there')},\n\n"
                        "Following up on my last note. One of our customers reduced deal slippage by 34% "
                        "in the first 60 days — happy to share the case study.\n\nBest,"
                    ),
                    "cta": "Can I send you the case study?",
                    "angle": "Social proof",
                },
                {
                    "step": 3, "send_day": 9,
                    "subject": "Closing the loop",
                    "body": (
                        f"Hi {lead.get('name', 'there')},\n\n"
                        "I'll keep this brief — if revenue predictability isn't a priority right now, "
                        "totally understand. If it is, I'd love 15 minutes.\n\nBest,"
                    ),
                    "cta": "15 minutes this week?",
                    "angle": "Permission-based close",
                },
            ],
            "sequence_strategy": "Fallback template sequence (LLM unavailable)",
            "predicted_open_rate": 0.25,
            "predicted_reply_rate": 0.08,
        }


def run_outreach_agent(
    leads: List[Dict[str, Any]],
    twin_profiles: List[Dict[str, Any]],
    company: str,
    session_id: str,
) -> Dict[str, Any]:
    logger.info("outreach_agent_start", company=company, leads=len(leads), session_id=session_id)

    try:
        sequences = []

        for i, lead in enumerate(leads[:2]):
            twin = twin_profiles[i] if i < len(twin_profiles) else {}
            seq_id = generate_id("seq")  
            sequence = _generate_sequence_for_lead(lead, twin, company, seq_id, session_id)
            sequences.append(sequence)

        n = max(len(sequences), 1)
        avg_open = sum(s.get("predicted_open_rate", 0) for s in sequences) / n
        avg_reply = sum(s.get("predicted_reply_rate", 0) for s in sequences) / n

        memory = get_vector_store()
        memory.add_document(
            doc_id=generate_id("outreach"),
            content=f"Outreach sequences generated for {company}: {[s.get('lead_name') for s in sequences]}",
            metadata={"company": company, "agent": "outreach", "session_id": session_id},
        )

        result = build_agent_response(
            status="success",
            data={
                "sequences": sequences,
                "total_sequences": len(sequences),
                "avg_predicted_open_rate": round(avg_open, 4),
                "avg_predicted_reply_rate": round(avg_reply, 4),
                "company": company,
            },
            reasoning=(
                f"Generated {len(sequences)} personalized 3-email sequences for {company}. "
                f"Predicted avg open rate: {avg_open:.1%}, reply rate: {avg_reply:.1%}."
            ),
            confidence=0.78,
            agent_name="outreach_agent",
        )

        record_audit(
            session_id=session_id,
            agent_name="outreach_agent",
            action="generate_sequences",
            input_summary=f"Company: {company}, Leads: {len(leads)}",
            output_summary=f"Generated {len(sequences)} email sequences",
            status="success",
            reasoning=result["reasoning"],
            confidence=0.78,
        )
        return result

    except Exception as e:
        logger.error("outreach_agent_failed", error=str(e))
        record_audit(
            session_id=session_id,
            agent_name="outreach_agent",
            action="generate_sequences",
            input_summary=f"Company: {company}",
            output_summary=f"FAILED: {str(e)[:100]}",
            status="failure",
        )
        return build_agent_response(
            status="failure",
            data={},
            reasoning=f"Outreach generation failed: {str(e)}",
            confidence=0.0,
            agent_name="outreach_agent",
            error=str(e),
        )