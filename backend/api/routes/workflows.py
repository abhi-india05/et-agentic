"""Workflow routes — outreach, risk detection, churn prediction."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Request, Response

from backend.agents.orchestrator import run_orchestrator
from backend.auth.deps import AuthUser, get_current_user
from backend.deps import get_product_repo, get_session_repo
from backend.models.schemas import (
    ChurnPredictionRequest,
    OutreachRequest,
    ProductContext,
    RiskDetectionRequest,
    OutreachEntry,
    OutreachEntryStatus
)
from backend.repositories.products import ProductRepository
from backend.repositories.sessions import SessionRepository
from backend.repositories.outreach_entries import OutreachEntryRepository
from backend.deps import get_product_repo, get_session_repo, get_outreach_entry_repo
from backend.utils.errors import APIError
from backend.utils.helpers import generate_session_id, now_iso, utcnow
from backend.utils.logger import bind_context

router = APIRouter(tags=["workflows"])

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


@router.post("/run-outreach")
async def run_outreach(
    payload: OutreachRequest,
    request: Request,
    response: Response,
    user: AuthUser = Depends(get_current_user),
    product_repo: ProductRepository = Depends(get_product_repo),
    session_repo: SessionRepository = Depends(get_session_repo),
    entry_repo: OutreachEntryRepository = Depends(get_outreach_entry_repo),
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
    result = await _run_workflow(
        task_type="cold_outreach",
        workflow_input=workflow_input,
        request=request,
        user=user,
        response=response,
        session_repo=session_repo,
    )
    
    # Extract sequences and create entries
    if result.get("status") in ("completed", "completed_with_errors") and "outreach_agent" in result.get("data", {}).get("agent_outputs", {}):
        sequences = result["data"]["agent_outputs"]["outreach_agent"].get("data", {}).get("sequences", [])
        for seq in sequences:
            status = OutreachEntryStatus.SENT if payload.auto_send else OutreachEntryStatus.DRAFT
            await entry_repo.create_entry(
                OutreachEntry(
                    id=seq.get("sequence_id", generate_session_id()),
                    user_id=user.user_id,
                    product_id=payload.product_id,
                    company_name=payload.company,
                    company_domain=payload.website,
                    outreach_type="email",
                    message=seq.get("sequence_strategy"),
                    status=status
                )
            )
            
    return result


@router.post("/detect-risk")
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


@router.post("/predict-churn")
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
