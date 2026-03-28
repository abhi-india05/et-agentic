from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.encoders import jsonable_encoder
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
            "details": jsonable_encoder(details),
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

    response: Optional[Response] = None
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        if rate_limit_result is not None:
            response.headers["X-RateLimit-Remaining"] = str(rate_limit_result.remaining)
        logger.info(
            "http_request_complete",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=status_code,
        )
        return response
    finally:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        get_metrics_registry().record_request(
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            duration_ms=duration_ms,
        )
        clear_context()

@app.exception_handler(APIError)
async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    return _error_response(
        request_id=getattr(request.state, "request_id", generate_request_id()),
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=exc.details,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return _error_response(
        request_id=getattr(request.state, "request_id", generate_request_id()),
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code="validation_error",
        message="Request validation failed",
        details=exc.errors(),
    )


@app.exception_handler(PasswordValidationError)
async def password_validation_handler(request: Request, exc: PasswordValidationError) -> JSONResponse:
    return _error_response(
        request_id=getattr(request.state, "request_id", generate_request_id()),
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code="weak_password",
        message=str(exc),
    )


@app.exception_handler(AuthServiceError)
async def auth_service_error_handler(request: Request, exc: AuthServiceError) -> JSONResponse:
    status_code = status.HTTP_401_UNAUTHORIZED
    if isinstance(exc, RefreshTokenReuseError):
        status_code = status.HTTP_401_UNAUTHORIZED
    elif isinstance(exc, InvalidRefreshTokenError):
        status_code = status.HTTP_401_UNAUTHORIZED
    return _error_response(
        request_id=getattr(request.state, "request_id", generate_request_id()),
        status_code=status_code,
        code=exc.code,
        message=str(exc),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict):
        code = detail.get("code", "http_error")
        message = detail.get("message", "Request failed")
        details = detail.get("details")
    else:
        code = "http_error"
        message = str(detail)
        details = None
    return _error_response(
        request_id=getattr(request.state, "request_id", generate_request_id()),
        status_code=exc.status_code,
        code=code,
        message=message,
        details=details,
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", generate_request_id())
    logger.error(
        "unhandled_exception",
        request_id=request_id,
        path=str(request.url),
        method=request.method,
        error=str(exc),
        exc_info=True,
    )
    message = "An internal error occurred"
    details = str(exc) if not settings.is_production else None
    return _error_response(
        request_id=request_id,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="internal_error",
        message=message,
        details=details,
    )


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    database = await _database_health()
    return {
        "status": "healthy" if database.get("ready") else "degraded",
        "version": app.version,
        "environment": settings.environment,
        "timestamp": now_iso(),
        "llm_provider": settings.llm_provider,
        "llm_model": settings.openai_model,
        "openai_configured": settings.has_openai_key,
        "email_mode": "live" if not settings.is_mock_email else "mock",
        "vector_store": get_vector_store().stats(),
        "email_stats": get_email_stats(),
        "database": database,
    }


@app.post("/auth/login", response_model=AuthTokenResponse)
async def auth_login(
    req: AuthLoginRequest,
    request: Request,
    response: Response,
    user_repo: UserRepository = Depends(get_user_repo),
    refresh_repo: RefreshTokenRepository = Depends(get_refresh_token_repo),
) -> AuthTokenResponse:
    if not settings.auth_enabled:
        access = create_access_token(subject="anonymous", username="anonymous", role="user")
        _set_access_cookie(response, access["token"])
        return AuthTokenResponse(
            access_token=access["token"],
            expires_in=settings.auth_access_token_expire_seconds,
            refresh_expires_in=0,
            role="user",
        )

    login_limit = get_rate_limiter().check(
        f"login:{_client_ip(request)}:{req.username.lower()}",
        limit=settings.login_rate_limit_attempts,
        window_seconds=settings.login_rate_limit_window_seconds,
    )
    if not login_limit.allowed:
        raise APIError(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code="login_rate_limited",
            message="Too many login attempts. Please try again later.",
            details={"retry_after_seconds": login_limit.retry_after_seconds},
        )

    user = await user_repo.get_by_username(req.username)
    if not user or not verify_password(req.password, user.password_hash):
        raise APIError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="invalid_credentials",
            message="Invalid username or password",
        )

    updated_user = await user_repo.update_last_login(user.user_id) or user
    issued = await issue_token_pair(user=updated_user, refresh_repo=refresh_repo)
    _set_access_cookie(response, issued.access_token)
    _set_refresh_cookie(response, issued.refresh_token)
    bind_context(user_id=updated_user.user_id, username=updated_user.username, role=updated_user.role, session_id=issued.session_id)
    record_audit(
        session_id=issued.session_id,
        agent_name="auth",
        action="login",
        input_summary=f"User login for {updated_user.username}",
        output_summary="Access and refresh tokens issued",
        status="success",
        confidence=1.0,
    )
    return AuthTokenResponse(
        access_token=issued.access_token,
        expires_in=issued.access_expires_in,
        refresh_expires_in=issued.refresh_expires_in,
        role=issued.role,
    )


@app.post("/auth/register", response_model=AuthTokenResponse)
async def auth_register(
    req: AuthRegisterRequest,
    response: Response,
    user_repo: UserRepository = Depends(get_user_repo),
    refresh_repo: RefreshTokenRepository = Depends(get_refresh_token_repo),
) -> AuthTokenResponse:
    if not settings.auth_enabled:
        raise APIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="auth_disabled",
            message="Registration is disabled when authentication is disabled.",
        )
    if req.username.lower() == settings.auth_username.lower():
        raise APIError(status_code=status.HTTP_409_CONFLICT, code="reserved_username", message="Username is reserved")

    try:
        user = await user_repo.create_user(username=req.username, password_hash=hash_password(req.password), role="user")
    except Exception as exc:
        if "duplicate" in str(exc).lower() or "exists" in str(exc).lower():
            raise APIError(status_code=status.HTTP_409_CONFLICT, code="username_exists", message="Username already exists") from exc
        raise

    issued = await issue_token_pair(user=user, refresh_repo=refresh_repo)
    _set_access_cookie(response, issued.access_token)
    _set_refresh_cookie(response, issued.refresh_token)
    bind_context(user_id=user.user_id, username=user.username, role=user.role, session_id=issued.session_id)
    record_audit(
        session_id=issued.session_id,
        agent_name="auth",
        action="register",
        input_summary=f"User registration for {user.username}",
        output_summary="User created and tokens issued",
        status="success",
        confidence=1.0,
    )
    return AuthTokenResponse(
        access_token=issued.access_token,
        expires_in=issued.access_expires_in,
        refresh_expires_in=issued.refresh_expires_in,
        role=issued.role,
    )


