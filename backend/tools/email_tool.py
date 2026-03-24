import asyncio
from typing import Any, Dict, List, Optional

from backend.utils.logger import get_logger
from backend.utils.helpers import now_iso, generate_id
from backend.config.settings import settings

logger = get_logger("email_tool")

sent_emails: List[Dict[str, Any]] = []


class EmailClient:
    def __init__(self):
        # Prefer SMTP (SMTP2GO) via fastapi-mail. If creds aren't configured,
        # run in mock mode and just record emails in memory.
        self.is_mock = settings.is_mock_email
        self._fm = None
        self._conf = None

        if self.is_mock:
            logger.info("Email client initialized (mock mode)")
            return

        try:
            from fastapi_mail import ConnectionConfig, FastMail
        except ImportError:
            logger.warning("fastapi-mail not installed, falling back to mock")
            self.is_mock = True
            return

        self._conf = ConnectionConfig(
            MAIL_USERNAME=settings.mail_username,
            MAIL_PASSWORD=settings.mail_password,
            MAIL_FROM=settings.mail_from,
            MAIL_SERVER=settings.mail_server,
            MAIL_PORT=settings.mail_port,
            MAIL_STARTTLS=settings.mail_tls,
            MAIL_SSL_TLS=settings.mail_ssl,
            USE_CREDENTIALS=True,
            VALIDATE_CERTS=True,
        )
        self._fm = FastMail(self._conf)
        logger.info(
            "SMTP email client initialized (live mode)",
            server=settings.mail_server,
            port=settings.mail_port,
            tls=settings.mail_tls,
            ssl=settings.mail_ssl,
        )

    async def _send_async(
        self,
        *,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str],
    ) -> None:
        from fastapi_mail import MessageSchema

        # fastapi-mail's schema supports either str or list[str] for recipients,
        # but we use list to be explicit.
        message = MessageSchema(
            subject=subject,
            recipients=[to_email],
            body=body_html or body_text,
            subtype="html" if body_html else "plain",
        )
        await self._fm.send_message(message)

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

        # Prefer configured MAIL_FROM as the actual sender.
        if settings.mail_from:
            email_record["from_email"] = settings.mail_from

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
            if not self._fm:
                raise RuntimeError("Email client not initialized")

            # We're running in a ThreadPoolExecutor thread (LangGraph invoke),
            # so it's safe to create a fresh event loop per send.
            asyncio.run(
                self._send_async(
                    to_email=to_email,
                    subject=subject,
                    body_text=body_text,
                    body_html=body_html,
                )
            )
            email_record["status"] = "sent"
            sent_emails.append(email_record)
            logger.info("Email sent via SMTP", to=to_email)
            return {
                "success": True,
                "email_id": email_record["email_id"],
                "status": "sent",
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
