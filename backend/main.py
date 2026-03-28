from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.agents.failure_recovery import get_recovery_engine
from backend.agents.orchestrator import run_orchestrator
from backend.auth.deps import AuthUser, get_current_user, require_role
from backend.auth.jwt import create_access_token
from backend.auth.passwords import PasswordValidationError, hash_password, verify_password
from backend.config.settings import settings
from backend.db.mongo import close_clients, get_database
from backend.deps import get_product_repo, get_refresh_token_repo, get_session_repo, get_user_repo
from backend.memory.vector_store import get_vector_store
from backend.models.schemas import (
    AuthLoginRequest,
    AuthMeResponse,
    AuthRefreshRequest,
    AuthRegisterRequest,
    AuthTokenResponse,
    ChurnPredictionRequest,
    OutreachRequest,
    ProductContext,
    ProductCreateRequest,
    ProductResponse,
    ProductUpdateRequest,
    RiskDetectionRequest,
    SendEmailRequest,
    SendSequencesRequest,
)
from backend.repositories.products import ProductInDB, ProductRepository
from backend.repositories.refresh_tokens import RefreshTokenRepository
from backend.repositories.sessions import SessionRepository
from backend.repositories.users import UserRepository
from backend.services.auth_service import (
    AuthServiceError,
    InvalidRefreshTokenError,
    RefreshTokenReuseError,
    issue_token_pair,
    revoke_refresh_token,
    rotate_refresh_token,
)
from backend.services.observability import get_metrics_registry
from backend.services.rate_limit import get_rate_limiter
from backend.tools.crm_tool import get_all_accounts, get_pipeline_stats
from backend.tools.email_tool import get_email_client, get_email_stats, get_sent_emails
from backend.utils.helpers import clamp_page_size, generate_request_id, generate_session_id, now_iso
from backend.utils.logger import (
    bind_context,
    clear_context,
    configure_logging,
    get_logger,
    query_audit_logs,
    record_audit,
)

configure_logging(log_level=settings.log_level, environment=settings.environment)
logger = get_logger("main")

RATE_LIMIT_EXEMPT_PATHS = {"/health", "/openapi.json", "/docs", "/redoc"}
REFRESH_COOKIE_PATH = "/auth"


class APIError(Exception):
    def __init__(self, *, status_code: int, code: str, message: str, details: Any = None) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "").strip()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _error_payload(*, request_id: str, code: str, message: str, details: Any = None) -> Dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": request_id,
            "timestamp": now_iso(),
        }
    }


def _error_response(
    *,
    request_id: str,
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
    headers: Optional[Dict[str, str]] = None,
) -> JSONResponse:
    response = JSONResponse(
        status_code=status_code,
        content=_error_payload(request_id=request_id, code=code, message=message, details=details),
    )
    response.headers["X-Request-ID"] = request_id
    for key, value in (headers or {}).items():
        response.headers[key] = value
    return response


def _set_access_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        httponly=True,
        secure=settings.resolved_auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        domain=settings.auth_cookie_domain,
        max_age=settings.auth_access_token_expire_seconds,
        path="/",
    )


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.auth_refresh_cookie_name,
        value=token,
        httponly=True,
        secure=settings.resolved_auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        domain=settings.auth_cookie_domain,
        max_age=settings.auth_refresh_token_expire_seconds,
        path=REFRESH_COOKIE_PATH,
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(key=settings.auth_cookie_name, domain=settings.auth_cookie_domain, path="/")
    response.delete_cookie(key=settings.auth_refresh_cookie_name, domain=settings.auth_cookie_domain, path=REFRESH_COOKIE_PATH)


def _apply_pagination_headers(response: Response, *, page: int, page_size: int, total: int) -> None:
    response.headers["X-Page"] = str(page)
    response.headers["X-Page-Size"] = str(page_size)
    response.headers["X-Total-Count"] = str(total)


def _normalized_page_size(page_size: Optional[int], limit: Optional[int] = None) -> int:
    desired = limit if limit is not None else page_size if page_size is not None else settings.default_page_size
    return clamp_page_size(desired, default=settings.default_page_size, max_value=settings.max_page_size)


def _product_response(product: ProductInDB) -> ProductResponse:
    return ProductResponse(
        product_id=product.product_id,
        owner_user_id=product.owner_user_id,
        name=product.name,
        description=product.description,
        created_at=product.created_at,
        updated_at=product.updated_at,
        is_deleted=product.is_deleted,
        deleted_at=product.deleted_at,
    )


def _session_payload(item: Any) -> Dict[str, Any]:
    return {
        "session_id": item.session_id,
        "owner_user_id": item.owner_user_id,
        "task_type": item.task_type,
        "status": item.status,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "completed_at": item.completed_at,
        "error": item.error,
        "request_id": item.request_id,
    }


