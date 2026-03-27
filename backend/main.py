from contextlib import asynccontextmanager
from typing import Any, Dict, Optional, List

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config.settings import settings
from backend.auth.deps import AuthUser, get_current_user
from backend.auth.jwt import create_access_token
from backend.auth.passwords import hash_password, verify_password
from backend.deps import get_product_repo, get_user_repo
from backend.repositories.products import ProductRepository
from backend.repositories.users import UserRepository
from backend.utils.logger import configure_logging, get_logger, get_all_logs, get_logs_by_session
from backend.utils.helpers import generate_session_id, now_iso

configure_logging(log_level=settings.log_level, environment=settings.environment)

import asyncio

from backend.models.schemas import (
    AuthLoginRequest,
    AuthMeResponse,
    AuthRegisterRequest,
    AuthTokenResponse,
    ProductCreateRequest,
    ProductResponse,
    ProductUpdateRequest,
    OutreachRequest,
    RiskDetectionRequest,
    ChurnPredictionRequest,
    SendEmailRequest,
    SendSequencesRequest,
)
from backend.agents.orchestrator import run_orchestrator
from backend.agents.failure_recovery import get_recovery_engine
from backend.tools.email_tool import get_email_stats, get_sent_emails, get_email_client
from backend.tools.crm_tool import get_pipeline_stats, get_all_accounts
from backend.memory.vector_store import get_vector_store

logger = get_logger("main")

_active_sessions: Dict[str, Dict[str, Any]] = {}


def _set_auth_cookie(response: Response, token: str, *, max_age_seconds: int) -> None:
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        httponly=True,
        secure=settings.resolved_auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        domain=settings.auth_cookie_domain,
        max_age=max_age_seconds,
        path="/",
    )


def _clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.auth_cookie_name,
        domain=settings.auth_cookie_domain,
        path="/",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "revops_ai_startup",
        environment=settings.environment,
        llm_provider=settings.llm_provider,
        model=settings.openai_model,
        embedding_model=settings.openai_embedding_model,
        has_openai_key=settings.has_openai_key,
        mock_email=settings.is_mock_email,
    )

    if settings.auth_enabled:
        secret = (settings.auth_secret_key or "").strip()
        if secret == "change-me" or len(secret) < 32:
            msg = "AUTH_SECRET_KEY is weak (use a random 32+ char secret)"
            if (settings.environment or "").strip().lower() == "production":
                raise RuntimeError(msg)
            logger.warning("weak_auth_secret", detail=msg)

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
    allow_origins=settings.cors_origins_list,
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
        "llm_provider": settings.llm_provider,
        "llm_model": settings.openai_model,
        "openai_configured": settings.has_openai_key,
        "email_mode": "live" if not settings.is_mock_email else "mock",
        "vector_store": store.stats(),
        "email_stats": get_email_stats(),
        "active_sessions": len([s for s in _active_sessions.values() if s["status"] == "running"]),
    }


@app.post("/auth/login", response_model=AuthTokenResponse)
async def auth_login(
    req: AuthLoginRequest,
    response: Response,
    user_repo: UserRepository = Depends(get_user_repo),
):
    expires = settings.auth_token_expire_minutes * 60

    if not settings.auth_enabled:
        token = create_access_token(subject="anonymous", username="anonymous", is_admin=False)
        _set_auth_cookie(response, token, max_age_seconds=expires)
        return AuthTokenResponse(access_token=token, expires_in=expires)

    # Back-compat admin login from env.
    if req.username == settings.auth_username and req.password == settings.auth_password:
        token = create_access_token(subject=settings.auth_username, username=req.username, is_admin=True)
        _set_auth_cookie(response, token, max_age_seconds=expires)
        return AuthTokenResponse(access_token=token, expires_in=expires)

    user = await user_repo.get_by_username(req.username)
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_access_token(subject=user.user_id, username=user.username, is_admin=False)
    _set_auth_cookie(response, token, max_age_seconds=expires)
    return AuthTokenResponse(access_token=token, expires_in=expires)


@app.post("/auth/register", response_model=AuthTokenResponse)
async def auth_register(
    req: AuthRegisterRequest,
    response: Response,
    user_repo: UserRepository = Depends(get_user_repo),
):
    if not settings.auth_enabled:
        raise HTTPException(status_code=400, detail="Registration is disabled when AUTH_ENABLED=false")

    if req.username == settings.auth_username:
        raise HTTPException(status_code=409, detail="Username is reserved")

    try:
        user = await user_repo.create_user(username=req.username, password_hash=hash_password(req.password))
    except Exception as e:
        msg = str(e).lower()
        if "duplicate" in msg or "exists" in msg:
            raise HTTPException(status_code=409, detail="Username already exists")
        raise

    expires = settings.auth_token_expire_minutes * 60
    token = create_access_token(subject=user.user_id, username=user.username, is_admin=False)
    _set_auth_cookie(response, token, max_age_seconds=expires)
    return AuthTokenResponse(access_token=token, expires_in=expires)


@app.post("/auth/logout")
async def auth_logout(response: Response):
    _clear_auth_cookie(response)
    return {"ok": True, "timestamp": now_iso()}


@app.get("/auth/me", response_model=AuthMeResponse)
async def auth_me(user: AuthUser = Depends(get_current_user)):
    return AuthMeResponse(user_id=user.user_id, username=user.username, is_admin=user.is_admin)


