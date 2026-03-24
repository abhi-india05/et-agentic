from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional, List
import asyncio

from backend.config.settings import settings
from backend.models.schemas import (
    OutreachRequest,
    RiskDetectionRequest,
    ChurnPredictionRequest,
)
from backend.agents.orchestrator import run_orchestrator
from backend.tools.email_tool import get_email_stats, get_sent_emails
from backend.tools.crm_tool import get_pipeline_stats, get_all_accounts
from backend.memory.vector_store import get_vector_store
from backend.utils.logger import configure_logging, get_all_logs, get_logs_by_session, get_logger
from backend.utils.helpers import generate_session_id, now_iso

configure_logging()
logger = get_logger("main")

_active_sessions: Dict[str, Dict[str, Any]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("RevOps AI starting up", environment=settings.environment)
    store = get_vector_store()
    store.load()
    logger.info("Vector store loaded", stats=store.stats())
    yield
    logger.info("RevOps AI shutting down")
    store.save()


app = FastAPI(
    title="RevOps AI — Autonomous Sales & Revenue Intelligence",
    description="Multi-agent AI system for autonomous sales operations",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "environment": settings.environment,
        "timestamp": now_iso(),
        "vector_store": get_vector_store().stats(),
        "email_stats": get_email_stats(),
    }


@app.post("/run-outreach")
async def run_outreach(request: OutreachRequest):
    session_id = generate_session_id()
    logger.info("Cold outreach request received", company=request.company, session_id=session_id)

    _active_sessions[session_id] = {
        "status": "running",
        "task_type": "cold_outreach",
        "started_at": now_iso(),
    }

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
        _active_sessions[session_id]["status"] = "completed"
        _active_sessions[session_id]["completed_at"] = now_iso()

        return JSONResponse(
            status_code=200,
            content={
                "session_id": session_id,
                "task_type": "cold_outreach",
                "status": result.get("status", "completed"),
                "data": result,
                "timestamp": now_iso(),
            },
        )
    except Exception as e:
        _active_sessions[session_id]["status"] = "failed"
        logger.error("Outreach run failed", error=str(e), session_id=session_id)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/detect-risk")
async def detect_risk(request: RiskDetectionRequest):
    session_id = generate_session_id()
    logger.info("Risk detection request received", session_id=session_id)

    _active_sessions[session_id] = {
        "status": "running",
        "task_type": "risk_detection",
        "started_at": now_iso(),
    }

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
        _active_sessions[session_id]["status"] = "completed"
        _active_sessions[session_id]["completed_at"] = now_iso()

        return JSONResponse(
            status_code=200,
            content={
                "session_id": session_id,
                "task_type": "risk_detection",
                "status": result.get("status", "completed"),
                "data": result,
                "timestamp": now_iso(),
            },
        )
    except Exception as e:
        _active_sessions[session_id]["status"] = "failed"
        logger.error("Risk detection failed", error=str(e), session_id=session_id)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/predict-churn")
async def predict_churn(request: ChurnPredictionRequest):
    session_id = generate_session_id()
    logger.info("Churn prediction request received", session_id=session_id)

    _active_sessions[session_id] = {
        "status": "running",
        "task_type": "churn_prediction",
        "started_at": now_iso(),
    }

    try:
        result = await run_orchestrator(
            task_type="churn_prediction",
            input_data={
                "account_ids": request.account_ids,
                "top_n": request.top_n,
            },
            session_id=session_id,
        )
        _active_sessions[session_id]["status"] = "completed"
        _active_sessions[session_id]["completed_at"] = now_iso()

        return JSONResponse(
            status_code=200,
            content={
                "session_id": session_id,
                "task_type": "churn_prediction",
                "status": result.get("status", "completed"),
                "data": result,
                "timestamp": now_iso(),
            },
        )
    except Exception as e:
        _active_sessions[session_id]["status"] = "failed"
        logger.error("Churn prediction failed", error=str(e), session_id=session_id)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/logs")
async def get_logs(session_id: Optional[str] = None, limit: int = 100):
    if session_id:
        logs = get_logs_by_session(session_id)
    else:
        logs = get_all_logs()
    return {
        "logs": logs[:limit],
        "total": len(logs),
        "timestamp": now_iso(),
    }


@app.get("/pipeline")
async def get_pipeline():
    stats = get_pipeline_stats()
    accounts = get_all_accounts()
    return {
        "stats": stats,
        "accounts": accounts[:20],
        "timestamp": now_iso(),
    }


@app.get("/emails")
async def get_emails(limit: int = 50):
    emails = get_sent_emails()
    return {
        "emails": emails[:limit],
        "stats": get_email_stats(),
        "timestamp": now_iso(),
    }


@app.get("/sessions")
async def get_sessions():
    return {
        "sessions": _active_sessions,
        "total": len(_active_sessions),
        "timestamp": now_iso(),
    }


@app.get("/memory/stats")
async def get_memory_stats():
    store = get_vector_store()
    return store.stats()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
