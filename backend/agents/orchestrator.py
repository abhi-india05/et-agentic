import json
from typing import Any, Dict, List, Optional, TypedDict, Annotated
from datetime import datetime

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

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


def orchestrator_node(state: OrchestratorState) -> OrchestratorState:
    logger.info(
        "Orchestrator routing",
        task_type=state["task_type"],
        session_id=state["session_id"],
    )
    record_audit(
        session_id=state["session_id"],
        agent_name="orchestrator",
        action="route_task",
        input_summary=f"Task: {state['task_type']}",
        output_summary=f"Routing to appropriate agent pipeline",
        status="success",
        reasoning=f"Orchestrating {state['task_type']} workflow",
        confidence=1.0,
    )
    return state


def prospecting_node(state: OrchestratorState) -> OrchestratorState:
    input_data = state["input_data"]
    session_id = state["session_id"]
    engine = get_recovery_engine()

    result = engine.execute_with_recovery(
        task_name="prospecting_agent",
        task_fn=run_prospecting_agent,
        task_args={
            "company": input_data.get("company", ""),
            "industry": input_data.get("industry", ""),
            "company_size": input_data.get("size", ""),
            "session_id": session_id,
            "notes": input_data.get("notes", ""),
        },
        session_id=session_id,
    )

    new_state = dict(state)
    new_state["agent_outputs"] = {**state["agent_outputs"], "prospecting_agent": result}

    if result.get("status") in ["success"]:
        new_state["completed_agents"] = state["completed_agents"] + ["prospecting_agent"]
    else:
        new_state["failed_agents"] = state["failed_agents"] + ["prospecting_agent"]
        new_state["error_log"] = state["error_log"] + [f"prospecting_agent: {result.get('error', 'unknown')}"]

    return new_state


def digital_twin_node(state: OrchestratorState) -> OrchestratorState:
    session_id = state["session_id"]
    prospect_output = state["agent_outputs"].get("prospecting_agent", {})
    leads = prospect_output.get("data", {}).get("leads", [])
    company = state["input_data"].get("company", "")
    industry = state["input_data"].get("industry", "")
    engine = get_recovery_engine()

    if not leads:
        leads = [
            {"name": "Decision Maker 1", "title": "VP Sales", "company": company,
             "email": f"dm1@{company.lower()}.com", "pain_points": [], "signals": []},
        ]

    result = engine.execute_with_recovery(
        task_name="digital_twin_agent",
        task_fn=run_digital_twin_agent,
        task_args={
            "leads": leads,
            "company": company,
            "industry": industry,
            "session_id": session_id,
        },
        session_id=session_id,
    )

    new_state = dict(state)
    new_state["agent_outputs"] = {**state["agent_outputs"], "digital_twin_agent": result}

    if result.get("status") == "success":
        new_state["completed_agents"] = state["completed_agents"] + ["digital_twin_agent"]
    else:
        new_state["failed_agents"] = state["failed_agents"] + ["digital_twin_agent"]

    return new_state


def outreach_node(state: OrchestratorState) -> OrchestratorState:
    session_id = state["session_id"]
    prospect_output = state["agent_outputs"].get("prospecting_agent", {})
    twin_output = state["agent_outputs"].get("digital_twin_agent", {})
    leads = prospect_output.get("data", {}).get("leads", [])
    twins = twin_output.get("data", {}).get("twin_profiles", [])
    company = state["input_data"].get("company", "")
    engine = get_recovery_engine()

    result = engine.execute_with_recovery(
        task_name="outreach_agent",
        task_fn=run_outreach_agent,
        task_args={
            "leads": leads,
            "twin_profiles": twins,
            "company": company,
            "session_id": session_id,
        },
        session_id=session_id,
    )

    new_state = dict(state)
    new_state["agent_outputs"] = {**state["agent_outputs"], "outreach_agent": result}

    if result.get("status") == "success":
        new_state["completed_agents"] = state["completed_agents"] + ["outreach_agent"]
    else:
        new_state["failed_agents"] = state["failed_agents"] + ["outreach_agent"]

    return new_state