@app.post("/auth/refresh", response_model=AuthTokenResponse)
async def auth_refresh(
    request: Request,
    response: Response,
    payload: Optional[AuthRefreshRequest] = None,
    user_repo: UserRepository = Depends(get_user_repo),
    refresh_repo: RefreshTokenRepository = Depends(get_refresh_token_repo),
) -> AuthTokenResponse:
    refresh_token = (payload.refresh_token if payload else None) or request.cookies.get(settings.auth_refresh_cookie_name)
    if not refresh_token:
        raise APIError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="missing_refresh_token",
            message="Refresh token is required",
        )

    issued, user = await rotate_refresh_token(refresh_token=refresh_token, refresh_repo=refresh_repo, user_repo=user_repo)
    _set_access_cookie(response, issued.access_token)
    _set_refresh_cookie(response, issued.refresh_token)
    bind_context(user_id=user.user_id, username=user.username, role=user.role, session_id=issued.session_id)
    record_audit(
        session_id=issued.session_id,
        agent_name="auth",
        action="refresh",
        input_summary=f"Refresh requested for {user.username}",
        output_summary="Tokens rotated successfully",
        status="success",
        confidence=1.0,
    )
    return AuthTokenResponse(
        access_token=issued.access_token,
        expires_in=issued.access_expires_in,
        refresh_expires_in=issued.refresh_expires_in,
        role=issued.role,
    )


@app.post("/auth/logout")
async def auth_logout(
    request: Request,
    response: Response,
    refresh_repo: RefreshTokenRepository = Depends(get_refresh_token_repo),
) -> Dict[str, Any]:
    refresh_token = request.cookies.get(settings.auth_refresh_cookie_name)
    if not refresh_token:
        try:
            payload = await request.json()
            if isinstance(payload, dict):
                refresh_token = payload.get("refresh_token")
        except Exception:
            refresh_token = None
    if refresh_token:
        await revoke_refresh_token(refresh_token=refresh_token, refresh_repo=refresh_repo, revoke_family=True)
    _clear_auth_cookies(response)
    return {"ok": True, "timestamp": now_iso()}


