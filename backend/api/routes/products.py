"""Product routes — CRUD + pagination + filtering."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Request, Response, status

from backend.auth.deps import AuthUser, get_current_user
from backend.config.settings import settings
from backend.deps import get_product_repo
from backend.models.schemas import (
    ProductCreateRequest,
    ProductResponse,
    ProductUpdateRequest,
)
from backend.repositories.products import ProductInDB, ProductRepository
from backend.services import product_service
from backend.utils.helpers import clamp_page_size

router = APIRouter(prefix="/products", tags=["products"])


def _normalized_page_size(
    page_size: Optional[int],
    limit: Optional[int] = None,
) -> int:
    desired = limit if limit is not None else page_size if page_size is not None else settings.default_page_size
    return clamp_page_size(desired, default=settings.default_page_size, max_value=settings.max_page_size)


def _apply_pagination_headers(
    response: Response,
    *,
    page: int,
    page_size: int,
    total: int,
) -> None:
    response.headers["X-Page"] = str(page)
    response.headers["X-Page-Size"] = str(page_size)
    response.headers["X-Total-Count"] = str(total)


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


@router.post("", response_model=ProductResponse)
async def create_product(
    req: ProductCreateRequest,
    request: Request,
    user: AuthUser = Depends(get_current_user),
    repo: ProductRepository = Depends(get_product_repo),
) -> ProductResponse:
    product = await product_service.create_product(
        user=user,
        repo=repo,
        name=req.name,
        description=req.description,
        request_id=request.state.request_id,
    )
    return _product_response(product)


@router.get("", response_model=List[ProductResponse])
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
    normalized = _normalized_page_size(page_size, limit)
    products, total = await product_service.list_products(
        user=user,
        repo=repo,
        page=max(1, page),
        page_size=normalized,
        name=name,
        created_from=created_from,
        created_to=created_to,
        include_deleted=include_deleted,
    )
    _apply_pagination_headers(response, page=max(1, page), page_size=normalized, total=total)
    return [_product_response(p) for p in products]


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: str,
    user: AuthUser = Depends(get_current_user),
    repo: ProductRepository = Depends(get_product_repo),
) -> ProductResponse:
    product = await product_service.get_product(
        user=user,
        repo=repo,
        product_id=product_id,
    )
    return _product_response(product)


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: str,
    req: ProductUpdateRequest,
    request: Request,
    user: AuthUser = Depends(get_current_user),
    repo: ProductRepository = Depends(get_product_repo),
) -> ProductResponse:
    fields_set = getattr(req, "model_fields_set", set())
    product = await product_service.update_product(
        user=user,
        repo=repo,
        product_id=product_id,
        name=req.name,
        description=req.description,
        name_set="name" in fields_set,
        description_set="description" in fields_set,
        request_id=request.state.request_id,
    )
    return _product_response(product)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: str,
    request: Request,
    user: AuthUser = Depends(get_current_user),
    repo: ProductRepository = Depends(get_product_repo),
) -> Response:
    await product_service.soft_delete_product(
        user=user,
        repo=repo,
        product_id=product_id,
        request_id=request.state.request_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
