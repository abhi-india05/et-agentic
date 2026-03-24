import logging
import sys
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog

_logging_configured = False

audit_store: List[Dict[str, Any]] = []


def configure_logging(log_level: str = "INFO", environment: str = "development") -> None:
    
    global _logging_configured
    if _logging_configured:
        return

    level = getattr(logging, log_level.upper(), logging.INFO)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_logger_name,
    ]

    if environment == "production":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors + [
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        wrapper_class=structlog.BoundLogger,
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )

    _logging_configured = True


def get_logger(name: str):
  
    return structlog.get_logger(name)


def record_audit(
    session_id: str,
    agent_name: str,
    action: str,
    input_summary: str,
    output_summary: str,
    status: str,
    reasoning: str = "",
    confidence: float = 0.0,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
   
    log_entry = {
        "log_id": f"log_{uuid.uuid4().hex[:10]}",
        "request_id": request_id or str(uuid.uuid4())[:8],
        "session_id": session_id,
        "agent_name": agent_name,
        "action": action,
        "input_summary": input_summary,
        "output_summary": output_summary,
        "status": status,
        "timestamp": datetime.utcnow().isoformat(),
        "reasoning": reasoning,
        "confidence": round(float(confidence), 4),
    }
    audit_store.append(log_entry)

    logger = get_logger("audit")
    logger.info(
        "audit_event",
        session_id=session_id,
        agent=agent_name,
        action=action,
        status=status,
        confidence=round(float(confidence), 4),
    )
    return log_entry


def get_all_logs() -> List[Dict[str, Any]]:
    return list(reversed(audit_store))


def get_logs_by_session(session_id: str) -> List[Dict[str, Any]]:
    return [log for log in reversed(audit_store) if log["session_id"] == session_id]