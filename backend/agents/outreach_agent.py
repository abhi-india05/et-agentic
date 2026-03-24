import json
from typing import Any, Dict, List

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.config.settings import settings
from backend.memory.vector_store import get_vector_store
from backend.utils.helpers import build_agent_response, generate_id, safe_json_loads
from backend.utils.logger import get_logger, record_audit

logger = get_logger("outreach_agent")
client = OpenAI(api_key=settings.openai_api_key)


@retry(stop=stop_after_attempt(settings.max_retries + 1), wait=wait_exponential(min=1, max=4))
def generate_email_sequence(
    lead: Dict[str, Any],
    twin_profile: Dict[str, Any],
    company: str,
    session_id: str,
) -> Dict[str, Any]:

    prompt = f"""You are a world-class B2B sales copywriter creating a personalized cold outreach sequence.

Lead Profile:
- Name: {lead.get('name')}
- Title: {lead.get('title')}
- Company: {company}
- Pain Points: {lead.get('pain_points', [])}
- Signals: {lead.get('signals', [])}

Buyer Psychology (Digital Twin Insights):
- Buying Style: {twin_profile.get('buying_style', 'evaluator')}
- Primary Motivations: {twin_profile.get('primary_motivations', [])}
- Top Objections: {[o.get('objection') for o in twin_profile.get('top_objections', [])[:2]]}
- Emotional Triggers: {twin_profile.get('emotional_triggers', [])}
- Recommended Tone: {twin_profile.get('recommended_tone', 'consultative')}
- Opening Hook: {twin_profile.get('opening_hook', '')}

Product: RevOps AI — an autonomous revenue intelligence system that detects deal risks, predicts churn, and automates sales actions.

Create a 3-email cold outreach sequence. Each email must be distinct in angle and timing.

Return a JSON object:
{{
  "lead_name": "{lead.get('name')}",
  "lead_email": "{lead.get('email')}",
  "sequence_id": "seq_{generate_id('seq')}",
  "emails": [
    {{
      "step": 1,
      "send_day": 1,
      "subject": "Email subject line",
      "body": "Full email body (3-4 paragraphs, personalized, conversational)",
      "cta": "Clear call to action",
      "angle": "The strategic angle of this email"
    }},
    {{
      "step": 2,
      "send_day": 4,
      "subject": "Follow-up subject",
      "body": "Follow-up email body (shorter, adds value or social proof)",
      "cta": "Call to action",
      "angle": "Value-add or case study angle"
    }},
    {{
      "step": 3,
      "send_day": 9,
      "subject": "Final touch subject",
      "body": "Final email (short, direct, breaks pattern)",
      "cta": "Final call to action",
      "angle": "Pattern break or FOMO"
    }}
  ],
  "sequence_strategy": "Brief explanation of the overall sequence strategy",
  "predicted_open_rate": 0.34,
  "predicted_reply_rate": 0.12
}}

Return ONLY valid JSON. No markdown.
""".replace("generate_id('seq')", generate_id("seq"))

    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=2000,
    )

    return safe_json_loads(response.choices[0].message.content)


@retry(stop=stop_after_attempt(settings.max_retries + 1), wait=wait_exponential(min=1, max=4))
def run_outreach_agent(
    leads: List[Dict[str, Any]],
    twin_profiles: List[Dict[str, Any]],
    company: str,
    session_id: str,
) -> Dict[str, Any]:
    logger.info("Outreach agent starting", company=company, leads=len(leads), session_id=session_id)

    try:
        sequences = []
        total_predicted_opens = 0
        total_predicted_replies = 0

        for i, lead in enumerate(leads[:2]):
            twin = twin_profiles[i] if i < len(twin_profiles) else {}
            logger.info("Generating sequence", lead=lead.get("name"), step=i + 1)

            sequence = generate_email_sequence(lead, twin, company, session_id)

            if sequence:
                sequences.append(sequence)
                total_predicted_opens += sequence.get("predicted_open_rate", 0)
                total_predicted_replies += sequence.get("predicted_reply_rate", 0)
            else:
                logger.warning("Failed to generate sequence for lead", lead=lead.get("name"))

        n = max(len(sequences), 1)
        avg_open = total_predicted_opens / n
        avg_reply = total_predicted_replies / n

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
                "avg_predicted_open_rate": round(avg_open, 3),
                "avg_predicted_reply_rate": round(avg_reply, 3),
                "company": company,
            },
            reasoning=f"Generated {len(sequences)} personalized 3-email sequences for {company}. "
                      f"Predicted avg open rate: {avg_open:.1%}, reply rate: {avg_reply:.1%}",
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

        logger.info("Outreach agent completed", sequences=len(sequences))
        return result

    except Exception as e:
        logger.error("Outreach agent failed", error=str(e))
        record_audit(
            session_id=session_id,
            agent_name="outreach_agent",
            action="generate_sequences",
            input_summary=f"Company: {company}",
            output_summary="FAILED",
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