@app.get("/auth/me", response_model=AuthMeResponse)
async def auth_me(user: AuthUser = Depends(get_current_user)) -> AuthMeResponse:
    return AuthMeResponse(user_id=user.user_id, username=user.username, role=user.role, is_admin=user.is_admin)

@app.post("/products", response_model=ProductResponse)
async def create_product(
    req: ProductCreateRequest,
    request: Request,
    user: AuthUser = Depends(get_current_user),
    repo: ProductRepository = Depends(get_product_repo),
) -> ProductResponse:
    product = await repo.create_product(owner_user_id=user.user_id, name=req.name, description=req.description)
    record_audit(
        session_id=request.state.request_id,
        agent_name="product_api",
        action="create_product",
        input_summary=f"Create product '{req.name}'",
        output_summary=f"Created product {product.product_id}",
        status="success",
        confidence=1.0,
    )
    return _product_response(product)


@app.get("/products", response_model=List[ProductResponse])
async def list_products(
    response: Response,
    page: int = 1,
    page_size: Optional[int] = None,
    limit: Optional[int] = None,
    name: Optional[str] = None,
    created_from: Optional[str] = None,
    created_to: Optional[str] = None,
    include_deleted: bool = False,
    user: AuthUser = Depends(get_current_user),
    repo: ProductRepository = Depends(get_product_repo),
) -> List[ProductResponse]:
    normalized_page_size = _normalized_page_size(page_size, limit)
    products, total = await repo.list_products(
        owner_user_id=user.user_id,
        page=max(1, page),
        page_size=normalized_page_size,
        name=name,
        created_from=created_from,
        created_to=created_to,
        include_deleted=include_deleted,
    )
    _apply_pagination_headers(response, page=max(1, page), page_size=normalized_page_size, total=total)
    return [_product_response(product) for product in products]


@app.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: str,
    user: AuthUser = Depends(get_current_user),
    repo: ProductRepository = Depends(get_product_repo),
) -> ProductResponse:
    product = await repo.get_product(owner_user_id=user.user_id, product_id=product_id)
    if not product:
        raise APIError(status_code=status.HTTP_404_NOT_FOUND, code="product_not_found", message="Product not found")
    return _product_response(product)


@app.put("/products/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: str,
    req: ProductUpdateRequest,
    request: Request,
    user: AuthUser = Depends(get_current_user),
    repo: ProductRepository = Depends(get_product_repo),
) -> ProductResponse:
    fields_set = getattr(req, "model_fields_set", set())
    product = await repo.update_product(
        owner_user_id=user.user_id,
        product_id=product_id,
        name=req.name,
        description=req.description,
        name_set="name" in fields_set,
        description_set="description" in fields_set,
    )
    if not product:
        raise APIError(status_code=status.HTTP_404_NOT_FOUND, code="product_not_found", message="Product not found")
    record_audit(
        session_id=request.state.request_id,
        agent_name="product_api",
        action="update_product",
        input_summary=f"Update product {product_id}",
        output_summary="Product updated",
        status="success",
        confidence=1.0,
    )
    return _product_response(product)


