import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import StateGraph, END

from backend.config.settings import settings
from backend.agents.prospecting_agent import run_prospecting_agent
from backend.agents.digital_twin_agent import run_digital_twin_agent
from backend.agents.outreach_agent import run_outreach_agent
from backend.agents.deal_intelligence_agent import run_deal_intelligence_agent
from backend.agents.crm_auditor_agent import run_crm_auditor_agent
from backend.agents.churn_agent import run_churn_agent
from backend.agents.action_agent import run_action_agent
from backend.agents.explainability_agent import run_explainability_agent
from backend.agents.failure_recovery import run_failure_recovery, get_recovery_engine
from backend.utils.helpers import generate_session_id, now_iso
from backend.utils.logger import get_logger, record_audit

logger = get_logger("orchestrator")

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="revops_agent")


class OrchestratorState(TypedDict):
    session_id: str
    task_type: str
    input_data: Dict[str, Any]
    agent_outputs: Dict[str, Any]
    completed_agents: List[str]
    failed_agents: List[str]
    escalated: bool
    final_output: Optional[Dict[str, Any]]
    error_log: List[str]


def _safe_get_confidence(output: Dict[str, Any]) -> float:
    try:
        return float(output.get("confidence", 0.0))
    except (TypeError, ValueError):
        return 0.0


def _update_state(
    state: OrchestratorState,
    agent_name: str,
    result: Dict[str, Any],
) -> OrchestratorState:
    
    new_state = dict(state)
    new_state["agent_outputs"] = {**state["agent_outputs"], agent_name: result}

    status = result.get("status", "failure")
    if status in ("success",):
        new_state["completed_agents"] = state["completed_agents"] + [agent_name]
    else:
        new_state["failed_agents"] = state["failed_agents"] + [agent_name]
        err = result.get("error") or result.get("reasoning", "unknown error")
        new_state["error_log"] = state["error_log"] + [f"{agent_name}: {str(err)[:120]}"]

    return new_state



def orchestrator_node(state: OrchestratorState) -> OrchestratorState:
    logger.info("orchestrator_routing", task_type=state["task_type"], session_id=state["session_id"])
    record_audit(
        session_id=state["session_id"],
        agent_name="orchestrator",
        action="route_task",
        input_summary=f"Task: {state['task_type']}",
        output_summary="Routing to agent pipeline",
        status="success",
        reasoning=f"Orchestrating {state['task_type']} workflow",
        confidence=1.0,
    )
    return state


def prospecting_node(state: OrchestratorState) -> OrchestratorState:
    inp = state["input_data"]
    result = get_recovery_engine().execute_with_recovery(
        task_name="prospecting_agent",
        task_fn=run_prospecting_agent,
        task_args={
            "company": inp.get("company", ""),
            "industry": inp.get("industry", ""),
            "company_size": inp.get("size", ""),
            "session_id": state["session_id"],
            "notes": inp.get("notes", ""),
        },
        session_id=state["session_id"],
    )
    return _update_state(state, "prospecting_agent", result)


def digital_twin_node(state: OrchestratorState) -> OrchestratorState:
    prospect_out = state["agent_outputs"].get("prospecting_agent", {})
    leads = prospect_out.get("data", {}).get("leads", [])
    company = state["input_data"].get("company", "")
    industry = state["input_data"].get("industry", "")

    prospect_confidence = _safe_get_confidence(prospect_out)
    if prospect_confidence < settings.confidence_threshold and not leads:
        logger.warning(
            "digital_twin_skipped",
            reason="low_prospecting_confidence",
            confidence=prospect_confidence,
        )
        leads = [{
            "name": "Key Decision Maker",
            "title": "VP of Revenue",
            "company": company,
            "email": f"contact@{company.lower().replace(' ', '')}.com",
            "pain_points": ["revenue predictability", "pipeline visibility"],
            "signals": ["growth stage company"],
            "score": 0.5,
        }]

    result = get_recovery_engine().execute_with_recovery(
        task_name="digital_twin_agent",
        task_fn=run_digital_twin_agent,
        task_args={
            "leads": leads,
            "company": company,
            "industry": industry,
            "session_id": state["session_id"],
        },
        session_id=state["session_id"],
    )
    return _update_state(state, "digital_twin_agent", result)


