import json
from typing import Any, Dict, List

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.config.settings import settings
from backend.tools.crm_tool import get_all_accounts, get_pipeline_stats
from backend.utils.helpers import build_agent_response, generate_id, safe_json_loads, days_since
from backend.utils.logger import get_logger, record_audit

logger = get_logger("crm_auditor_agent")
client = OpenAI(api_key=settings.openai_api_key)

STUCK_STAGE_THRESHOLDS = {
    "Discovery": 21,
    "Proposal": 14,
    "Negotiation": 21,
    "Prospecting": 30,
}


def detect_crm_anomalies(accounts: List[Dict]) -> Dict[str, Any]:
    missed_followups = []
    stuck_deals = []
    data_quality_issues = []
    revenue_at_risk = 0

    for acc in accounts:
        stage = acc.get("stage", "")
        days_in_stage = acc.get("days_in_stage", 0)
        last_activity = acc.get("last_activity", "")
        company = acc.get("company", "")
        deal_value = acc.get("deal_value", 0)

        if stage in ["Closed Won", "Closed Lost"]:
            continue

        days_inactive = days_since(last_activity) if last_activity else days_in_stage

        threshold = STUCK_STAGE_THRESHOLDS.get(stage, 30)
        if days_in_stage > threshold:
            stuck_deals.append({
                "account_id": acc.get("account_id"),
                "company": company,
                "stage": stage,
                "days_in_stage": days_in_stage,
                "threshold": threshold,
                "overage_days": days_in_stage - threshold,
                "deal_value": deal_value,
                "severity": "critical" if days_in_stage > threshold * 2 else "high",
            })
            revenue_at_risk += deal_value

        if days_inactive >= 7 and stage not in ["Closed Won", "Closed Lost"]:
            missed_followups.append({
                "account_id": acc.get("account_id"),
                "company": company,
                "contact_name": acc.get("contact_name"),
                "email": acc.get("email"),
                "stage": stage,
                "days_since_contact": days_inactive,
                "deal_value": deal_value,
                "urgency": "high" if days_inactive >= 14 else "medium",
            })

        if not acc.get("email") or not acc.get("contact_name"):
            data_quality_issues.append({
                "account_id": acc.get("account_id"),
                "company": company,
                "issue": "Missing contact email or name",
            })

    return {
        "missed_followups": sorted(missed_followups, key=lambda x: x["days_since_contact"], reverse=True),
        "stuck_deals": sorted(stuck_deals, key=lambda x: x["days_in_stage"], reverse=True),
        "data_quality_issues": data_quality_issues,
        "revenue_at_risk": revenue_at_risk,
    }


@retry(stop=stop_after_attempt(settings.max_retries + 1), wait=wait_exponential(min=1, max=4))
def run_crm_auditor_agent(session_id: str) -> Dict[str, Any]:
    logger.info("CRM auditor agent starting", session_id=session_id)

    try:
        accounts = get_all_accounts()
        pipeline_stats = get_pipeline_stats()
        anomalies = detect_crm_anomalies(accounts)

        audit_summary = {
            "missed_followups": anomalies["missed_followups"],
            "stuck_deals": anomalies["stuck_deals"],
            "data_quality_issues": anomalies["data_quality_issues"],
            "revenue_at_risk": anomalies["revenue_at_risk"],
        }

        prompt = f"""You are a CRM audit specialist. Analyze this CRM audit data and provide strategic recommendations.

Pipeline Stats: {json.dumps(pipeline_stats, indent=2)}
Audit Findings: {json.dumps(audit_summary, indent=2)}

Return a JSON object:
{{
  "audit_score": 72,
  "health_rating": "Fair | Good | Poor | Critical",
  "top_priorities": [
    {{"priority": 1, "action": "Specific action", "impact": "Expected impact", "deals_affected": 3}}
  ],
  "process_gaps": ["gap 1", "gap 2"],
  "immediate_actions": ["action 1", "action 2", "action 3"],
  "revenue_recovery_potential": 450000,
  "recommendations_summary": "Brief overall assessment"
}}

Return ONLY valid JSON.
"""

        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=800,
        )

        recommendations = safe_json_loads(response.choices[0].message.content) or {
            "audit_score": 65,
            "health_rating": "Fair",
            "top_priorities": [],
            "process_gaps": ["Manual follow-up tracking", "Inconsistent stage progression"],
            "immediate_actions": ["Review stuck deals", "Schedule follow-ups"],
            "revenue_recovery_potential": anomalies["revenue_at_risk"],
            "recommendations_summary": "CRM audit complete. Multiple deals require attention.",
        }

        full_data = {
            **anomalies,
            "pipeline_stats": pipeline_stats,
            "recommendations": recommendations,
            "total_accounts_audited": len(accounts),
        }

        result = build_agent_response(
            status="success",
            data=full_data,
            reasoning=f"CRM audit complete. Found {len(anomalies['missed_followups'])} missed follow-ups, "
                      f"{len(anomalies['stuck_deals'])} stuck deals. "
                      f"${anomalies['revenue_at_risk']:,.0f} revenue at risk.",
            confidence=0.90,
            agent_name="crm_auditor_agent",
        )

        record_audit(
            session_id=session_id,
            agent_name="crm_auditor_agent",
            action="audit_crm",
            input_summary=f"Audited {len(accounts)} accounts",
            output_summary=f"{len(anomalies['missed_followups'])} missed followups, {len(anomalies['stuck_deals'])} stuck deals",
            status="success",
            reasoning=result["reasoning"],
            confidence=0.90,
        )

        logger.info("CRM audit completed", missed=len(anomalies["missed_followups"]), stuck=len(anomalies["stuck_deals"]))
        return result

    except Exception as e:
        logger.error("CRM auditor failed", error=str(e))
        record_audit(
            session_id=session_id,
            agent_name="crm_auditor_agent",
            action="audit_crm",
            input_summary="All accounts",
            output_summary="FAILED",
            status="failure",
        )
        return build_agent_response(
            status="failure",
            data={},
            reasoning=f"CRM audit failed: {str(e)}",
            confidence=0.0,
            agent_name="crm_auditor_agent",
            error=str(e),
        )
