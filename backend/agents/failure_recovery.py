import time
from typing import Any, Callable, Dict, List, Optional

from backend.config.settings import settings
from backend.utils.helpers import build_agent_response, now_iso
from backend.utils.logger import get_logger, record_audit

logger = get_logger("failure_recovery")


class FailureRecoveryEngine:
    def __init__(self):
        self.max_retries = settings.max_retries
        self.retry_delay = settings.retry_delay
        self.escalation_threshold = 2
        self.failed_tasks: List[Dict[str, Any]] = []
        self.recovered_tasks: List[Dict[str, Any]] = []

    def execute_with_recovery(
        self,
        task_name: str,
        task_fn: Callable,
        task_args: Dict[str, Any],
        session_id: str,
        fallback_fn: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        last_error = None
        retry_count = 0

        for attempt in range(self.max_retries + 1):
            try:
                if attempt > 0:
                    delay = self.retry_delay * (2 ** (attempt - 1))
                    logger.info(
                        "Retrying task",
                        task=task_name,
                        attempt=attempt + 1,
                        delay=delay,
                        session_id=session_id,
                    )
                    time.sleep(delay)

                result = task_fn(**task_args)

                if result.get("status") == "failure":
                    raise RuntimeError(result.get("error", "Agent returned failure status"))

                if attempt > 0:
                    self.recovered_tasks.append({
                        "task": task_name,
                        "session_id": session_id,
                        "attempts": attempt + 1,
                        "recovered_at": now_iso(),
                    })
                    logger.info("Task recovered", task=task_name, attempts=attempt + 1)

                return result

            except Exception as e:
                last_error = str(e)
                retry_count = attempt + 1
                logger.warning(
                    "Task attempt failed",
                    task=task_name,
                    attempt=attempt + 1,
                    error=last_error,
                )

        self.failed_tasks.append({
            "task": task_name,
            "session_id": session_id,
            "attempts": retry_count,
            "last_error": last_error,
            "failed_at": now_iso(),
            "escalated": retry_count >= self.escalation_threshold,
        })

        should_escalate = retry_count >= self.escalation_threshold

        if fallback_fn:
            try:
                logger.info("Attempting fallback", task=task_name)
                fallback_result = fallback_fn(**task_args)
                fallback_result["_recovered_via_fallback"] = True
                record_audit(
                    session_id=session_id,
                    agent_name="failure_recovery",
                    action=f"fallback_{task_name}",
                    input_summary=f"Task: {task_name} failed after {retry_count} attempts",
                    output_summary="Fallback succeeded",
                    status="success",
                )
                return fallback_result
            except Exception as fe:
                logger.error("Fallback also failed", task=task_name, error=str(fe))

        record_audit(
            session_id=session_id,
            agent_name="failure_recovery",
            action=f"failed_{task_name}",
            input_summary=f"Task: {task_name}",
            output_summary=f"Failed after {retry_count} attempts. Error: {last_error[:100]}",
            status="failure",
        )

        return build_agent_response(
            status="escalated" if should_escalate else "failure",
            data={
                "task": task_name,
                "retry_count": retry_count,
                "last_error": last_error,
                "escalated": should_escalate,
                "escalation_reason": f"Task '{task_name}' failed {retry_count} times. Manual intervention required." if should_escalate else "",
            },
            reasoning=f"Task '{task_name}' exhausted {retry_count} retry attempts. "
                      f"Last error: {last_error}. "
                      f"{'ESCALATED for human review.' if should_escalate else 'Marked as failed.'}",
            confidence=0.0,
            agent_name="failure_recovery",
            error=last_error,
        )

    def get_recovery_report(self) -> Dict[str, Any]:
        total_failed = len(self.failed_tasks)
        total_recovered = len(self.recovered_tasks)
        escalated = [t for t in self.failed_tasks if t.get("escalated")]

        return {
            "total_failed_tasks": total_failed,
            "total_recovered_tasks": total_recovered,
            "escalated_tasks": len(escalated),
            "recovery_rate": total_recovered / max(total_recovered + total_failed, 1),
            "failed_tasks": self.failed_tasks,
            "recovered_tasks": self.recovered_tasks,
            "escalation_items": escalated,
            "report_time": now_iso(),
        }

    def reset(self):
        self.failed_tasks = []
        self.recovered_tasks = []


def run_failure_recovery(
    failed_agent: str,
    session_id: str,
    agent_outputs: Dict[str, Any],
) -> Dict[str, Any]:
    logger.info("Failure recovery triggered", agent=failed_agent, session_id=session_id)

    recovery_actions = []
    recommendations = []

    if "prospecting" in failed_agent:
        recommendations.append("Retry with simplified company profile")
        recommendations.append("Use manual LinkedIn search as fallback")
        recovery_actions.append("Fallback to basic enrichment without LLM scoring")

    elif "outreach" in failed_agent:
        recommendations.append("Use email template library instead of AI generation")
        recommendations.append("Assign to human SDR for manual outreach")
        recovery_actions.append("Generate simplified 1-email sequence using template")

    elif "deal_intelligence" in failed_agent:
        recommendations.append("Use rule-based risk detection (inactivity thresholds)")
        recommendations.append("Alert sales manager directly via Slack")
        recovery_actions.append("Apply hardcoded risk thresholds without LLM analysis")

    elif "churn" in failed_agent:
        recommendations.append("Use scoring model without LLM interpretation")
        recommendations.append("Alert Customer Success team for manual review")
        recovery_actions.append("Return raw churn scores without retention strategies")

    elif "action" in failed_agent:
        recommendations.append("Queue emails for manual send")
        recommendations.append("Log CRM updates for manual entry")
        recovery_actions.append("Store failed actions in escalation queue")

    else:
        recommendations.append("Contact engineering team")
        recovery_actions.append("Log error for investigation")

    successful_agents = [
        name for name, output in agent_outputs.items()
        if isinstance(output, dict) and output.get("status") == "success"
    ]

    result = build_agent_response(
        status="success",
        data={
            "failed_agent": failed_agent,
            "recovery_actions": recovery_actions,
            "recommendations": recommendations,
            "successful_agents": successful_agents,
            "escalated": True,
            "escalation_message": f"Agent '{failed_agent}' failed and requires attention. "
                                  f"Recovery actions have been logged.",
            "timestamp": now_iso(),
        },
        reasoning=f"Failure recovery initiated for '{failed_agent}'. "
                  f"Generated {len(recovery_actions)} recovery actions and {len(recommendations)} recommendations. "
                  f"Escalated for human review.",
        confidence=0.70,
        agent_name="failure_recovery",
    )

    record_audit(
        session_id=session_id,
        agent_name="failure_recovery",
        action="recover_failure",
        input_summary=f"Failed agent: {failed_agent}",
        output_summary=f"Recovery plan generated, escalated",
        status="success",
        reasoning=result["reasoning"],
        confidence=0.70,
    )

    return result


_engine_instance: Optional[FailureRecoveryEngine] = None


def get_recovery_engine() -> FailureRecoveryEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = FailureRecoveryEngine()
    return _engine_instance
