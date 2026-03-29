from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from tenacity import retry, stop_after_attempt, wait_exponential

from backend.agents.guardrails import parse_llm_json
from backend.config.settings import settings
from backend.llm.client import get_llm_client
from backend.memory.vector_store import get_vector_store
from backend.models.schemas import DealRisk
from backend.tools.crm_tool import get_at_risk_deals
from backend.tools.scraping_tool import detect_intent_signals
from backend.utils.helpers import build_agent_response, generate_id
from backend.utils.logger import get_logger, record_audit

logger = get_logger("deal_intelligence_agent")


@retry(stop=stop_after_attempt(settings.max_retries + 1), wait=wait_exponential(min=1, max=4))
def analyze_deal_risk(account: Dict[str, Any]) -> DealRisk:
    signals = detect_intent_signals(account.get("company", ""), account)
    prompt = f"""You are an expert deal intelligence analyst.

Account Data:
{json.dumps(account, indent=2)}

External Signals:
{json.dumps(signals, indent=2)}


Return ONLY valid JSON:
{{
  \"deal_id\": \"{account.get('account_id')}\",
  \"company\": \"{account.get('company')}\",
  \"risk_level\": \"critical | high | medium | low\",
  \"risk_score\": 0.85,
  \"risk_signals\": [\"signal\"],
  \"competitor_threat\": true,
  \"competitor_name\": \"Competitor or null\",
  \"deal_velocity\": \"stalled | slow | on_track | accelerating\",
  \"days_inactive\": {account.get('days_inactive', 0)},
  \"recovery_strategy\": \"Specific plan that reflects the product capabilities\",
  \"recommended_actions\": [\"action 1\"],
  \"escalate_to_manager\": true,
  \"predicted_close_probability\": 0.45,
  \"reasoning\": \"Detailed explanation\"
}}"""
    response = get_llm_client().chat.completions.create(
        model=settings.openai_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=1000,
    )
    return parse_llm_json(response.choices[0].message.content or "", DealRisk)


def _fallback_risk(account: Dict[str, Any]) -> DealRisk:
    days_inactive = int(account.get("days_inactive", 0))
    return DealRisk(
        deal_id=account.get("account_id", ""),
        company=account.get("company", "Unknown"),
        risk_level="critical" if days_inactive >= 30 else "high",
        risk_score=0.82 if days_inactive >= 30 else 0.68,
        risk_signals=[f"Inactive for {days_inactive} days", "Buyer engagement is weakening"],
        competitor_threat=False,
        competitor_name=None,
        deal_velocity="stalled",
        days_inactive=days_inactive,
        recovery_strategy=(
            "Demonstrate how the team can surface deal risk earlier. "
            "Re-engage with a focused executive summary and a short working session."
        ),
        recommended_actions=["Send executive follow-up", "Book a recovery workshop", "Share tailored ROI snapshot"],
        escalate_to_manager=days_inactive >= 30,
        predicted_close_probability=0.28,
        reasoning="Rule-based fallback classified the deal as at risk due to inactivity threshold breach.",
    )


def run_deal_intelligence_agent(
    deal_ids: Optional[List[str]],
    inactivity_threshold: int,
    session_id: str,
    user_id: str,
) -> Dict[str, Any]:
    if not user_id:
        raise ValueError("user_id is required")
        
    logger.info("deal_intelligence_agent_start", session_id=session_id)
    memory = get_vector_store()
    namespace = user_id
    at_risk = get_at_risk_deals(inactivity_days=inactivity_threshold, user_id=user_id)
    if deal_ids:
        at_risk = [account for account in at_risk if account.get("account_id") in deal_ids]

    if not at_risk:
        result = build_agent_response(
            status="success",
            data={"risks": [], "total_at_risk": 0, "critical_count": 0},
            reasoning="No deals found matching the risk criteria.",
            confidence=1.0,
            agent_name="deal_intelligence_agent",
            tools_used=["crm_tool", "scraping_tool"],
        )
        record_audit(
            session_id=session_id,
            agent_name="deal_intelligence_agent",
            action="detect_risks",
            input_summary=f"Threshold: {inactivity_threshold} days",
            output_summary="No at-risk deals found",
            status="success",
            confidence=1.0,
        )
        return result

    analyzed: List[Dict[str, Any]] = []
    for account in at_risk[:10]:
        try:
            analyzed.append(analyze_deal_risk(account).model_dump())
        except Exception as exc:
            logger.warning("deal_risk_llm_failed", account_id=account.get("account_id"), error=str(exc))
            analyzed.append(_fallback_risk(account).model_dump())

    analyzed.sort(key=lambda item: item.get("risk_score", 0.0), reverse=True)
    critical_count = len([item for item in analyzed if item.get("risk_level") in {"critical", "high"}])
    memory.add_document(
        doc_id=generate_id("deal_intel"),
        content=f"Deal risk analysis completed for {len(analyzed)} accounts.",
        metadata={"agent": "deal_intelligence", "session_id": session_id, "user_id": user_id or ""},
        namespace=namespace,
    )

    result = build_agent_response(
        status="success",
        data={
            "risks": analyzed,
            "total_at_risk": len(analyzed),
            "critical_count": critical_count,
            "requires_escalation": any(item.get("escalate_to_manager") for item in analyzed),
        },
        reasoning=f"Analyzed {len(analyzed)} at-risk deals. {critical_count} classified as critical/high risk.",
        confidence=0.84,
        agent_name="deal_intelligence_agent",
        tools_used=["crm_tool", "scraping_tool", "vector_memory", "llm"],
    )
    record_audit(
        session_id=session_id,
        agent_name="deal_intelligence_agent",
        action="detect_risks",
        input_summary=f"Threshold: {inactivity_threshold} days, Checked: {len(at_risk)} deals",
        output_summary=f"Found {len(analyzed)} at-risk deals, {critical_count} critical/high",
        status="success",
        reasoning=result["reasoning"],
        confidence=0.84,
    )
    return result
