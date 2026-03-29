from __future__ import annotations

from typing import Dict, List, Optional

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from backend.config.settings import settings
from backend.llm.client import get_llm_client
from backend.memory.vector_store import get_vector_store

from backend.tools.crm_tool import get_all_accounts, get_all_usage_data
from backend.utils.helpers import build_agent_response, generate_id
from backend.utils.logger import get_logger, record_audit

logger = get_logger("churn_agent")


def _get_openai_client():
    return get_llm_client()


def compute_churn_score(account: Dict, usage: Dict) -> float:
    weights = {
        "health_score": 0.25,
        "logins": 0.20,
        "feature_adoption": 0.20,
        "api_trend": 0.15,
        "open_tickets": 0.10,
        "renewal_days": 0.10,
    }
    score = 0.0
    health = account.get("health_score", 50)
    score += weights["health_score"] * (1.0 - health / 100.0)
    logins = account.get("logins_last_30_days", 10)
    score += weights["logins"] * max(0.0, 1.0 - logins / 20.0)
    if usage:
        adoption = float(usage.get("feature_adoption", 0.5))
        score += weights["feature_adoption"] * (1.0 - adoption)
        api_trend = float(usage.get("api_calls_trend", 0.0))
        score += weights["api_trend"] * max(0.0, -api_trend)
        tickets = int(usage.get("support_escalations", 0))
        score += weights["open_tickets"] * min(1.0, tickets / 20.0)
        renewal_days = int(usage.get("contract_renewal_days", 365))
        score += weights["renewal_days"] * max(0.0, 1.0 - renewal_days / 180.0)
    return round(min(1.0, max(0.0, score)), 4)


@retry(
    stop=stop_after_attempt(settings.max_retries + 1),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type((RuntimeError, ValueError)),
    reraise=True,
)
def _call_llm_for_retention(prompt: str) -> str:
    client = _get_openai_client()
    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5,
        max_tokens=300,
    )
    text = (response.choices[0].message.content or "").strip()
    if not text:
        raise ValueError("LLM returned empty retention strategy")
    return text


def _generate_retention_strategy(account: Dict, usage: Dict, churn_score: float) -> str:
    feature_adoption_str = f"{usage.get('feature_adoption', 0):.1%}" if usage else "N/A"
    api_trend_str = f"{usage.get('api_calls_trend', 0):+.0%}" if usage else "N/A"
    renewal_str = str(usage.get("contract_renewal_days", "unknown")) if usage else "N/A"
    prompt = f"""You are a Customer Success expert specializing in B2B SaaS churn prevention.

Account: {account.get('company')}
Industry: {account.get('industry', 'N/A')}
ARR: ${account.get('arr', 0):,.0f}
Health Score: {account.get('health_score', 'N/A')}/100
Churn Probability: {churn_score:.1%}
Logins (last 30d): {account.get('logins_last_30_days', 0)}
Open Tickets: {account.get('open_tickets', 0)}
Feature Adoption: {feature_adoption_str}
API Usage Trend: {api_trend_str}
Contract Renewal In: {renewal_str} days


Write a specific, actionable 2-3 sentence retention strategy. Return ONLY the strategy text."""
    try:
        return _call_llm_for_retention(prompt)
    except Exception as exc:
        logger.warning("retention_llm_failed", company=account.get("company"), error=str(exc))
        return (
            "Deploy immediate adoption workshops to reverse churn risk. "
            f"Focus on lifting feature adoption from {feature_adoption_str}, resolving active support pain, and attaching a measurable 30-day success plan."
        )


