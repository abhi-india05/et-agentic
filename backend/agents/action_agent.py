import json
from typing import Any, Dict, List, Optional

from tenacity import retry, stop_after_attempt, wait_exponential

from backend.config.settings import settings
from backend.tools.email_tool import get_email_client
from backend.tools.crm_tool import update_deal_stage, log_activity, add_new_lead
from backend.utils.helpers import build_agent_response, generate_id, now_iso
from backend.utils.logger import get_logger, record_audit

logger = get_logger("action_agent")


def execute_send_sequence(sequences: List[Dict], session_id: str) -> List[Dict]:
    email_client = get_email_client()
    results = []

    for seq in sequences:
        lead_email = seq.get("lead_email", "")
        lead_name = seq.get("lead_name", "")
        sequence_id = seq.get("sequence_id", generate_id("seq"))
        emails = seq.get("emails", [])

        if not lead_email or not emails:
            results.append({
                "sequence_id": sequence_id,
                "lead": lead_name,
                "status": "skipped",
                "reason": "Missing email or content",
            })
            continue

        email_payloads = [
            {"subject": e.get("subject", ""), "body": e.get("body", "")}
            for e in emails
        ]

        send_result = email_client.send_sequence(
            to_email=lead_email,
            to_name=lead_name,
            emails=email_payloads,
            sequence_id=sequence_id,
        )

        results.append({
            "sequence_id": sequence_id,
            "lead": lead_name,
            "lead_email": lead_email,
            "status": "sent" if send_result.get("failed", 1) == 0 else "partial",
            "sent_count": send_result.get("sent", 0),
            "total_emails": send_result.get("total_emails", 0),
            "timestamp": now_iso(),
        })

        log_activity(
            account_id=generate_id("acc"),
            activity_type="email_sequence",
            description=f"Sent {send_result.get('sent', 0)}-email sequence to {lead_email}",
        )

    return results


def execute_risk_followups(risks: List[Dict], session_id: str) -> List[Dict]:
    email_client = get_email_client()
    results = []

    for risk in risks:
        company = risk.get("company", "Unknown")
        account_id = risk.get("deal_id", "")
        recovery_strategy = risk.get("recovery_strategy", "")
        risk_level = risk.get("risk_level", "medium")

        subject = f"Quick check-in — {company}"
        body = f"""Hi there,

I wanted to personally reach out regarding your account. I noticed we haven't connected recently, and I want to make sure you're getting maximum value.

{recovery_strategy}

Would you have 15 minutes this week for a quick sync? I have some specific ideas that could be immediately useful for your team.

Best regards,
RevOps AI Team"""

        send_result = email_client.send_email(
            to_email=f"contact@{company.lower().replace(' ', '')}.com",
            to_name=f"{company} Team",
            subject=subject,
            body_text=body,
            sequence_id=generate_id("recovery"),
        )

        crm_update = update_deal_stage(
            account_id=account_id,
            new_stage="Re-engagement",
            notes=f"Recovery outreach sent. Risk level: {risk_level}",
        )

        log_activity(
            account_id=account_id,
            activity_type="risk_followup",
            description=f"Automated risk recovery email sent. Risk: {risk_level}",
        )

        results.append({
            "account_id": account_id,
            "company": company,
            "risk_level": risk_level,
            "email_sent": send_result.get("success", False),
            "crm_updated": crm_update.get("success", False),
            "timestamp": now_iso(),
        })

    return results


def execute_retention_outreach(churn_risks: List[Dict], session_id: str) -> List[Dict]:
    email_client = get_email_client()
    results = []

    for risk in churn_risks:
        company = risk.get("company", "Unknown")
        contact_name = risk.get("contact_name", "")
        contact_email = risk.get("contact_email", "")
        churn_prob = risk.get("churn_probability", 0)
        retention_strategy = risk.get("retention_strategy", "")

        if not contact_email:
            contact_email = f"account@{company.lower().replace(' ', '-')}.com"

        subject = f"Your {company} success plan — let's reconnect"
        body = f"""Hi {contact_name or 'there'},

Your success is our top priority, and I wanted to check in directly.

{retention_strategy}

I'd love to schedule a 20-minute business review to ensure you're getting the outcomes you expected. I have specific recommendations based on your usage patterns.

Can we connect this week?

Warmly,
Customer Success Team
RevOps AI"""

        send_result = email_client.send_email(
            to_email=contact_email,
            to_name=contact_name or company,
            subject=subject,
            body_text=body,
            sequence_id=generate_id("retention"),
        )

        log_activity(
            account_id=risk.get("account_id", ""),
            activity_type="retention_outreach",
            description=f"Retention email sent. Churn probability: {churn_prob:.1%}",
        )

        results.append({
            "account_id": risk.get("account_id"),
            "company": company,
            "churn_probability": churn_prob,
            "email_sent": send_result.get("success", False),
            "contact_email": contact_email,
            "timestamp": now_iso(),
        })

    return results


@retry(stop=stop_after_attempt(settings.max_retries + 1), wait=wait_exponential(min=1, max=4))
def run_action_agent(
    action_type: str,
    payload: Dict[str, Any],
    session_id: str,
) -> Dict[str, Any]:
    logger.info("Action agent starting", action_type=action_type, session_id=session_id)

    try:
        executed_actions = []
        total_emails_sent = 0
        total_crm_updates = 0

        if action_type == "send_sequences":
            sequences = payload.get("sequences", [])
            results = execute_send_sequence(sequences, session_id)
            executed_actions.extend(results)
            total_emails_sent = sum(r.get("sent_count", 0) for r in results)

        elif action_type == "risk_followup":
            risks = payload.get("risks", [])
            results = execute_risk_followups(risks, session_id)
            executed_actions.extend(results)
            total_emails_sent = len([r for r in results if r.get("email_sent")])
            total_crm_updates = len([r for r in results if r.get("crm_updated")])

        elif action_type == "retention_outreach":
            churn_risks = payload.get("churn_risks", [])
            results = execute_retention_outreach(churn_risks, session_id)
            executed_actions.extend(results)
            total_emails_sent = len([r for r in results if r.get("email_sent")])

        elif action_type == "add_leads":
            leads = payload.get("leads", [])
            for lead in leads:
                crm_record = add_new_lead(lead)
                executed_actions.append({
                    "action": "add_lead",
                    "company": lead.get("company"),
                    "account_id": crm_record.get("account_id"),
                    "success": True,
                })
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
            reasoning=f"Executed {len(executed_actions)} {action_type} actions. "
                      f"Sent {total_emails_sent} emails, made {total_crm_updates} CRM updates.",
            confidence=0.95,
            agent_name="action_agent",
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

        logger.info("Action agent completed", actions=len(executed_actions), emails=total_emails_sent)
        return result

    except Exception as e:
        logger.error("Action agent failed", error=str(e), action_type=action_type)
        record_audit(
            session_id=session_id,
            agent_name="action_agent",
            action=action_type,
            input_summary=f"Action: {action_type}",
            output_summary="FAILED",
            status="failure",
        )
        return build_agent_response(
            status="failure",
            data={},
            reasoning=f"Action execution failed: {str(e)}",
            confidence=0.0,
            agent_name="action_agent",
            error=str(e),
        )