def deal_intelligence_node(state: OrchestratorState) -> OrchestratorState:
    session_id = state["session_id"]
    input_data = state["input_data"]
    engine = get_recovery_engine()

    result = engine.execute_with_recovery(
        task_name="deal_intelligence_agent",
        task_fn=run_deal_intelligence_agent,
        task_args={
            "deal_ids": input_data.get("deal_ids"),
            "inactivity_threshold": input_data.get("inactivity_threshold_days", 10),
            "session_id": session_id,
        },
        session_id=session_id,
    )

    new_state = dict(state)
    new_state["agent_outputs"] = {**state["agent_outputs"], "deal_intelligence_agent": result}

    if result.get("status") == "success":
        new_state["completed_agents"] = state["completed_agents"] + ["deal_intelligence_agent"]
    else:
        new_state["failed_agents"] = state["failed_agents"] + ["deal_intelligence_agent"]

    return new_state


def crm_auditor_node(state: OrchestratorState) -> OrchestratorState:
    session_id = state["session_id"]
    engine = get_recovery_engine()

    result = engine.execute_with_recovery(
        task_name="crm_auditor_agent",
        task_fn=run_crm_auditor_agent,
        task_args={"session_id": session_id},
        session_id=session_id,
    )

    new_state = dict(state)
    new_state["agent_outputs"] = {**state["agent_outputs"], "crm_auditor_agent": result}

    if result.get("status") == "success":
        new_state["completed_agents"] = state["completed_agents"] + ["crm_auditor_agent"]
    else:
        new_state["failed_agents"] = state["failed_agents"] + ["crm_auditor_agent"]

    return new_state


def churn_node(state: OrchestratorState) -> OrchestratorState:
    session_id = state["session_id"]
    input_data = state["input_data"]
    engine = get_recovery_engine()

    result = engine.execute_with_recovery(
        task_name="churn_agent",
        task_fn=run_churn_agent,
        task_args={
            "account_ids": input_data.get("account_ids"),
            "top_n": input_data.get("top_n", 3),
            "session_id": session_id,
        },
        session_id=session_id,
    )

    new_state = dict(state)
    new_state["agent_outputs"] = {**state["agent_outputs"], "churn_agent": result}

    if result.get("status") == "success":
        new_state["completed_agents"] = state["completed_agents"] + ["churn_agent"]
    else:
        new_state["failed_agents"] = state["failed_agents"] + ["churn_agent"]

    return new_state


def action_execution_node(state: OrchestratorState) -> OrchestratorState:
    session_id = state["session_id"]
    task_type = state["task_type"]
    engine = get_recovery_engine()

    action_type = "send_sequences"
    payload = {}

    if task_type == "cold_outreach":
        outreach_output = state["agent_outputs"].get("outreach_agent", {})
        sequences = outreach_output.get("data", {}).get("sequences", [])
        action_type = "send_sequences"
        payload = {"sequences": sequences}

    elif task_type == "risk_detection":
        deal_output = state["agent_outputs"].get("deal_intelligence_agent", {})
        risks = deal_output.get("data", {}).get("risks", [])
        high_risks = [r for r in risks if r.get("risk_level") in ["critical", "high"]]
        action_type = "risk_followup"
        payload = {"risks": high_risks[:5]}

    elif task_type == "churn_prediction":
        churn_output = state["agent_outputs"].get("churn_agent", {})
        churn_risks = churn_output.get("data", {}).get("top_churn_risks", [])
        action_type = "retention_outreach"
        payload = {"churn_risks": churn_risks}

    result = engine.execute_with_recovery(
        task_name="action_agent",
        task_fn=run_action_agent,
        task_args={
            "action_type": action_type,
            "payload": payload,
            "session_id": session_id,
        },
        session_id=session_id,
    )

    new_state = dict(state)
    new_state["agent_outputs"] = {**state["agent_outputs"], "action_agent": result}

    if result.get("status") == "success":
        new_state["completed_agents"] = state["completed_agents"] + ["action_agent"]
    else:
        new_state["failed_agents"] = state["failed_agents"] + ["action_agent"]

    return new_state