def run_churn_agent(
    account_ids: Optional[List[str]],
    top_n: int,
    session_id: str,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    logger.info("churn_agent_start", session_id=session_id)
    memory = get_vector_store()
    namespace = user_id or "global"
    accounts = get_all_accounts()
    usage_map = {row["account_id"]: row for row in get_all_usage_data()}
    if account_ids:
        accounts = [account for account in accounts if account.get("account_id") in account_ids]

    active_accounts = [account for account in accounts if account.get("stage") not in ["Closed Lost", "Prospecting"]]
    if not active_accounts:
        result = build_agent_response(
            status="success",
            data={"top_churn_risks": [], "total_analyzed": 0, "total_arr_at_risk": 0},
            reasoning="No active accounts to analyze.",
            confidence=1.0,
            agent_name="churn_agent",
            tools_used=["crm_tool"],
        )
        record_audit(
            session_id=session_id,
            agent_name="churn_agent",
            action="predict_churn",
            input_summary="No active accounts",
            output_summary="No churn risks found",
            status="success",
            confidence=1.0,
        )
        return result

    scored: List[Dict[str, Any]] = []
    for account in active_accounts:
        usage = usage_map.get(account.get("account_id", ""), {})
        churn_score = compute_churn_score(account, usage)
        risk_factors: List[str] = []
        if account.get("health_score", 100) < 40:
            risk_factors.append(f"Low health score ({account.get('health_score')})")
        if account.get("logins_last_30_days", 10) < 5:
            risk_factors.append(f"Very low engagement ({account.get('logins_last_30_days')} logins)")
        if usage and float(usage.get("feature_adoption", 1)) < 0.3:
            risk_factors.append(f"Poor feature adoption ({float(usage.get('feature_adoption', 0)):.0%})")
        if usage and float(usage.get("api_calls_trend", 0)) < -0.5:
            risk_factors.append("Rapidly declining usage")
        if usage and int(usage.get("contract_renewal_days", 365)) < 30:
            risk_factors.append(f"Contract renewal in {usage.get('contract_renewal_days')} days")
        if account.get("open_tickets", 0) > 8:
            risk_factors.append(f"High support burden ({account.get('open_tickets')} tickets)")
        urgency = "critical" if churn_score > 0.7 else "high" if churn_score > 0.5 else "medium" if churn_score > 0.3 else "low"
        scored.append(
            {
                "account_id": account.get("account_id"),
                "company": account.get("company"),
                "arr": account.get("arr", 0),
                "churn_probability": churn_score,
                "risk_factors": risk_factors,
                "urgency": urgency,
                "health_score": account.get("health_score"),
                "contact_name": account.get("contact_name"),
                "contact_email": account.get("email"),
                "industry": account.get("industry"),
                "stage": account.get("stage"),
                "retention_strategy": _generate_retention_strategy(account, usage, churn_score),
            }
        )

    scored.sort(key=lambda item: item["churn_probability"], reverse=True)
    top_risks = scored[:top_n]
    total_arr_at_risk = sum(item["arr"] for item in top_risks)
    average_probability = sum(item["churn_probability"] for item in top_risks) / max(len(top_risks), 1)

    result = build_agent_response(
        status="success",
        data={
            "top_churn_risks": top_risks,
            "total_analyzed": len(active_accounts),
            "top_n": top_n,
            "total_arr_at_risk": total_arr_at_risk,
            "avg_churn_probability": round(average_probability, 4),
            "critical_count": len([risk for risk in top_risks if risk["urgency"] == "critical"]),
        },
        reasoning=f"Analyzed {len(active_accounts)} active accounts. Top {top_n} churn risks identified.",
        confidence=0.87,
        agent_name="churn_agent",
        tools_used=["crm_tool", "llm"],
    )
    memory.add_document(
        doc_id=generate_id("churn"),
        content=f"Churn analysis completed for {len(active_accounts)} accounts.",
        metadata={"agent": "churn", "session_id": session_id, "user_id": user_id or ""},
        namespace=namespace,
    )
    record_audit(
        session_id=session_id,
        agent_name="churn_agent",
        action="predict_churn",
        input_summary=f"Analyzed {len(active_accounts)} accounts",
        output_summary=f"Top {top_n} risks, ${total_arr_at_risk:,.0f} ARR at risk",
        status="success",
        reasoning=result["reasoning"],
        confidence=0.87,
    )
    return result
