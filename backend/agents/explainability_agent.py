import json
from typing import Any, Dict, List

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.config.settings import settings
from backend.utils.helpers import build_agent_response, safe_json_loads, now_iso
from backend.utils.logger import get_logger, record_audit

logger = get_logger("explainability_agent")
client = OpenAI(api_key=settings.openai_api_key)


@retry(stop=stop_after_attempt(settings.max_retries + 1), wait=wait_exponential(min=1, max=4))
def run_explainability_agent(
    session_id: str,
    agent_outputs: Dict[str, Any],
    task_type: str,
) -> Dict[str, Any]:
    logger.info("Explainability agent starting", session_id=session_id, task_type=task_type)

    try:
        summaries = {}
        for agent_name, output in agent_outputs.items():
            if isinstance(output, dict):
                summaries[agent_name] = {
                    "status": output.get("status"),
                    "reasoning": output.get("reasoning", "")[:300],
                    "confidence": output.get("confidence", 0),
                    "key_data": _extract_key_data(agent_name, output),
                }

        prompt = f"""You are an AI explainability specialist. Generate a clear, human-readable explanation of what the RevOps AI system did and why.

Task Type: {task_type}
Session ID: {session_id}

Agent Summaries:
{json.dumps(summaries, indent=2)}

Generate an explanation report as a JSON object:
{{
  "executive_summary": "2-3 sentence plain-English summary of what happened and the outcome",
  "decision_chain": [
    {{
      "step": 1,
      "agent": "agent_name",
      "decision": "What this agent decided",
      "why": "Why it made this decision",
      "confidence": 0.85,
      "impact": "What effect this had on the workflow"
    }}
  ],
  "key_insights": ["insight 1", "insight 2", "insight 3"],
  "data_sources_used": ["CRM data", "OpenAI GPT-4o", "FAISS memory"],
  "overall_confidence": 0.82,
  "limitations": ["limitation 1"],
  "human_review_recommended": false,
  "human_review_reasons": [],
  "impact_metrics": {{
    "deals_analyzed": 0,
    "emails_generated": 0,
    "revenue_at_risk_identified": 0,
    "actions_taken": 0
  }}
}}

Return ONLY valid JSON.
"""

        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1200,
        )

        explanation = safe_json_loads(response.choices[0].message.content)

        if not explanation:
            explanation = _generate_fallback_explanation(task_type, summaries, session_id)

        needs_review = explanation.get("human_review_recommended", False)
        low_confidence_agents = [
            name for name, s in summaries.items()
            if s.get("confidence", 1.0) < 0.5
        ]
        if low_confidence_agents:
            explanation["human_review_recommended"] = True
            explanation["human_review_reasons"] = explanation.get("human_review_reasons", []) + [
                f"Low confidence from: {', '.join(low_confidence_agents)}"
            ]

        full_explanation = {
            **explanation,
            "session_id": session_id,
            "task_type": task_type,
            "generated_at": now_iso(),
            "agent_count": len(agent_outputs),
            "failed_agents": [
                name for name, s in summaries.items()
                if s.get("status") == "failure"
            ],
        }

        result = build_agent_response(
            status="success",
            data=full_explanation,
            reasoning=explanation.get("executive_summary", "Explanation generated."),
            confidence=explanation.get("overall_confidence", 0.8),
            agent_name="explainability_agent",
        )

        record_audit(
            session_id=session_id,
            agent_name="explainability_agent",
            action="generate_explanation",
            input_summary=f"Task: {task_type}, Agents: {list(agent_outputs.keys())}",
            output_summary=explanation.get("executive_summary", "Explanation complete")[:200],
            status="success",
            reasoning=result["reasoning"],
            confidence=result["confidence"],
        )

        logger.info("Explainability agent completed", session_id=session_id)
        return result

    except Exception as e:
        logger.error("Explainability agent failed", error=str(e))
        record_audit(
            session_id=session_id,
            agent_name="explainability_agent",
            action="generate_explanation",
            input_summary=f"Task: {task_type}",
            output_summary="FAILED",
            status="failure",
        )
        return build_agent_response(
            status="failure",
            data={},
            reasoning=f"Explainability generation failed: {str(e)}",
            confidence=0.0,
            agent_name="explainability_agent",
            error=str(e),
        )


def _extract_key_data(agent_name: str, output: Dict) -> Dict:
    data = output.get("data", {})
    if agent_name == "prospecting_agent":
        return {"leads_found": len(data.get("leads", []))}
    elif agent_name == "digital_twin_agent":
        return {"twins_created": len(data.get("twin_profiles", []))}
    elif agent_name == "outreach_agent":
        return {"sequences_generated": data.get("total_sequences", 0)}
    elif agent_name == "deal_intelligence_agent":
        return {"risks_found": data.get("total_at_risk", 0), "critical": data.get("critical_count", 0)}
    elif agent_name == "churn_agent":
        return {"churn_risks": len(data.get("top_churn_risks", [])), "arr_at_risk": data.get("total_arr_at_risk", 0)}
    elif agent_name == "action_agent":
        return {"emails_sent": data.get("emails_sent", 0), "crm_updates": data.get("crm_updates", 0)}
    return {}


def _generate_fallback_explanation(task_type: str, summaries: Dict, session_id: str) -> Dict:
    successful = [n for n, s in summaries.items() if s.get("status") == "success"]
    failed = [n for n, s in summaries.items() if s.get("status") == "failure"]

    return {
        "executive_summary": f"RevOps AI completed a {task_type} workflow. "
                             f"{len(successful)} agents executed successfully" +
                             (f", {len(failed)} failed." if failed else "."),
        "decision_chain": [
            {"step": i + 1, "agent": name, "decision": s.get("reasoning", "")[:100],
             "why": "Part of automated workflow", "confidence": s.get("confidence", 0.5),
             "impact": "Contributed to overall outcome"}
            for i, (name, s) in enumerate(summaries.items())
        ],
        "key_insights": ["Automated pipeline executed", f"Task type: {task_type}"],
        "data_sources_used": ["CRM data", "OpenAI GPT-4o", "FAISS memory store"],
        "overall_confidence": sum(s.get("confidence", 0) for s in summaries.values()) / max(len(summaries), 1),
        "limitations": ["LLM outputs may require human validation"],
        "human_review_recommended": len(failed) > 0,
        "human_review_reasons": [f"Agents failed: {failed}"] if failed else [],
        "impact_metrics": {"deals_analyzed": 0, "emails_generated": 0, "actions_taken": len(successful)},
    }