def outreach_node(state: OrchestratorState) -> OrchestratorState:
    prospect_out = state["agent_outputs"].get("prospecting_agent", {})
    twin_out = state["agent_outputs"].get("digital_twin_agent", {})
    leads = prospect_out.get("data", {}).get("leads", [])
    twins = twin_out.get("data", {}).get("twin_profiles", [])
    company = state["input_data"].get("company", "")
    product_name = state["input_data"].get("product_name", "")
    product_description = state["input_data"].get("product_description", "")

    result = get_recovery_engine().execute_with_recovery(
        task_name="outreach_agent",
        task_fn=run_outreach_agent,
        task_args={
            "leads": leads,
            "twin_profiles": twins,
            "company": company,
            "product_name": product_name,
            "product_description": product_description,
            "session_id": state["session_id"],
        },
        session_id=state["session_id"],
    )
    return _update_state(state, "outreach_agent", result)


def deal_intelligence_node(state: OrchestratorState) -> OrchestratorState:
    inp = state["input_data"]
    result = get_recovery_engine().execute_with_recovery(
        task_name="deal_intelligence_agent",
        task_fn=run_deal_intelligence_agent,
        task_args={
            "deal_ids": inp.get("deal_ids"),
            "inactivity_threshold": inp.get("inactivity_threshold_days", 10),
            "session_id": state["session_id"],
        },
        session_id=state["session_id"],
    )
    return _update_state(state, "deal_intelligence_agent", result)


def crm_auditor_node(state: OrchestratorState) -> OrchestratorState:
    result = get_recovery_engine().execute_with_recovery(
        task_name="crm_auditor_agent",
        task_fn=run_crm_auditor_agent,
        task_args={"session_id": state["session_id"]},
        session_id=state["session_id"],
    )
    return _update_state(state, "crm_auditor_agent", result)


def churn_node(state: OrchestratorState) -> OrchestratorState:
    inp = state["input_data"]
    result = get_recovery_engine().execute_with_recovery(
        task_name="churn_agent",
        task_fn=run_churn_agent,
        task_args={
            "account_ids": inp.get("account_ids"),
            "top_n": inp.get("top_n", 3),
            "session_id": state["session_id"],
        },
        session_id=state["session_id"],
    )
    return _update_state(state, "churn_agent", result)


def action_execution_node(state: OrchestratorState) -> OrchestratorState:
    task_type = state["task_type"]
    action_type, payload = "send_sequences", {}

    if task_type == "cold_outreach" and not state["input_data"].get("auto_send", False):
        skipped = {
            "status": "success",
            "data": {
                "action_type": "send_sequences",
                "executed_actions": [],
                "total_actions": 0,
                "emails_sent": 0,
                "crm_updates": 0,
                "auto_send": False,
                "message": "Auto-send disabled. Sequences are ready for human review and manual send.",
                "timestamp": now_iso(),
            },
            "reasoning": "Skipped automatic email sending because auto_send=false.",
            "confidence": 1.0,
            "agent_name": "action_agent",
        }
        return _update_state(state, "action_agent", skipped)

    if task_type == "cold_outreach":
        sequences = state["agent_outputs"].get("outreach_agent", {}).get("data", {}).get("sequences", [])
        action_type, payload = "send_sequences", {"sequences": sequences}

    elif task_type == "risk_detection":
        risks = state["agent_outputs"].get("deal_intelligence_agent", {}).get("data", {}).get("risks", [])
        high_risks = [r for r in risks if r.get("risk_level") in ("critical", "high")]
        action_type, payload = "risk_followup", {"risks": high_risks[:5]}

    elif task_type == "churn_prediction":
        churn_risks = state["agent_outputs"].get("churn_agent", {}).get("data", {}).get("top_churn_risks", [])
        action_type, payload = "retention_outreach", {"churn_risks": churn_risks}

    result = get_recovery_engine().execute_with_recovery(
        task_name="action_agent",
        task_fn=run_action_agent,
        task_args={
            "action_type": action_type,
            "payload": payload,
            "session_id": state["session_id"],
        },
        session_id=state["session_id"],
    )
    return _update_state(state, "action_agent", result)


def explainability_node(state: OrchestratorState) -> OrchestratorState:
    result = get_recovery_engine().execute_with_recovery(
        task_name="explainability_agent",
        task_fn=run_explainability_agent,
        task_args={
            "session_id": state["session_id"],
            "agent_outputs": state["agent_outputs"],
            "task_type": state["task_type"],
        },
        session_id=state["session_id"],
    )
    return _update_state(state, "explainability_agent", result)


