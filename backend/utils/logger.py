import structlog
import logging
import sys
from datetime import datetime
from typing import Any, Dict
import json

from backend.config.settings import settings


def configure_logging():
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer() if settings.environment == "production"
            else structlog.dev.ConsoleRenderer(colors=True),
        ],
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        wrapper_class=structlog.BoundLogger,
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )


def get_logger(name: str):
    return structlog.get_logger(name)


audit_store: list[Dict[str, Any]] = []


def record_audit(
    session_id: str,
    agent_name: str,
    action: str,
    input_summary: str,
    output_summary: str,
    status: str,
    reasoning: str = "",
    confidence: float = 0.0,
) -> Dict[str, Any]:
    log_entry = {
        "log_id": f"log_{datetime.utcnow().timestamp()}_{agent_name}",
        "session_id": session_id,
        "agent_name": agent_name,
        "action": action,
        "input_summary": input_summary,
        "output_summary": output_summary,
        "status": status,
        "timestamp": datetime.utcnow().isoformat(),
        "reasoning": reasoning,
        "confidence": confidence,
    }
    audit_store.append(log_entry)
    logger = get_logger("audit")
    logger.info(
        "audit_log",
        session_id=session_id,
        agent_name=agent_name,
        action=action,
        status=status,
    )
    return log_entry


def get_all_logs() -> list[Dict[str, Any]]:
    return list(reversed(audit_store))


def get_logs_by_session(session_id: str) -> list[Dict[str, Any]]:
    return [log for log in audit_store if log["session_id"] == session_id]
