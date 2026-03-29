from __future__ import annotations

from typing import Any, Dict, List

from tenacity import retry, stop_after_attempt, wait_exponential

from backend.config.settings import settings
from backend.tools.crm_tool import add_new_lead, log_activity, update_deal_stage
from backend.tools.email_tool import get_email_client
from backend.utils.helpers import build_agent_response, generate_id, now_iso
from backend.utils.logger import get_logger, record_audit

logger = get_logger("action_agent")


def execute_send_sequence(sequences: List[Dict[str, Any]], user_id: str) -> List[Dict[str, Any]]:
    email_client = get_email_client()
    results: List[Dict[str, Any]] = []
    for sequence in sequences:
        lead_email = sequence.get("lead_email", "")
        lead_name = sequence.get("lead_name", "")
        sequence_id = sequence.get("sequence_id", generate_id("seq"))
        emails = sequence.get("emails", [])
        if not lead_email or not emails:
            results.append(
                {
                    "sequence_id": sequence_id,
                    "lead": lead_name,
                    "status": "skipped",
                    "reason": "Missing email address or message content",
                }
            )
            continue
        email_payloads = [{"subject": email.get("subject", ""), "body": email.get("body", "")} for email in emails]
        send_result = email_client.send_sequence(
            to_email=lead_email,
            to_name=lead_name,
            emails=email_payloads,
            sequence_id=sequence_id,
            user_id=user_id,
        )
        results.append(
            {
                "sequence_id": sequence_id,
                "lead": lead_name,
                "lead_email": lead_email,
                "status": "sent" if send_result.get("failed", 1) == 0 else "partial",
                "sent_count": send_result.get("sent", 0),
                "total_emails": send_result.get("total_emails", 0),
                "timestamp": now_iso(),
            }
        )
    return results


def execute_risk_followups(risks: List[Dict[str, Any]], user_id: str) -> List[Dict[str, Any]]:
    email_client = get_email_client()
    results: List[Dict[str, Any]] = []
    for risk in risks:
        company = risk.get("company", "Unknown")
        account_id = risk.get("deal_id", "")
        body = (
            "Hi there,\n\n"
            "I noticed a few risk signals on your account and wanted to proactively reconnect.\n\n"
            f"{risk.get('recovery_strategy', '')}\n\n"
            "Would 15 minutes this week help us align on next steps?"
        )
        send_result = email_client.send_email(
            to_email=f"contact@{company.lower().replace(' ', '')}.com",
            to_name=f"{company} Team",
            subject=f"Quick check-in - {company}",
            body_text=body,
            sequence_id=generate_id("recovery"),
            user_id=user_id,
        )
        crm_update = update_deal_stage(
            account_id=account_id,
            new_stage="Re-engagement",
            notes=f"Recovery outreach sent. Risk level: {risk.get('risk_level', 'medium')}",
            user_id=user_id,
        )
        log_activity(
            account_id=account_id,
            activity_type="risk_followup",
            description=f"Automated risk recovery email sent. Risk: {risk.get('risk_level', 'medium')}",
            user_id=user_id,
        )
        results.append(
            {
                "account_id": account_id,
                "company": company,
                "risk_level": risk.get("risk_level", "medium"),
                "email_sent": send_result.get("success", False),
                "crm_updated": crm_update.get("success", False),
                "timestamp": now_iso(),
            }
        )
    return results


def execute_retention_outreach(churn_risks: List[Dict[str, Any]], user_id: str) -> List[Dict[str, Any]]:
    email_client = get_email_client()
    results: List[Dict[str, Any]] = []
    for risk in churn_risks:
        company = risk.get("company", "Unknown")
        contact_name = risk.get("contact_name", "")
        contact_email = risk.get("contact_email") or f"account@{company.lower().replace(' ', '-')}.com"
        body = (
            f"Hi {contact_name or 'there'},\n\n"
            "I wanted to reach out proactively because your success is important to us.\n\n"
            f"{risk.get('retention_strategy', '')}\n\n"
            "Would you be open to a short business review this week?"
        )
        send_result = email_client.send_email(
            to_email=contact_email,
            to_name=contact_name or company,
            subject=f"Your {company} success plan - let's reconnect",
            body_text=body,
            sequence_id=generate_id("retention"),
            user_id=user_id,
        )
        log_activity(
            account_id=risk.get("account_id", ""),
            activity_type="retention_outreach",
            description=f"Retention email sent. Churn probability: {risk.get('churn_probability', 0):.1%}",
            user_id=user_id,
        )
        results.append(
            {
                "account_id": risk.get("account_id"),
                "company": company,
                "churn_probability": risk.get("churn_probability", 0),
                "email_sent": send_result.get("success", False),
                "contact_email": contact_email,
                "timestamp": now_iso(),
            }
        )
    return results


@retry(stop=stop_after_attempt(settings.max_retries + 1), wait=wait_exponential(min=1, max=4))
def run_action_agent(action_type: str, payload: Dict[str, Any], session_id: str, user_id: str) -> Dict[str, Any]:
    logger.info("action_agent_start", action_type=action_type, session_id=session_id)
    executed_actions: List[Dict[str, Any]] = []
    total_emails_sent = 0
    total_crm_updates = 0

    if action_type == "send_sequences":
        executed_actions = execute_send_sequence(payload.get("sequences", []), user_id=user_id)
        total_emails_sent = sum(item.get("sent_count", 0) for item in executed_actions)
    elif action_type == "risk_followup":
        executed_actions = execute_risk_followups(payload.get("risks", []), user_id=user_id)
        total_emails_sent = len([item for item in executed_actions if item.get("email_sent")])
        total_crm_updates = len([item for item in executed_actions if item.get("crm_updated")])
    elif action_type == "retention_outreach":
        executed_actions = execute_retention_outreach(payload.get("churn_risks", []), user_id=user_id)
        total_emails_sent = len([item for item in executed_actions if item.get("email_sent")])
    elif action_type == "add_leads":
        for lead in payload.get("leads", []):
            crm_record = add_new_lead(lead, user_id=user_id)
            executed_actions.append(
                {
                    "action": "add_lead",
                    "company": lead.get("company"),
                    "account_id": crm_record.get("account_id"),
                    "success": True,
                }
            )
        total_crm_updates = len(executed_actions)
    else:
        raise ValueError(f"Unknown action type: {action_type}")

    result = build_agent_response(
        status="success",
        data={
            "action_type": action_type,
            "executed_actions": executed_actions,
            "total_actions": len(executed_actions),
            "emails_sent": total_emails_sent,
            "crm_updates": total_crm_updates,
            "timestamp": now_iso(),
        },
        reasoning=f"Executed {len(executed_actions)} {action_type} actions.",
        confidence=0.95,
        agent_name="action_agent",
        tools_used=["email_tool", "crm_tool"],
    )
    record_audit(
        session_id=session_id,
        agent_name="action_agent",
        action=action_type,
        input_summary=f"Action: {action_type}, Items: {len(executed_actions)}",
        output_summary=f"Emails sent: {total_emails_sent}, CRM updates: {total_crm_updates}",
        status="success",
        reasoning=result["reasoning"],
        confidence=0.95,
    )
    return result