def failure_recovery_node(state: OrchestratorState) -> OrchestratorState:
    if not state["failed_agents"]:
        return state

    failed = state["failed_agents"][-1]
    result = run_failure_recovery(
        failed_agent=failed,
        session_id=state["session_id"],
        agent_outputs=state["agent_outputs"],
    )
    new_state = dict(state)
    new_state["agent_outputs"] = {**state["agent_outputs"], "failure_recovery": result}
    new_state["escalated"] = result.get("data", {}).get("escalated", False)
    return new_state


def finalize_node(state: OrchestratorState) -> OrchestratorState:
    session_id = state["session_id"]
    task_type = state["task_type"]
    explain_out = state["agent_outputs"].get("explainability_agent", {})
    action_out = state["agent_outputs"].get("action_agent", {})

    final_output = {
        "session_id": session_id,
        "task_type": task_type,
        "status": "completed" if not state["failed_agents"] else "completed_with_errors",
        "completed_agents": state["completed_agents"],
        "failed_agents": state["failed_agents"],
        "error_log": state["error_log"],
        "escalated": state["escalated"],
        "agent_outputs": state["agent_outputs"],
        "explanation": explain_out.get("data", {}),
        "actions_taken": action_out.get("data", {}),
        "impact_metrics": _compute_impact_metrics(state),
        "completed_at": now_iso(),
    }

    record_audit(
        session_id=session_id,
        agent_name="orchestrator",
        action="finalize",
        input_summary=f"Task: {task_type}",
        output_summary=(
            f"Completed. "
            f"{len(state['completed_agents'])} agents succeeded, "
            f"{len(state['failed_agents'])} failed."
        ),
        status="success",
        reasoning=f"Workflow '{task_type}' complete.",
        confidence=0.95,
    )

    new_state = dict(state)
    new_state["final_output"] = final_output
    return new_state



def _route_after_actions(state: OrchestratorState) -> str:
    return "failure_recovery" if state["failed_agents"] else "explainability"


def _compute_impact_metrics(state: OrchestratorState) -> Dict[str, Any]:
    metrics: Dict[str, Any] = {}
    out = state["agent_outputs"]

    if "prospecting_agent" in out:
        metrics["leads_identified"] = len(out["prospecting_agent"].get("data", {}).get("leads", []))

    if "outreach_agent" in out:
        seqs = out["outreach_agent"].get("data", {}).get("sequences", [])
        metrics["email_sequences_created"] = len(seqs)
        metrics["total_emails_crafted"] = len(seqs) * 3

    if "deal_intelligence_agent" in out:
        d = out["deal_intelligence_agent"].get("data", {})
        metrics["deals_at_risk"] = d.get("total_at_risk", 0)
        metrics["critical_deals"] = d.get("critical_count", 0)

    if "churn_agent" in out:
        d = out["churn_agent"].get("data", {})
        metrics["churn_risks_identified"] = len(d.get("top_churn_risks", []))
        metrics["arr_at_risk"] = d.get("total_arr_at_risk", 0)

    if "action_agent" in out:
        d = out["action_agent"].get("data", {})
        metrics["emails_sent"] = d.get("emails_sent", 0)
        metrics["crm_updates"] = d.get("crm_updates", 0)

    return metrics



def _build_outreach_graph():
    g = StateGraph(OrchestratorState)
    g.add_node("orchestrator", orchestrator_node)
    g.add_node("prospecting", prospecting_node)
    g.add_node("digital_twin", digital_twin_node)
    g.add_node("outreach", outreach_node)
    g.add_node("action_execution", action_execution_node)
    g.add_node("crm_auditor", crm_auditor_node)
    g.add_node("failure_recovery", failure_recovery_node)
    g.add_node("explainability", explainability_node)
    g.add_node("finalize", finalize_node)

    g.set_entry_point("orchestrator")
    g.add_edge("orchestrator", "prospecting")
    g.add_edge("prospecting", "digital_twin")
    g.add_edge("digital_twin", "outreach")
    g.add_edge("outreach", "action_execution")
    g.add_edge("action_execution", "crm_auditor")
    g.add_conditional_edges(
        "crm_auditor",
        _route_after_actions,
        {"failure_recovery": "failure_recovery", "explainability": "explainability"},
    )
    g.add_edge("failure_recovery", "explainability")
    g.add_edge("explainability", "finalize")
    g.add_edge("finalize", END)
    return g.compile()


