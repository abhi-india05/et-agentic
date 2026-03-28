"""Outreach tracking routes — entries and metrics."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query

from backend.auth.deps import AuthUser, get_current_user
from backend.deps import get_outreach_entry_repo
from backend.models.schemas import OutreachEntryStatusUpdate
from backend.repositories.outreach_entries import OutreachEntryRepository
from backend.utils.errors import APIError
from backend.utils.helpers import clamp_page_size, now_iso

router = APIRouter(tags=["outreach"])


@router.get("/entries")
async def get_outreach_entries(
    page: int = 1,
    page_size: Optional[int] = None,
    status: Optional[str] = None,
    company: Optional[str] = None,
    product_id: Optional[str] = None,
    user: AuthUser = Depends(get_current_user),
    repo: OutreachEntryRepository = Depends(get_outreach_entry_repo),
) -> Dict[str, Any]:
    normalized_size = clamp_page_size(page_size or 50, default=50, max_value=200)
    entries, total = await repo.list_entries(
        user_id=user.user_id,
        page=max(1, page),
        page_size=normalized_size,
        status=status,
        company=company,
        product_id=product_id,
    )
    return {
        "entries": [entry.model_dump() for entry in entries],
        "total": total,
        "page": max(1, page),
        "page_size": normalized_size,
        "timestamp": now_iso(),
    }


@router.patch("/entries/{entry_id}/status")
async def update_outreach_status(
    entry_id: str,
    update_data: OutreachEntryStatusUpdate,
    user: AuthUser = Depends(get_current_user),
    repo: OutreachEntryRepository = Depends(get_outreach_entry_repo),
) -> Dict[str, Any]:
    entry = await repo.get_entry(entry_id)
    if not entry:
        raise APIError(status_code=404, code="not_found", message="Outreach entry not found")
        
    if entry.user_id != user.user_id:
        raise APIError(status_code=403, code="forbidden", message="Cannot update entry for another user")
        
    updated = await repo.update_status(entry_id, update_data.status)
    if not updated:
        raise APIError(status_code=500, code="update_failed", message="Failed to update entry status")
        
    return {
        "entry": updated.model_dump(),
        "timestamp": now_iso()
    }