@app.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: str,
    request: Request,
    user: AuthUser = Depends(get_current_user),
    repo: ProductRepository = Depends(get_product_repo),
) -> Response:
    deleted = await repo.soft_delete_product(owner_user_id=user.user_id, product_id=product_id)
    if not deleted:
        raise APIError(status_code=status.HTTP_404_NOT_FOUND, code="product_not_found", message="Product not found")
    record_audit(
        session_id=request.state.request_id,
        agent_name="product_api",
        action="delete_product",
        input_summary=f"Soft delete product {product_id}",
        output_summary="Product soft deleted",
        status="success",
        confidence=1.0,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _run_workflow(
    *,
    task_type: str,
    workflow_input: Dict[str, Any],
    request: Request,
    user: AuthUser,
    response: Response,
    session_repo: SessionRepository,
) -> Dict[str, Any]:
    session_id = generate_session_id()
    bind_context(session_id=session_id, user_id=user.user_id, username=user.username, role=user.role)
    await session_repo.create_session(
        session_id=session_id,
        owner_user_id=user.user_id,
        task_type=task_type,
        input_data=workflow_input,
        plan={"task_type": task_type, "status": "running"},
        request_id=request.state.request_id,
        status="running",
    )
    try:
        result = await run_orchestrator(
            task_type=task_type,
            input_data=workflow_input,
            session_id=session_id,
            user_id=user.user_id,
        )
        await session_repo.update_session(
            session_id=session_id,
            status=result.get("status", "completed"),
            plan=result.get("plan", {}),
        )
        response.headers["X-Session-ID"] = session_id
        return {
            "session_id": session_id,
            "task_type": task_type,
            "status": result.get("status", "completed"),
            "data": result,
            "timestamp": now_iso(),
        }
    except Exception as exc:
        await session_repo.update_session(
            session_id=session_id,
            status="failed",
            error=str(exc),
        )
        raise


@app.post("/run-outreach")
async def run_outreach(
    payload: OutreachRequest,
    request: Request,
    response: Response,
    user: AuthUser = Depends(get_current_user),
    product_repo: ProductRepository = Depends(get_product_repo),
    session_repo: SessionRepository = Depends(get_session_repo),
) -> Dict[str, Any]:
    product_context = await _resolve_product_context(
        user=user,
        repo=product_repo,
        product_id=payload.product_id,
        product_name=payload.product_name,
        product_description=payload.product_description,
    )
    workflow_input = {
        "company": payload.company,
        "industry": payload.industry,
        "size": payload.size,
        "website": payload.website,
        "notes": payload.notes,
        "product_context": product_context.model_dump(),
        "auto_send": payload.auto_send,
    }
    return await _run_workflow(
        task_type="cold_outreach",
        workflow_input=workflow_input,
        request=request,
        user=user,
        response=response,
        session_repo=session_repo,
    )


@app.post("/detect-risk")
async def detect_risk(
    payload: RiskDetectionRequest,
    request: Request,
    response: Response,
    user: AuthUser = Depends(get_current_user),
    product_repo: ProductRepository = Depends(get_product_repo),
    session_repo: SessionRepository = Depends(get_session_repo),
) -> Dict[str, Any]:
    product_context = await _resolve_product_context(user=user, repo=product_repo, product_id=payload.product_id)
    workflow_input = {
        "deal_ids": payload.deal_ids,
        "check_all": payload.check_all,
        "inactivity_threshold_days": payload.inactivity_threshold_days,
        "product_context": product_context.model_dump(),
    }
    return await _run_workflow(
        task_type="risk_detection",
        workflow_input=workflow_input,
        request=request,
        user=user,
        response=response,
        session_repo=session_repo,
    )


@app.post("/predict-churn")
async def predict_churn(
    payload: ChurnPredictionRequest,
    request: Request,
    response: Response,
    user: AuthUser = Depends(get_current_user),
    product_repo: ProductRepository = Depends(get_product_repo),
    session_repo: SessionRepository = Depends(get_session_repo),
) -> Dict[str, Any]:
    product_context = await _resolve_product_context(user=user, repo=product_repo, product_id=payload.product_id)
    workflow_input = {
        "account_ids": payload.account_ids,
        "top_n": payload.top_n,
        "product_context": product_context.model_dump(),
    }
    return await _run_workflow(
        task_type="churn_prediction",
        workflow_input=workflow_input,
        request=request,
        user=user,
        response=response,
        session_repo=session_repo,
    )

@app.get("/logs")
async def get_logs(
    response: Response,
    session_id: Optional[str] = None,
    page: int = 1,
    page_size: Optional[int] = None,
    user_id: Optional[str] = None,
    user: AuthUser = Depends(get_current_user),
) -> Dict[str, Any]:
    normalized_page_size = _normalized_page_size(page_size)
    scoped_user_id = user_id if user.is_admin and user_id else user.user_id
    logs = query_audit_logs(
        session_id=session_id,
        user_id=scoped_user_id,
        page=max(1, page),
        page_size=normalized_page_size,
    )
    _apply_pagination_headers(response, page=max(1, page), page_size=normalized_page_size, total=logs["total"])
    return {
        "logs": logs["items"],
        "total": logs["total"],
        "page": max(1, page),
        "page_size": normalized_page_size,
        "timestamp": now_iso(),
    }


@app.get("/sessions")
async def get_sessions(
    response: Response,
    page: int = 1,
    page_size: Optional[int] = None,
    status_filter: Optional[str] = None,
    created_from: Optional[str] = None,
    created_to: Optional[str] = None,
    owner_user_id: Optional[str] = None,
    user: AuthUser = Depends(get_current_user),
    repo: SessionRepository = Depends(get_session_repo),
) -> Dict[str, Any]:
    normalized_page_size = _normalized_page_size(page_size)
    scoped_owner_id = owner_user_id if user.is_admin and owner_user_id else user.user_id
    sessions, total, running = await repo.list_sessions(
        owner_user_id=scoped_owner_id,
        page=max(1, page),
        page_size=normalized_page_size,
        status=status_filter,
        created_from=created_from,
        created_to=created_to,
    )
    _apply_pagination_headers(response, page=max(1, page), page_size=normalized_page_size, total=total)
    return {
        "sessions": [_session_payload(item) for item in sessions],
        "total": total,
        "running": running,
        "page": max(1, page),
        "page_size": normalized_page_size,
        "timestamp": now_iso(),
    }


@app.get("/pipeline")
async def get_pipeline(_user: AuthUser = Depends(get_current_user)) -> Dict[str, Any]:
    return {
        "stats": get_pipeline_stats(),
        "accounts": get_all_accounts()[:20],
        "timestamp": now_iso(),
    }


@app.get("/emails")
async def get_emails(
    limit: int = 50,
    to_email: Optional[str] = None,
    sequence_id: Optional[str] = None,
    _user: AuthUser = Depends(get_current_user),
) -> Dict[str, Any]:
    return {
        "emails": get_sent_emails(to_email=to_email, sequence_id=sequence_id)[: max(1, limit)],
        "stats": get_email_stats(),
        "timestamp": now_iso(),
    }


@app.post("/send-email")
async def send_email(req: SendEmailRequest, _user: AuthUser = Depends(get_current_user)) -> Dict[str, Any]:
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
        raise APIError(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, code="email_failed", message=result.get("error", "Email failed"))
    return {"result": result, "timestamp": now_iso()}


@app.post("/send-sequences")
async def send_sequences(req: SendSequencesRequest, _user: AuthUser = Depends(get_current_user)) -> Dict[str, Any]:
    client = get_email_client()
    results: List[Dict[str, Any]] = []
    total_sent = 0
    total_failed = 0
    for sequence in req.sequences:
        payload = [
            {
                "subject": email.subject,
                "body": email.body,
                "from_email": email.from_email,
                "from_name": email.from_name,
            }
            for email in sequence.emails
        ]
        result = await asyncio.to_thread(
            client.send_sequence,
            to_email=sequence.lead_email,
            to_name=sequence.lead_name or "",
            emails=payload,
            sequence_id=sequence.sequence_id or generate_session_id(),
        )
        results.append(result)
        total_sent += int(result.get("sent", 0))
        total_failed += int(result.get("failed", 0))
    return {
        "results": results,
        "summary": {
            "total_sequences": len(results),
            "sent": total_sent,
            "failed": total_failed,
        },
        "timestamp": now_iso(),
    }

@app.get("/memory/stats")
async def get_memory_stats(user: AuthUser = Depends(get_current_user)) -> Dict[str, Any]:
    stats = get_vector_store().stats()
    if user.is_admin:
        return stats
    return {
        "namespace": user.user_id,
        "documents": stats.get("namespaces", {}).get(user.user_id, 0),
        "dimension": stats.get("dimension"),
        "faiss_available": stats.get("faiss_available"),
        "ttl_seconds": settings.memory_ttl_seconds,
        "max_documents_per_user": settings.memory_max_documents_per_user,
    }


@app.delete("/memory/clear")
async def clear_memory(
    namespace: Optional[str] = None,
    _user: AuthUser = Depends(require_role("admin")),
) -> Dict[str, Any]:
    if settings.is_production:
        raise APIError(status_code=status.HTTP_403_FORBIDDEN, code="not_allowed", message="Not available in production")
    get_vector_store().clear(namespace=namespace)
    return {"status": "cleared", "namespace": namespace or "all", "timestamp": now_iso()}


@app.get("/recovery-report")
async def recovery_report(_user: AuthUser = Depends(require_role("admin"))) -> Dict[str, Any]:
    return get_recovery_engine().get_recovery_report()


@app.get("/metrics")
async def metrics(_user: AuthUser = Depends(require_role("admin"))) -> Dict[str, Any]:
    return get_metrics_registry().snapshot()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=not settings.is_production)