def explainability_node(state: OrchestratorState) -> OrchestratorState:
    session_id = state["session_id"]
    engine = get_recovery_engine()

    result = engine.execute_with_recovery(
        task_name="explainability_agent",
        task_fn=run_explainability_agent,
        task_args={
            "session_id": session_id,
            "agent_outputs": state["agent_outputs"],
            "task_type": state["task_type"],
        },
        session_id=session_id,
    )

    new_state = dict(state)
    new_state["agent_outputs"] = {**state["agent_outputs"], "explainability_agent": result}

    if result.get("status") == "success":
        new_state["completed_agents"] = state["completed_agents"] + ["explainability_agent"]
    else:
        new_state["failed_agents"] = state["failed_agents"] + ["explainability_agent"]

    return new_state


def failure_recovery_node(state: OrchestratorState) -> OrchestratorState:
    if not state["failed_agents"]:
        return state

    failed = state["failed_agents"][-1]
    session_id = state["session_id"]

    result = run_failure_recovery(
        failed_agent=failed,
        session_id=session_id,
        agent_outputs=state["agent_outputs"],
    )

    new_state = dict(state)
    new_state["agent_outputs"] = {**state["agent_outputs"], "failure_recovery": result}
    new_state["escalated"] = result.get("data", {}).get("escalated", False)
    return new_state


def finalize_node(state: OrchestratorState) -> OrchestratorState:
    session_id = state["session_id"]
    task_type = state["task_type"]

    explain_output = state["agent_outputs"].get("explainability_agent", {})
    action_output = state["agent_outputs"].get("action_agent", {})

    final_output = {
        "session_id": session_id,
        "task_type": task_type,
        "status": "completed" if not state["failed_agents"] else "completed_with_errors",
        "completed_agents": state["completed_agents"],
        "failed_agents": state["failed_agents"],
        "escalated": state["escalated"],
        "agent_outputs": state["agent_outputs"],
        "explanation": explain_output.get("data", {}),
        "actions_taken": action_output.get("data", {}),
        "impact_metrics": _compute_impact_metrics(state),
        "completed_at": now_iso(),
    }

    record_audit(
        session_id=session_id,
        agent_name="orchestrator",
        action="finalize",
        input_summary=f"Task: {task_type}",
        output_summary=f"Completed. Agents: {len(state['completed_agents'])} success, {len(state['failed_agents'])} failed",
        status="success",
        reasoning=f"Workflow '{task_type}' completed with {len(state['completed_agents'])} successful agents",
        confidence=0.95,
    )

    new_state = dict(state)
    new_state["final_output"] = final_output
    return new_state


def _compute_impact_metrics(state: OrchestratorState) -> Dict[str, Any]:
    metrics = {}
    outputs = state["agent_outputs"]

    if "prospecting_agent" in outputs:
        leads = outputs["prospecting_agent"].get("data", {}).get("leads", [])
        metrics["leads_identified"] = len(leads)

    if "outreach_agent" in outputs:
        seqs = outputs["outreach_agent"].get("data", {}).get("sequences", [])
        metrics["email_sequences_created"] = len(seqs)
        metrics["total_emails_crafted"] = len(seqs) * 3

    if "deal_intelligence_agent" in outputs:
        data = outputs["deal_intelligence_agent"].get("data", {})
        metrics["deals_at_risk"] = data.get("total_at_risk", 0)
        metrics["critical_deals"] = data.get("critical_count", 0)

    if "churn_agent" in outputs:
        data = outputs["churn_agent"].get("data", {})
        metrics["churn_risks_identified"] = len(data.get("top_churn_risks", []))
        metrics["arr_at_risk"] = data.get("total_arr_at_risk", 0)

    if "action_agent" in outputs:
        data = outputs["action_agent"].get("data", {})
        metrics["emails_sent"] = data.get("emails_sent", 0)
        metrics["crm_updates"] = data.get("crm_updates", 0)

    return metrics


