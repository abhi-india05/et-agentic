import json
from typing import Any, Dict, List, Optional

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.config.settings import settings
from backend.tools.crm_tool import get_at_risk_deals, get_all_accounts
from backend.tools.scraping_tool import detect_intent_signals
from backend.memory.vector_store import get_vector_store
from backend.utils.helpers import build_agent_response, generate_id, safe_json_loads
from backend.utils.logger import get_logger, record_audit

logger = get_logger("deal_intelligence_agent")
client = OpenAI(api_key=settings.openai_api_key)


@retry(stop=stop_after_attempt(settings.max_retries + 1), wait=wait_exponential(min=1, max=4))
def analyze_deal_risk(account: Dict[str, Any], session_id: str) -> Dict[str, Any]:
    signals = detect_intent_signals(account.get("company", ""), account)

    prompt = f"""You are an expert deal intelligence analyst. Analyze this deal for risk signals.

Account Data:
{json.dumps(account, indent=2)}

External Signals:
{json.dumps(signals, indent=2)}

Perform a comprehensive deal risk analysis. Return a JSON object:
{{
  "deal_id": "{account.get('account_id')}",
  "company": "{account.get('company')}",
  "risk_level": "critical | high | medium | low",
  "risk_score": 0.85,
  "risk_signals": [
    "Specific risk signal 1",
    "Specific risk signal 2"
  ],
  "competitor_threat": true | false,
  "competitor_name": "Competitor if detected or null",
  "deal_velocity": "stalled | slow | on_track | accelerating",
  "days_inactive": {account.get('days_inactive', 0)},
  "recovery_strategy": "Specific, actionable recovery plan (2-3 sentences)",
  "recommended_actions": [
    "Specific action 1",
    "Specific action 2",
    "Specific action 3"
  ],
  "escalate_to_manager": true | false,
  "predicted_close_probability": 0.45,
  "reasoning": "Detailed analysis reasoning"
}}

Return ONLY valid JSON.
"""

    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=1000,
    )

    return safe_json_loads(response.choices[0].message.content)


@retry(stop=stop_after_attempt(settings.max_retries + 1), wait=wait_exponential(min=1, max=4))
def run_deal_intelligence_agent(
    deal_ids: Optional[List[str]],
    inactivity_threshold: int,
    session_id: str,
) -> Dict[str, Any]:
    logger.info("Deal intelligence agent starting", session_id=session_id)

    try:
        at_risk = get_at_risk_deals(inactivity_days=inactivity_threshold)

        if deal_ids:
            at_risk = [a for a in at_risk if a.get("account_id") in deal_ids]

        if not at_risk:
            result = build_agent_response(
                status="success",
                data={"risks": [], "total_at_risk": 0, "critical_count": 0},
                reasoning="No deals found matching the risk criteria",
                confidence=1.0,
                agent_name="deal_intelligence_agent",
            )
            record_audit(
                session_id=session_id,
                agent_name="deal_intelligence_agent",
                action="detect_risks",
                input_summary=f"Threshold: {inactivity_threshold} days",
                output_summary="No at-risk deals found",
                status="success",
            )
            return result

        analyzed_risks = []
        critical_count = 0

        for account in at_risk[:10]:
            analysis = analyze_deal_risk(account, session_id)
            if analysis:
                analyzed_risks.append(analysis)
                if analysis.get("risk_level") in ["critical", "high"]:
                    critical_count += 1
            else:
                analyzed_risks.append({
                    "deal_id": account.get("account_id"),
                    "company": account.get("company"),
                    "risk_level": "high",
                    "risk_score": 0.7,
                    "risk_signals": [f"Inactive for {account.get('days_inactive', 0)} days"],
                    "recovery_strategy": "Immediate personal outreach required",
                    "recommended_actions": ["Schedule executive call", "Send value recap"],
                    "escalate_to_manager": account.get("days_inactive", 0) > 30,
                    "predicted_close_probability": 0.3,
                    "reasoning": "Deal flagged due to inactivity threshold breach",
                })

        analyzed_risks.sort(key=lambda x: x.get("risk_score", 0), reverse=True)

        memory = get_vector_store()
        memory.add_document(
            doc_id=generate_id("deal_intel"),
            content=f"Deal risk analysis: {critical_count} critical deals detected. Top risk: {analyzed_risks[0].get('company') if analyzed_risks else 'none'}",
            metadata={"agent": "deal_intelligence", "session_id": session_id},
        )

        result = build_agent_response(
            status="success",
            data={
                "risks": analyzed_risks,
                "total_at_risk": len(analyzed_risks),
                "critical_count": critical_count,
                "requires_escalation": any(r.get("escalate_to_manager") for r in analyzed_risks),
            },
            reasoning=f"Analyzed {len(analyzed_risks)} at-risk deals. {critical_count} classified as critical/high risk. "
                      f"{'Escalation required for manager review.' if critical_count > 0 else 'No immediate escalation needed.'}",
            confidence=0.85,
            agent_name="deal_intelligence_agent",
        )

        record_audit(
            session_id=session_id,
            agent_name="deal_intelligence_agent",
            action="detect_risks",
            input_summary=f"Threshold: {inactivity_threshold} days, Checked: {len(at_risk)} deals",
            output_summary=f"Found {len(analyzed_risks)} at-risk deals, {critical_count} critical",
            status="success",
            reasoning=result["reasoning"],
            confidence=0.85,
        )

        logger.info("Deal intelligence completed", at_risk=len(analyzed_risks), critical=critical_count)
        return result

    except Exception as e:
        logger.error("Deal intelligence agent failed", error=str(e))
        record_audit(
            session_id=session_id,
            agent_name="deal_intelligence_agent",
            action="detect_risks",
            input_summary=f"Threshold: {inactivity_threshold} days",
            output_summary="FAILED",
            status="failure",
        )
        return build_agent_response(
            status="failure",
            data={},
            reasoning=f"Deal intelligence failed: {str(e)}",
            confidence=0.0,
            agent_name="deal_intelligence_agent",
            error=str(e),
        )
