from __future__ import annotations

import html
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from typing import Any, Dict, List, Optional

from backend.config.settings import settings
from backend.utils.helpers import generate_id, now_iso
from backend.utils.logger import get_logger

logger = get_logger("email_tool")

sent_emails: List[Dict[str, Any]] = []


class EmailClient:
    def __init__(self):
        # Prefer SMTP (Gmail) via stdlib smtplib. If creds aren't configured,
        # run in mock mode and just record emails in memory.
        self.is_mock = settings.is_mock_email
        if self.is_mock:
            logger.info("Email client initialized (mock mode)")
            return

        logger.info(
            "SMTP email client initialized (live mode)",
            server=settings.mail_server,
            port=settings.mail_port,
            tls=settings.mail_tls,
            ssl=settings.mail_ssl,
        )

    def _build_html_fallback(self, body_text: str) -> str:
        escaped = html.escape(body_text or "")
        escaped = escaped.replace("\r\n", "\n").replace("\r", "\n")
        return "<p>" + escaped.replace("\n", "<br>") + "</p>"

    def _send_via_smtp(self, message: EmailMessage) -> None:
        if not settings.mail_username or not settings.mail_password:
            raise RuntimeError("MAIL_USERNAME and MAIL_PASSWORD must be set for live email")

        context = ssl.create_default_context()

        if settings.mail_ssl:
            with smtplib.SMTP_SSL(
                settings.mail_server,
                settings.mail_port,
                context=context,
                timeout=30,
            ) as smtp:
                smtp.ehlo()
                smtp.login(settings.mail_username, settings.mail_password)
                smtp.send_message(message)
                return

        with smtplib.SMTP(settings.mail_server, settings.mail_port, timeout=30) as smtp:
            smtp.ehlo()
            if settings.mail_tls:
                smtp.starttls(context=context)
                smtp.ehlo()
            smtp.login(settings.mail_username, settings.mail_password)
            smtp.send_message(message)

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
            "body_html": body_html or self._build_html_fallback(body_text),
            "sequence_id": sequence_id,
            "sequence_step": sequence_step,
            "sent_at": now_iso(),
            "status": "pending",
        }

        # Prefer configured MAIL_FROM as the actual sender.
        if settings.mail_from:
            email_record["from_email"] = settings.mail_from

        if self.is_mock:
            email_record["status"] = "sent_mock"
            email_record["mock_message_id"] = generate_id("msg")
            sent_emails.append(email_record)
            logger.info("Mock email sent", to=to_email, subject=subject, sequence_step=sequence_step)
            return {
                "success": True,
                "email_id": email_record["email_id"],
                "status": "sent_mock",
                "message": f"Mock email sent to {to_email}",
            }

        try:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = formataddr((from_name, email_record["from_email"]))
            msg["To"] = formataddr((to_name, to_email)) if to_name else to_email
            msg["Message-ID"] = make_msgid(domain=(settings.mail_server or "localhost"))

            msg.set_content(body_text or "")
            msg.add_alternative(email_record["body_html"], subtype="html")

            self._send_via_smtp(msg)

            email_record["status"] = "sent"
            sent_emails.append(email_record)
            logger.info("Email sent via SMTP", to=to_email)
            return {"success": True, "email_id": email_record["email_id"], "status": "sent"}
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
                from_email=email.get("from_email", "sales@revops-ai.com"),
                from_name=email.get("from_name", "RevOps AI"),
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
