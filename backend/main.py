from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config.settings import settings
from backend.utils.logger import configure_logging, get_logger, get_all_logs, get_logs_by_session
from backend.utils.helpers import generate_session_id, now_iso

configure_logging(log_level=settings.log_level, environment=settings.environment)

from backend.models.schemas import OutreachRequest, RiskDetectionRequest, ChurnPredictionRequest
from backend.agents.orchestrator import run_orchestrator
from backend.agents.failure_recovery import get_recovery_engine
from backend.tools.email_tool import get_email_stats, get_sent_emails
from backend.tools.crm_tool import get_pipeline_stats, get_all_accounts
from backend.memory.vector_store import get_vector_store

logger = get_logger("main")

_active_sessions: Dict[str, Dict[str, Any]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "revops_ai_startup",
        environment=settings.environment,
        model=settings.openai_model,
        has_openai_key=settings.has_openai_key,
        mock_email=settings.is_mock_email,
    )
    store = get_vector_store()
    store.load()
    logger.info("vector_store_ready", **store.stats())
    yield
    logger.info("revops_ai_shutdown")
    store.save()


app = FastAPI(
    title="RevOps AI — Autonomous Sales & Revenue Intelligence",
    description="Production-grade multi-agent AI system for autonomous sales operations.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "unhandled_exception",
        path=str(request.url),
        method=request.method,
        error=str(exc),
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "An internal error occurred. It has been logged.",
            "detail": str(exc) if settings.environment != "production" else "Contact support.",
            "timestamp": now_iso(),
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code, "timestamp": now_iso()},
    )



def _start_session(session_id: str, task_type: str) -> None:
    _active_sessions[session_id] = {
        "status": "running",
        "task_type": task_type,
        "started_at": now_iso(),
    }


def _end_session(session_id: str, status: str = "completed") -> None:
    if session_id in _active_sessions:
        _active_sessions[session_id]["status"] = status
        _active_sessions[session_id]["completed_at"] = now_iso()



@app.get("/health")
async def health_check():
    store = get_vector_store()
    return {
        "status": "healthy",
        "version": "1.0.0",
        "environment": settings.environment,
        "timestamp": now_iso(),
        "openai_configured": settings.has_openai_key,
        "email_mode": "live" if not settings.is_mock_email else "mock",
        "vector_store": store.stats(),
        "email_stats": get_email_stats(),
        "active_sessions": len([s for s in _active_sessions.values() if s["status"] == "running"]),
    }


@app.post("/run-outreach")
async def run_outreach(request: OutreachRequest):
    session_id = generate_session_id()
    logger.info("outreach_request", company=request.company, session_id=session_id)
    _start_session(session_id, "cold_outreach")

    try:
        result = await run_orchestrator(
            task_type="cold_outreach",
            input_data={
                "company": request.company,
                "industry": request.industry,
                "size": request.size,
                "website": request.website,
                "notes": request.notes,
            },
            session_id=session_id,
        )
        _end_session(session_id, "completed")
        return JSONResponse(status_code=200, content={
            "session_id": session_id,
            "task_type": "cold_outreach",
            "status": result.get("status", "completed"),
            "data": result,
            "timestamp": now_iso(),
        })
    except Exception as e:
        _end_session(session_id, "failed")
        logger.error("outreach_endpoint_error", error=str(e), session_id=session_id)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/detect-risk")
async def detect_risk(request: RiskDetectionRequest):
    session_id = generate_session_id()
    logger.info("risk_detection_request", session_id=session_id)
    _start_session(session_id, "risk_detection")

    try:
        result = await run_orchestrator(
            task_type="risk_detection",
            input_data={
                "deal_ids": request.deal_ids,
                "inactivity_threshold_days": request.inactivity_threshold_days,
                "check_all": request.check_all,
            },
            session_id=session_id,
        )
        _end_session(session_id, "completed")
        return JSONResponse(status_code=200, content={
            "session_id": session_id,
            "task_type": "risk_detection",
            "status": result.get("status", "completed"),
            "data": result,
            "timestamp": now_iso(),
        })
    except Exception as e:
        _end_session(session_id, "failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predict-churn")
async def predict_churn(request: ChurnPredictionRequest):
    session_id = generate_session_id()
    logger.info("churn_prediction_request", session_id=session_id)
    _start_session(session_id, "churn_prediction")

    try:
        result = await run_orchestrator(
            task_type="churn_prediction",
            input_data={
                "account_ids": request.account_ids,
                "top_n": request.top_n,
            },
            session_id=session_id,
        )
        _end_session(session_id, "completed")
        return JSONResponse(status_code=200, content={
            "session_id": session_id,
            "task_type": "churn_prediction",
            "status": result.get("status", "completed"),
            "data": result,
            "timestamp": now_iso(),
        })
    except Exception as e:
        _end_session(session_id, "failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/logs")
async def get_logs(session_id: Optional[str] = None, limit: int = 100):
    logs = get_logs_by_session(session_id) if session_id else get_all_logs()
    return {"logs": logs[:limit], "total": len(logs), "timestamp": now_iso()}


@app.get("/pipeline")
async def get_pipeline():
    return {
        "stats": get_pipeline_stats(),
        "accounts": get_all_accounts()[:20],
        "timestamp": now_iso(),
    }


@app.get("/emails")
async def get_emails(limit: int = 50):
    return {
        "emails": get_sent_emails()[:limit],
        "stats": get_email_stats(),
        "timestamp": now_iso(),
    }


@app.get("/sessions")
async def get_sessions():
    return {
        "sessions": _active_sessions,
        "total": len(_active_sessions),
        "running": len([s for s in _active_sessions.values() if s["status"] == "running"]),
        "timestamp": now_iso(),
    }


@app.get("/memory/stats")
async def get_memory_stats():
    return get_vector_store().stats()


@app.get("/recovery-report")
async def recovery_report():
    return get_recovery_engine().get_recovery_report()


@app.delete("/memory/clear")
async def clear_memory():
    if settings.environment == "production":
        raise HTTPException(status_code=403, detail="Not available in production.")
    get_vector_store().clear()
    return {"status": "cleared", "timestamp": now_iso()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)