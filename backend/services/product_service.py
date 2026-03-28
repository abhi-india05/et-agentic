"""Product service — all product business logic lives here."""
from __future__ import annotations

from typing import List, Optional, Tuple

from backend.auth.deps import AuthUser
from backend.repositories.products import ProductInDB, ProductRepository
from backend.utils.errors import APIError
from backend.utils.logger import record_audit


async def create_product(
    *,
    user: AuthUser,
    repo: ProductRepository,
    name: str,
    description: Optional[str],
    request_id: str,
) -> ProductInDB:
    product = await repo.create_product(
        owner_user_id=user.user_id,
        name=name,
        description=description,
    )
    record_audit(
        session_id=request_id,
        agent_name="product_api",
        action="create_product",
        input_summary=f"Create product '{name}'",
        output_summary=f"Created product {product.product_id}",
        status="success",
        confidence=1.0,
    )
    return product


async def list_products(
    *,
    user: AuthUser,
    repo: ProductRepository,
    page: int,
    page_size: int,
    name: Optional[str] = None,
    created_from: Optional[str] = None,
    created_to: Optional[str] = None,
    include_deleted: bool = False,
) -> Tuple[List[ProductInDB], int]:
    return await repo.list_products(
        owner_user_id=user.user_id,
        page=max(1, page),
        page_size=page_size,
        name=name,
        created_from=created_from,
        created_to=created_to,
        include_deleted=include_deleted,
    )


async def get_product(
    *,
    user: AuthUser,
    repo: ProductRepository,
    product_id: str,
) -> ProductInDB:
    product = await repo.get_product(
        owner_user_id=user.user_id,
        product_id=product_id,
    )
    if not product:
        raise APIError(
            status_code=404,
            code="product_not_found",
            message="Product not found",
        )
    return product


async def update_product(
    *,
    user: AuthUser,
    repo: ProductRepository,
    product_id: str,
    name: Optional[str],
    description: Optional[str],
    name_set: bool,
    description_set: bool,
    request_id: str,
) -> ProductInDB:
    product = await repo.update_product(
        owner_user_id=user.user_id,
        product_id=product_id,
        name=name,
        description=description,
        name_set=name_set,
        description_set=description_set,
    )
    if not product:
        raise APIError(
            status_code=404,
            code="product_not_found",
            message="Product not found",
        )
    record_audit(
        session_id=request_id,
        agent_name="product_api",
        action="update_product",
        input_summary=f"Update product {product_id}",
        output_summary="Product updated",
        status="success",
        confidence=1.0,
    )
    return product


async def soft_delete_product(
    *,
    user: AuthUser,
    repo: ProductRepository,
    product_id: str,
    request_id: str,
) -> None:
    deleted = await repo.soft_delete_product(
        owner_user_id=user.user_id,
        product_id=product_id,
    )
    if not deleted:
        raise APIError(
            status_code=404,
            code="product_not_found",
            message="Product not found",
        )
    record_audit(
        session_id=request_id,
        agent_name="product_api",
        action="delete_product",
        input_summary=f"Soft delete product {product_id}",
        output_summary="Product soft deleted",
        status="success",
        confidence=1.0,
    )