async def _resolve_product_context(
    *,
    user: AuthUser,
    repo: ProductRepository,
    product_id: Optional[str] = None,
    product_name: Optional[str] = None,
    product_description: Optional[str] = None,
) -> ProductContext:
    if product_id:
        product = await repo.get_product(owner_user_id=user.user_id, product_id=product_id)
        if not product:
            raise APIError(status_code=404, code="product_not_found", message="Product not found")
        return ProductContext(
            product_id=product.product_id,
            name=product.name,
            description=product.description or "",
            source="database",
        )
    if product_name or product_description:
        return ProductContext(
            product_id=None,
            name=product_name or "",
            description=product_description or "",
            source="request",
        )
    latest = await repo.get_latest_product(owner_user_id=user.user_id)
    if latest:
        return ProductContext(
            product_id=latest.product_id,
            name=latest.name,
            description=latest.description or "",
            source="latest_product",
        )
    return ProductContext(source="none")


async def _seed_admin_user(user_repo: UserRepository) -> None:
    if not settings.auth_enabled:
        return
    admin_password_hash = hash_password(settings.auth_password)
    await user_repo.ensure_admin_user(username=settings.auth_username, password_hash=admin_password_hash)


async def _initialize_runtime() -> None:
    settings.validate_runtime()
    store = get_vector_store()
    store.load()
    logger.info("vector_store_ready", **store.stats())

    if settings.is_test:
        return

    try:
        await get_database().command("ping")
        user_repo = get_user_repo()
        product_repo = get_product_repo()
        session_repo = get_session_repo()
        refresh_repo = get_refresh_token_repo()
        await user_repo.ensure_indexes()
        await product_repo.ensure_indexes()
        await session_repo.ensure_indexes()
        await refresh_repo.ensure_indexes()
        await _seed_admin_user(user_repo)
        logger.info("runtime_persistence_ready")
    except Exception as exc:
        if settings.is_production:
            raise
        logger.warning("runtime_persistence_unavailable", error=str(exc))


async def _database_health() -> Dict[str, Any]:
    if settings.is_test:
        return {"ready": True, "mode": "test"}
    try:
        await get_database().command("ping")
        return {"ready": True, "mode": "mongo"}
    except Exception as exc:
        return {"ready": False, "error": str(exc)}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info(
        "revops_ai_startup",
        environment=settings.environment,
        llm_provider=settings.llm_provider,
        model=settings.openai_model,
        embedding_model=settings.openai_embedding_model,
        has_openai_key=settings.has_openai_key,
        mock_email=settings.is_mock_email,
    )
    await _initialize_runtime()
    yield
    logger.info("revops_ai_shutdown")
    get_vector_store().save()
    close_clients()


app = FastAPI(
    title="RevOps AI - Autonomous Sales and Revenue Intelligence",
    description="Production-grade RevOps AI backend with hardened auth, persistence, and agent workflows.",
    version="2.0.0",
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


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or generate_request_id()
    client_ip = _client_ip(request)
    request.state.request_id = request_id
    bind_context(request_id=request_id, method=request.method, path=request.url.path, client_ip=client_ip)

    rate_limit_result = None
    status_code = 500
    started_at = time.perf_counter()

    if request.url.path not in RATE_LIMIT_EXEMPT_PATHS and request.method.upper() != "OPTIONS":
        rate_limit_result = get_rate_limiter().check(
            f"global:{client_ip}",
            limit=settings.global_rate_limit_requests_per_minute,
            window_seconds=60,
        )
        if not rate_limit_result.allowed:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            get_metrics_registry().record_request(
                method=request.method,
                path=request.url.path,
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                duration_ms=duration_ms,
            )
            response = _error_response(
                request_id=request_id,
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                code="rate_limit_exceeded",
                message="Too many requests. Please try again later.",
                details={"retry_after_seconds": rate_limit_result.retry_after_seconds},
                headers={
                    "Retry-After": str(rate_limit_result.retry_after_seconds),
                    "X-RateLimit-Remaining": "0",
                },
            )
            clear_context()
            return response

    try:
        response = await call_next(request)
        status_code = response.status_code
    finally:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        get_metrics_registry().record_request(
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            duration_ms=duration_ms,
        )

    response.headers["X-Request-ID"] = request_id
    if rate_limit_result is not None:
        response.headers["X-RateLimit-Remaining"] = str(rate_limit_result.remaining)
    logger.info(
        "http_request_complete",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        status_code=status_code,
        duration_ms=duration_ms,
    )
    clear_context()
    return response
