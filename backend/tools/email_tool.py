import json
from typing import Any, Dict, List, Optional
from datetime import datetime

from backend.utils.logger import get_logger
from backend.utils.helpers import now_iso, generate_id
from backend.config.settings import settings

logger = get_logger("email_tool")

sent_emails: List[Dict[str, Any]] = []


class EmailClient:
    def __init__(self):
        self.api_key = settings.sendgrid_api_key
        self.is_mock = self.api_key == "mock_key" or not self.api_key.startswith("SG.")
        self._sg_client = None

        if not self.is_mock:
            try:
                from sendgrid import SendGridAPIClient
                from sendgrid.helpers.mail import Mail
                self._sg_client = SendGridAPIClient(self.api_key)
                logger.info("SendGrid client initialized (live mode)")
            except ImportError:
                logger.warning("SendGrid not installed, falling back to mock")
                self.is_mock = True
        else:
            logger.info("Email client initialized (mock mode)")

    def send_email(
        self,
        to_email: str,
        to_name: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        from_email: str = "sales@revops-ai.com",
        from_name: str = "RevOps AI",
        sequence_id: Optional[str] = None,
        sequence_step: int = 1,
    ) -> Dict[str, Any]:
        email_record = {
            "email_id": generate_id("email"),
            "to_email": to_email,
            "to_name": to_name,
            "from_email": from_email,
            "from_name": from_name,
            "subject": subject,
            "body_text": body_text,
            "body_html": body_html or f"<p>{body_text}</p>",
            "sequence_id": sequence_id,
            "sequence_step": sequence_step,
            "sent_at": now_iso(),
            "status": "pending",
        }

        if self.is_mock:
            email_record["status"] = "sent_mock"
            email_record["mock_message_id"] = generate_id("msg")
            sent_emails.append(email_record)
            logger.info(
                "Mock email sent",
                to=to_email,
                subject=subject,
                sequence_step=sequence_step,
            )
            return {
                "success": True,
                "email_id": email_record["email_id"],
                "status": "sent_mock",
                "message": f"Mock email sent to {to_email}",
            }

        try:
            from sendgrid.helpers.mail import Mail
            message = Mail(
                from_email=(from_email, from_name),
                to_emails=(to_email, to_name),
                subject=subject,
                plain_text_content=body_text,
                html_content=body_html or f"<p>{body_text}</p>",
            )
            response = self._sg_client.send(message)
            email_record["status"] = "sent"
            email_record["sendgrid_status_code"] = response.status_code
            sent_emails.append(email_record)
            logger.info("Email sent via SendGrid", to=to_email, status=response.status_code)
            return {
                "success": True,
                "email_id": email_record["email_id"],
                "status": "sent",
                "sendgrid_status": response.status_code,
            }
        except Exception as e:
            email_record["status"] = "failed"
            email_record["error"] = str(e)
            sent_emails.append(email_record)
            logger.error("Email send failed", to=to_email, error=str(e))
            return {
                "success": False,
                "email_id": email_record["email_id"],
                "status": "failed",
                "error": str(e),
            }

    def send_sequence(
        self,
        to_email: str,
        to_name: str,
        emails: List[Dict[str, str]],
        sequence_id: str,
    ) -> Dict[str, Any]:
        results = []
        failed = 0

        for i, email in enumerate(emails, 1):
            result = self.send_email(
                to_email=to_email,
                to_name=to_name,
                subject=email.get("subject", f"Follow-up #{i}"),
                body_text=email.get("body", ""),
                sequence_id=sequence_id,
                sequence_step=i,
            )
            results.append(result)
            if not result.get("success"):
                failed += 1

        return {
            "sequence_id": sequence_id,
            "total_emails": len(emails),
            "sent": len(emails) - failed,
            "failed": failed,
            "results": results,
            "timestamp": now_iso(),
        }


def get_sent_emails(
    to_email: Optional[str] = None,
    sequence_id: Optional[str] = None,
) -> List[Dict]:
    emails = sent_emails
    if to_email:
        emails = [e for e in emails if e["to_email"] == to_email]
    if sequence_id:
        emails = [e for e in emails if e.get("sequence_id") == sequence_id]
    return emails


def get_email_stats() -> Dict[str, Any]:
    total = len(sent_emails)
    sent = len([e for e in sent_emails if "sent" in e.get("status", "")])
    failed = len([e for e in sent_emails if e.get("status") == "failed"])
    return {
        "total": total,
        "sent": sent,
        "failed": failed,
        "success_rate": sent / total if total > 0 else 0.0,
    }


_email_client_instance: Optional[EmailClient] = None


def get_email_client() -> EmailClient:
    global _email_client_instance
    if _email_client_instance is None:
        _email_client_instance = EmailClient()
    return _email_client_instance