@app.post("/products", response_model=ProductResponse)
async def create_product(
    req: ProductCreateRequest,
    user: AuthUser = Depends(get_current_user),
    repo: ProductRepository = Depends(get_product_repo),
):
    product = await repo.create_product(owner_user_id=user.user_id, name=req.name, description=req.description)
    return ProductResponse(**product.__dict__)


@app.get("/products", response_model=List[ProductResponse])
async def list_products(
    limit: int = 50,
    user: AuthUser = Depends(get_current_user),
    repo: ProductRepository = Depends(get_product_repo),
):
    products = await repo.list_products(owner_user_id=user.user_id, limit=limit)
    return [ProductResponse(**p.__dict__) for p in products]


@app.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: str,
    user: AuthUser = Depends(get_current_user),
    repo: ProductRepository = Depends(get_product_repo),
):
    product = await repo.get_product(owner_user_id=user.user_id, product_id=product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductResponse(**product.__dict__)


@app.put("/products/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: str,
    req: ProductUpdateRequest,
    user: AuthUser = Depends(get_current_user),
    repo: ProductRepository = Depends(get_product_repo),
):
    fields_set = getattr(req, "model_fields_set", set())
    name_set = "name" in fields_set
    desc_set = "description" in fields_set
    if name_set and not req.name:
        raise HTTPException(status_code=422, detail="Name cannot be empty")
    product = await repo.update_product(
        owner_user_id=user.user_id,
        product_id=product_id,
        name=req.name,
        description=req.description,
        name_set=name_set,
        description_set=desc_set,
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductResponse(**product.__dict__)


@app.post("/run-outreach")
async def run_outreach(request: OutreachRequest, _user: AuthUser = Depends(get_current_user)):
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
                "product_name": request.product_name,
                "product_description": request.product_description,
                "auto_send": request.auto_send,
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
async def detect_risk(request: RiskDetectionRequest, _user: AuthUser = Depends(get_current_user)):
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
async def predict_churn(request: ChurnPredictionRequest, _user: AuthUser = Depends(get_current_user)):
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
async def get_logs(
    session_id: Optional[str] = None,
    limit: int = 100,
    _user: AuthUser = Depends(get_current_user),
):
    logs = get_logs_by_session(session_id) if session_id else get_all_logs()
    return {"logs": logs[:limit], "total": len(logs), "timestamp": now_iso()}


@app.get("/pipeline")
async def get_pipeline(_user: AuthUser = Depends(get_current_user)):
    return {
        "stats": get_pipeline_stats(),
        "accounts": get_all_accounts()[:20],
        "timestamp": now_iso(),
    }


@app.get("/emails")
async def get_emails(limit: int = 50, _user: AuthUser = Depends(get_current_user)):
    return {
        "emails": get_sent_emails()[:limit],
        "stats": get_email_stats(),
        "timestamp": now_iso(),
    }

@app.post("/send-email")
async def send_email(req: SendEmailRequest, _user: AuthUser = Depends(get_current_user)):
    # Send via SMTP if configured, otherwise this will be recorded as mock.
    client = get_email_client()
    result = await asyncio.to_thread(
        client.send_email,
        to_email=req.to_email,
        to_name=req.to_name or "",
        subject=req.subject,
        body_text=req.body_text,
        body_html=req.body_html,
    )
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "email failed"))
    return {"result": result, "timestamp": now_iso()}


@app.post("/send-sequences")
async def send_sequences(req: SendSequencesRequest, _user: AuthUser = Depends(get_current_user)):
    client = get_email_client()
    all_results = []
    total_sent = 0
    total_failed = 0

    for seq in req.sequences:
        email_payloads = [
            {
                "subject": e.subject,
                "body": e.body,
                "from_email": e.from_email,
                "from_name": e.from_name,
            }
            for e in seq.emails
        ]
        result = await asyncio.to_thread(
            client.send_sequence,
            to_email=seq.lead_email,
            to_name=seq.lead_name or "",
            emails=email_payloads,
            sequence_id=seq.sequence_id or generate_session_id(),
        )
        all_results.append(result)
        total_sent += int(result.get("sent", 0))
        total_failed += int(result.get("failed", 0))

    return {
        "results": all_results,
        "summary": {
            "total_sequences": len(all_results),
            "sent": total_sent,
            "failed": total_failed,
        },
        "timestamp": now_iso(),
    }


@app.get("/sessions")
async def get_sessions(_user: AuthUser = Depends(get_current_user)):
    return {
        "sessions": _active_sessions,
        "total": len(_active_sessions),
        "running": len([s for s in _active_sessions.values() if s["status"] == "running"]),
        "timestamp": now_iso(),
    }


@app.get("/memory/stats")
async def get_memory_stats(_user: AuthUser = Depends(get_current_user)):
    return get_vector_store().stats()


@app.get("/recovery-report")
async def recovery_report(_user: AuthUser = Depends(get_current_user)):
    return get_recovery_engine().get_recovery_report()


@app.delete("/memory/clear")
async def clear_memory(_user: AuthUser = Depends(get_current_user)):
    if settings.environment == "production":
        raise HTTPException(status_code=403, detail="Not available in production.")
    get_vector_store().clear()
    return {"status": "cleared", "timestamp": now_iso()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
