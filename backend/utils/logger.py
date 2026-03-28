from __future__ import annotations

import logging
import sys
from threading import Lock
from typing import Any, Dict, List, Optional

import structlog

from backend.config.settings import settings
from backend.utils.helpers import generate_id, now_iso

_logging_configured = False
_audit_store: List[Dict[str, Any]] = []
_audit_lock = Lock()
_audit_backend_disabled = False
_audit_indexes_ready = False
_max_audit_buffer = 2000


def configure_logging(log_level: str = "INFO", environment: str = "development") -> None:
    global _logging_configured
    if _logging_configured:
        return

    level = getattr(logging, log_level.upper(), logging.INFO)
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    renderer = structlog.processors.JSONRenderer() if environment == "production" else structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=processors + [renderer],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)
    _logging_configured = True


def get_logger(name: str):
    return structlog.get_logger(name)


def bind_context(**kwargs: Any) -> None:
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    structlog.contextvars.clear_contextvars()


def _get_context_value(key: str) -> Optional[str]:
    value = structlog.contextvars.get_contextvars().get(key)
    return str(value) if value not in {None, ""} else None


def _get_request_id() -> str:
    return _get_context_value("request_id") or generate_id("req")


def _ensure_audit_indexes() -> None:
    global _audit_backend_disabled, _audit_indexes_ready
    if _audit_backend_disabled or _audit_indexes_ready or settings.is_test:
        return
    try:
        from backend.db.mongo import get_sync_database

        collection = get_sync_database()["audit_logs"]
        collection.create_index([("user_id", 1), ("timestamp", -1)])
        collection.create_index([("session_id", 1), ("timestamp", -1)])
        collection.create_index([("request_id", 1)])
        _audit_indexes_ready = True
    except Exception:
        _audit_backend_disabled = True


def _persist_audit_entry(entry: Dict[str, Any]) -> None:
    global _audit_backend_disabled
    if _audit_backend_disabled or settings.is_test:
        return
    try:
        from backend.db.mongo import get_sync_database

        _ensure_audit_indexes()
        get_sync_database()["audit_logs"].insert_one(dict(entry))
    except Exception:
        _audit_backend_disabled = True


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
    *,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    entry = {
        "log_id": generate_id("log"),
        "request_id": request_id or _get_request_id(),
        "session_id": session_id,
        "user_id": _get_context_value("user_id"),
        "agent_name": agent_name,
        "action": action,
        "input_summary": input_summary,
        "output_summary": output_summary,
        "status": status,
        "timestamp": now_iso(),
        "reasoning": reasoning,
        "confidence": round(float(confidence), 4),
        "extra": extra or {},
    }
    with _audit_lock:
        _audit_store.append(entry)
        if len(_audit_store) > _max_audit_buffer:
            del _audit_store[: len(_audit_store) - _max_audit_buffer]
    _persist_audit_entry(entry)
    try:
        from backend.services.observability import get_metrics_registry

        get_metrics_registry().record_agent_result(agent_name=agent_name, status=status)
    except Exception:
        pass
    get_logger("audit").info(
        "audit_event",
        request_id=entry["request_id"],
        session_id=session_id,
        user_id=entry["user_id"],
        agent_name=agent_name,
        action=action,
        status=status,
        confidence=entry["confidence"],
    )
    return entry


def reset_audit_store() -> None:
    with _audit_lock:
        _audit_store.clear()


def _query_logs_from_memory(
    session_id: Optional[str],
    user_id: Optional[str],
    page: int,
    page_size: int,
) -> Dict[str, Any]:
    with _audit_lock:
        logs = list(reversed(_audit_store))
    if session_id:
        logs = [log for log in logs if log.get("session_id") == session_id]
    if user_id:
        logs = [log for log in logs if log.get("user_id") == user_id]
    total = len(logs)
    start = max(0, (page - 1) * page_size)
    end = start + page_size
    return {"items": logs[start:end], "total": total}


def query_audit_logs(
    *,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    page: int = 1,
    page_size: int = 100,
) -> Dict[str, Any]:
    if not _audit_backend_disabled and not settings.is_test:
        try:
            from backend.db.mongo import get_sync_database

            collection = get_sync_database()["audit_logs"]
            filters: Dict[str, Any] = {}
            if session_id:
                filters["session_id"] = session_id
            if user_id:
                filters["user_id"] = user_id
            total = collection.count_documents(filters)
            cursor = (
                collection.find(filters, {"_id": 0})
                .sort("timestamp", -1)
                .skip(max(0, (page - 1) * page_size))
                .limit(page_size)
            )
            return {"items": list(cursor), "total": total}
        except Exception:
            pass
    return _query_logs_from_memory(session_id, user_id, page, page_size)


def get_all_logs(*, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    return query_audit_logs(user_id=user_id, page=1, page_size=_max_audit_buffer)["items"]


def get_logs_by_session(session_id: str, *, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    return query_audit_logs(session_id=session_id, user_id=user_id, page=1, page_size=_max_audit_buffer)["items"]