def _should_run_recovery(state: OrchestratorState) -> str:
    if state["failed_agents"]:
        return "failure_recovery"
    return "explainability"


def _route_after_recovery(state: OrchestratorState) -> str:
    return "explainability"


def build_outreach_graph() -> StateGraph:
    graph = StateGraph(OrchestratorState)

    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("prospecting", prospecting_node)
    graph.add_node("digital_twin", digital_twin_node)
    graph.add_node("outreach", outreach_node)
    graph.add_node("action_execution", action_execution_node)
    graph.add_node("crm_auditor", crm_auditor_node)
    graph.add_node("failure_recovery", failure_recovery_node)
    graph.add_node("explainability", explainability_node)
    graph.add_node("finalize", finalize_node)

    graph.set_entry_point("orchestrator")
    graph.add_edge("orchestrator", "prospecting")
    graph.add_edge("prospecting", "digital_twin")
    graph.add_edge("digital_twin", "outreach")
    graph.add_edge("outreach", "action_execution")
    graph.add_edge("action_execution", "crm_auditor")
    graph.add_conditional_edges(
        "crm_auditor",
        _should_run_recovery,
        {"failure_recovery": "failure_recovery", "explainability": "explainability"},
    )
    graph.add_edge("failure_recovery", "explainability")
    graph.add_edge("explainability", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile()


def build_risk_detection_graph() -> StateGraph:
    graph = StateGraph(OrchestratorState)

    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("deal_intelligence", deal_intelligence_node)
    graph.add_node("crm_auditor", crm_auditor_node)
    graph.add_node("action_execution", action_execution_node)
    graph.add_node("failure_recovery", failure_recovery_node)
    graph.add_node("explainability", explainability_node)
    graph.add_node("finalize", finalize_node)

    graph.set_entry_point("orchestrator")
    graph.add_edge("orchestrator", "deal_intelligence")
    graph.add_edge("deal_intelligence", "crm_auditor")
    graph.add_edge("crm_auditor", "action_execution")
    graph.add_conditional_edges(
        "action_execution",
        _should_run_recovery,
        {"failure_recovery": "failure_recovery", "explainability": "explainability"},
    )
    graph.add_edge("failure_recovery", "explainability")
    graph.add_edge("explainability", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile()


def build_churn_prediction_graph() -> StateGraph:
    graph = StateGraph(OrchestratorState)

    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("churn", churn_node)
    graph.add_node("action_execution", action_execution_node)
    graph.add_node("failure_recovery", failure_recovery_node)
    graph.add_node("explainability", explainability_node)
    graph.add_node("finalize", finalize_node)

    graph.set_entry_point("orchestrator")
    graph.add_edge("orchestrator", "churn")
    graph.add_edge("churn", "action_execution")
    graph.add_conditional_edges(
        "action_execution",
        _should_run_recovery,
        {"failure_recovery": "failure_recovery", "explainability": "explainability"},
    )
    graph.add_edge("failure_recovery", "explainability")
    graph.add_edge("explainability", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile()


async def run_orchestrator(
    task_type: str,
    input_data: Dict[str, Any],
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    if not session_id:
        session_id = generate_session_id()

    logger.info("Orchestrator starting", task_type=task_type, session_id=session_id)

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
        if task_type == "cold_outreach":
            graph = build_outreach_graph()
        elif task_type == "risk_detection":
            graph = build_risk_detection_graph()
        elif task_type == "churn_prediction":
            graph = build_churn_prediction_graph()
        else:
            raise ValueError(f"Unknown task type: {task_type}")

        final_state = await graph.ainvoke(initial_state)
        logger.info("Orchestrator completed", session_id=session_id, task_type=task_type)
        return final_state.get("final_output", {})

    except Exception as e:
        logger.error("Orchestrator failed", error=str(e), session_id=session_id)
        return {
            "session_id": session_id,
            "task_type": task_type,
            "status": "error",
            "error": str(e),
            "completed_at": now_iso(),
        }
