import json
from typing import Any, Dict, List, Optional

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.config.settings import settings
from backend.tools.crm_tool import get_all_accounts, get_usage_data, get_all_usage_data
from backend.utils.helpers import build_agent_response, generate_id, safe_json_loads
from backend.utils.logger import get_logger, record_audit

logger = get_logger("churn_agent")
client = OpenAI(api_key=settings.openai_api_key)


def compute_churn_score(account: Dict, usage: Dict) -> float:
    score = 0.0
    weights = {
        "health_score": 0.25,
        "logins": 0.20,
        "feature_adoption": 0.20,
        "api_trend": 0.15,
        "open_tickets": 0.10,
        "renewal_days": 0.10,
    }

    health = account.get("health_score", 50)
    score += weights["health_score"] * (1 - health / 100)

    logins = account.get("logins_last_30_days", 10)
    login_risk = max(0, 1 - logins / 20)
    score += weights["logins"] * login_risk

    if usage:
        adoption = usage.get("feature_adoption", 0.5)
        score += weights["feature_adoption"] * (1 - adoption)

        api_trend = usage.get("api_calls_trend", 0)
        api_risk = max(0, -api_trend)
        score += weights["api_trend"] * api_risk

        tickets = usage.get("support_escalations", 0)
        ticket_risk = min(1.0, tickets / 20)
        score += weights["open_tickets"] * ticket_risk

        renewal_days = usage.get("contract_renewal_days", 365)
        renewal_risk = max(0, 1 - renewal_days / 180)
        score += weights["renewal_days"] * renewal_risk

    return round(min(1.0, score), 3)


@retry(stop=stop_after_attempt(settings.max_retries + 1), wait=wait_exponential(min=1, max=4))
def generate_retention_strategy(account: Dict, usage: Dict, churn_score: float, session_id: str) -> str:
    prompt = f"""You are a Customer Success expert specializing in churn prevention.

Account: {account.get('company')}
Industry: {account.get('industry')}
ARR: ${account.get('arr', 0):,.0f}
Health Score: {account.get('health_score')}/100
Churn Probability: {churn_score:.1%}
Logins (30d): {account.get('logins_last_30_days')}
Open Tickets: {account.get('open_tickets')}
Feature Adoption: {usage.get('feature_adoption', 0):.1%} if usage else 'N/A'
API Trend: {usage.get('api_calls_trend', 0):.1%} if usage else 'N/A'
Contract Renewal Days: {usage.get('contract_renewal_days', 'N/A')}

Generate a SPECIFIC, actionable retention strategy (2-3 sentences) tailored to this account's exact situation.
Focus on the highest-leverage intervention given their specific risk factors.
Return ONLY the strategy text, no JSON, no labels.
"""

    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5,
        max_tokens=300,
    )
    return response.choices[0].message.content.strip()


@retry(stop=stop_after_attempt(settings.max_retries + 1), wait=wait_exponential(min=1, max=4))
def run_churn_agent(
    account_ids: Optional[List[str]],
    top_n: int,
    session_id: str,
) -> Dict[str, Any]:
    logger.info("Churn prediction agent starting", session_id=session_id)

    try:
        accounts = get_all_accounts()
        all_usage = get_all_usage_data()
        usage_map = {u["account_id"]: u for u in all_usage}

        if account_ids:
            accounts = [a for a in accounts if a.get("account_id") in account_ids]

        active_accounts = [
            a for a in accounts
            if a.get("stage") not in ["Closed Lost", "Prospecting"]
        ]

        scored_accounts = []
        for acc in active_accounts:
            usage = usage_map.get(acc.get("account_id"), {})
            churn_score = compute_churn_score(acc, usage)

            risk_factors = []
            if acc.get("health_score", 100) < 40:
                risk_factors.append(f"Low health score ({acc.get('health_score')})")
            if acc.get("logins_last_30_days", 10) < 5:
                risk_factors.append(f"Very low engagement ({acc.get('logins_last_30_days')} logins)")
            if usage.get("feature_adoption", 1) < 0.3:
                risk_factors.append(f"Poor feature adoption ({usage.get('feature_adoption', 0):.0%})")
            if usage.get("api_calls_trend", 0) < -0.5:
                risk_factors.append("Rapidly declining usage trend")
            if usage.get("contract_renewal_days", 365) < 30:
                risk_factors.append(f"Contract renewal in {usage.get('contract_renewal_days')} days")
            if acc.get("open_tickets", 0) > 8:
                risk_factors.append(f"High support burden ({acc.get('open_tickets')} open tickets)")

            urgency = "critical" if churn_score > 0.7 else "high" if churn_score > 0.5 else "medium" if churn_score > 0.3 else "low"

            scored_accounts.append({
                "account_id": acc.get("account_id"),
                "company": acc.get("company"),
                "arr": acc.get("arr", 0),
                "churn_probability": churn_score,
                "risk_factors": risk_factors,
                "urgency": urgency,
                "health_score": acc.get("health_score"),
                "contact_name": acc.get("contact_name"),
                "contact_email": acc.get("email"),
                "industry": acc.get("industry"),
                "stage": acc.get("stage"),
                "usage": usage,
                "_account": acc,
            })

        scored_accounts.sort(key=lambda x: x["churn_probability"], reverse=True)
        top_risks = scored_accounts[:top_n]

        for risk in top_risks:
            strategy = generate_retention_strategy(
                risk["_account"],
                risk["usage"],
                risk["churn_probability"],
                session_id,
            )
            risk["retention_strategy"] = strategy
            del risk["_account"]
            del risk["usage"]

        total_arr_at_risk = sum(r["arr"] for r in top_risks)
        avg_churn_prob = sum(r["churn_probability"] for r in top_risks) / max(len(top_risks), 1)

        result = build_agent_response(
            status="success",
            data={
                "top_churn_risks": top_risks,
                "total_analyzed": len(active_accounts),
                "top_n": top_n,
                "total_arr_at_risk": total_arr_at_risk,
                "avg_churn_probability": round(avg_churn_prob, 3),
                "critical_count": len([r for r in top_risks if r["urgency"] == "critical"]),
            },
            reasoning=f"Analyzed {len(active_accounts)} accounts. Top {top_n} churn risks identified. "
                      f"${total_arr_at_risk:,.0f} ARR at risk. Highest risk: {top_risks[0].get('company') if top_risks else 'none'} "
                      f"at {top_risks[0].get('churn_probability', 0):.1%}" if top_risks else "No accounts analyzed.",
            confidence=0.87,
            agent_name="churn_agent",
        )

        record_audit(
            session_id=session_id,
            agent_name="churn_agent",
            action="predict_churn",
            input_summary=f"Analyzed {len(active_accounts)} accounts",
            output_summary=f"Top {top_n} churn risks, ${total_arr_at_risk:,.0f} ARR at risk",
            status="success",
            reasoning=result["reasoning"],
            confidence=0.87,
        )

        logger.info("Churn agent completed", top_risks=len(top_risks), arr_at_risk=total_arr_at_risk)
        return result

    except Exception as e:
        logger.error("Churn agent failed", error=str(e))
        record_audit(
            session_id=session_id,
            agent_name="churn_agent",
            action="predict_churn",
            input_summary="All accounts",
            output_summary="FAILED",
            status="failure",
        )
        return build_agent_response(
            status="failure",
            data={},
            reasoning=f"Churn prediction failed: {str(e)}",
            confidence=0.0,
            agent_name="churn_agent",
            error=str(e),
        )