def _build_risk_graph():
    g = StateGraph(OrchestratorState)
    g.add_node("orchestrator", orchestrator_node)
    g.add_node("deal_intelligence", deal_intelligence_node)
    g.add_node("crm_auditor", crm_auditor_node)
    g.add_node("action_execution", action_execution_node)
    g.add_node("failure_recovery", failure_recovery_node)
    g.add_node("explainability", explainability_node)
    g.add_node("finalize", finalize_node)

    g.set_entry_point("orchestrator")
    g.add_edge("orchestrator", "deal_intelligence")
    g.add_edge("deal_intelligence", "crm_auditor")
    g.add_edge("crm_auditor", "action_execution")
    g.add_conditional_edges(
        "action_execution",
        _route_after_actions,
        {"failure_recovery": "failure_recovery", "explainability": "explainability"},
    )
    g.add_edge("failure_recovery", "explainability")
    g.add_edge("explainability", "finalize")
    g.add_edge("finalize", END)
    return g.compile()


def _build_churn_graph():
    g = StateGraph(OrchestratorState)
    g.add_node("orchestrator", orchestrator_node)
    g.add_node("churn", churn_node)
    g.add_node("action_execution", action_execution_node)
    g.add_node("failure_recovery", failure_recovery_node)
    g.add_node("explainability", explainability_node)
    g.add_node("finalize", finalize_node)

    g.set_entry_point("orchestrator")
    g.add_edge("orchestrator", "churn")
    g.add_edge("churn", "action_execution")
    g.add_conditional_edges(
        "action_execution",
        _route_after_actions,
        {"failure_recovery": "failure_recovery", "explainability": "explainability"},
    )
    g.add_edge("failure_recovery", "explainability")
    g.add_edge("explainability", "finalize")
    g.add_edge("finalize", END)
    return g.compile()



_GRAPHS: Dict[str, Any] = {}


def _get_graph(task_type: str):
    if task_type not in _GRAPHS:
        builders = {
            "cold_outreach": _build_outreach_graph,
            "risk_detection": _build_risk_graph,
            "churn_prediction": _build_churn_graph,
        }
        if task_type not in builders:
            raise ValueError(f"Unknown task type: '{task_type}'. Valid: {list(builders)}")
        _GRAPHS[task_type] = builders[task_type]()
        logger.info("graph_compiled", task_type=task_type)
    return _GRAPHS[task_type]



async def run_orchestrator(
    task_type: str,
    input_data: Dict[str, Any],
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    
    if not session_id:
        session_id = generate_session_id()

    logger.info("orchestrator_start", task_type=task_type, session_id=session_id)

    initial_state: OrchestratorState = {
        "session_id": session_id,
        "task_type": task_type,
        "input_data": input_data,
        "agent_outputs": {},
        "completed_agents": [],
        "failed_agents": [],
        "escalated": False,
        "final_output": None,
        "error_log": [],
    }

    try:
        graph = _get_graph(task_type)

        loop = asyncio.get_event_loop()
        final_state = await loop.run_in_executor(
            _executor,
            graph.invoke,
            initial_state,
        )

        result = final_state.get("final_output") or {}
        logger.info(
            "orchestrator_complete",
            session_id=session_id,
            task_type=task_type,
            completed=len(final_state.get("completed_agents", [])),
            failed=len(final_state.get("failed_agents", [])),
        )
        return result

    except Exception as e:
        logger.error("orchestrator_fatal", error=str(e), session_id=session_id, exc_info=True)
        record_audit(
            session_id=session_id,
            agent_name="orchestrator",
            action="fatal_error",
            input_summary=f"Task: {task_type}",
            output_summary=f"FATAL: {str(e)[:120]}",
            status="failure",
            reasoning=str(e),
            confidence=0.0,
        )
        return {
            "session_id": session_id,
            "task_type": task_type,
            "status": "error",
            "error": str(e),
            "completed_agents": [],
            "failed_agents": [],
            "agent_outputs": {},
            "impact_metrics": {},
            "completed_at": now_iso(),
        }