from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Protocol, Tuple

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from backend.utils.helpers import parse_date, utcnow


@dataclass(frozen=True)
class ProductInDB:
    product_id: str
    owner_user_id: str
    name: str
    description: Optional[str]
    created_at: object
    updated_at: object
    is_deleted: bool = False
    deleted_at: Optional[object] = None


class ProductRepository(Protocol):
    async def ensure_indexes(self) -> None: ...
    async def create_product(self, *, owner_user_id: str, name: str, description: Optional[str]) -> ProductInDB: ...
    async def list_products(
        self,
        *,
        owner_user_id: str,
        page: int,
        page_size: int,
        name: Optional[str] = None,
        created_from: Optional[str] = None,
        created_to: Optional[str] = None,
        include_deleted: bool = False,
    ) -> Tuple[List[ProductInDB], int]: ...
    async def get_product(
        self,
        *,
        owner_user_id: str,
        product_id: str,
        include_deleted: bool = False,
    ) -> Optional[ProductInDB]: ...
    async def get_latest_product(self, *, owner_user_id: str) -> Optional[ProductInDB]: ...
    async def update_product(
        self,
        *,
        owner_user_id: str,
        product_id: str,
        name: Optional[str],
        description: Optional[str],
        name_set: bool,
        description_set: bool,
    ) -> Optional[ProductInDB]: ...
    async def soft_delete_product(self, *, owner_user_id: str, product_id: str) -> bool: ...


def _doc_to_product(doc: Dict[str, object]) -> ProductInDB:
    now = utcnow()
    return ProductInDB(
        product_id=str(doc["_id"]),
        owner_user_id=str(doc.get("owner_user_id", "")),
        name=str(doc.get("name", "")),
        description=doc.get("description"),
        created_at=doc.get("created_at") or now,
        updated_at=doc.get("updated_at") or now,
        is_deleted=bool(doc.get("is_deleted", False)),
        deleted_at=doc.get("deleted_at"),
    )


def _build_created_at_filter(created_from: Optional[str], created_to: Optional[str]) -> Dict[str, object]:
    created_at: Dict[str, object] = {}
    from_dt = parse_date(created_from or "")
    to_dt = parse_date(created_to or "")
    if from_dt:
        created_at["$gte"] = from_dt
    if to_dt:
        created_at["$lte"] = to_dt
    return created_at


class MongoProductRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._col = db["products"]
        self._indexes_ready = False

    async def ensure_indexes(self) -> None:
        if self._indexes_ready:
            return
        await self._col.create_index([("owner_user_id", 1), ("created_at", -1)])
        await self._col.create_index([("owner_user_id", 1), ("updated_at", -1)])
        await self._col.create_index([("owner_user_id", 1), ("is_deleted", 1), ("created_at", -1)])
        self._indexes_ready = True

    async def create_product(self, *, owner_user_id: str, name: str, description: Optional[str]) -> ProductInDB:
        await self.ensure_indexes()
        now = utcnow()
        doc = {
            "owner_user_id": owner_user_id,
            "name": name,
            "description": description,
            "created_at": now,
            "updated_at": now,
            "is_deleted": False,
            "deleted_at": None,
        }
        result = await self._col.insert_one(doc)
        doc["_id"] = result.inserted_id
        return _doc_to_product(doc)

    async def list_products(
        self,
        *,
        owner_user_id: str,
        page: int,
        page_size: int,
        name: Optional[str] = None,
        created_from: Optional[str] = None,
        created_to: Optional[str] = None,
        include_deleted: bool = False,
    ) -> Tuple[List[ProductInDB], int]:
        await self.ensure_indexes()
        filters: Dict[str, object] = {"owner_user_id": owner_user_id}
        if not include_deleted:
            filters["is_deleted"] = False
        if name:
            filters["name"] = {"$regex": name, "$options": "i"}
        created_at = _build_created_at_filter(created_from, created_to)
        if created_at:
            filters["created_at"] = created_at
        total = await self._col.count_documents(filters)
        cursor = (
            self._col.find(filters)
            .sort("created_at", -1)
            .skip(max(0, (page - 1) * page_size))
            .limit(page_size)
        )
        items: List[ProductInDB] = []
        async for doc in cursor:
            items.append(_doc_to_product(doc))
        return items, total

    async def get_product(
        self,
        *,
        owner_user_id: str,
        product_id: str,
        include_deleted: bool = False,
    ) -> Optional[ProductInDB]:
        await self.ensure_indexes()
        try:
            oid = ObjectId(product_id)
        except Exception:
            return None
        filters: Dict[str, object] = {"_id": oid, "owner_user_id": owner_user_id}
        if not include_deleted:
            filters["is_deleted"] = False
        doc = await self._col.find_one(filters)
        return _doc_to_product(doc) if doc else None

    async def get_latest_product(self, *, owner_user_id: str) -> Optional[ProductInDB]:
        await self.ensure_indexes()
        doc = await self._col.find_one(
            {"owner_user_id": owner_user_id, "is_deleted": False},
            sort=[("created_at", -1)],
        )
        return _doc_to_product(doc) if doc else None

    async def update_product(
        self,
        *,
        owner_user_id: str,
        product_id: str,
        name: Optional[str],
        description: Optional[str],
        name_set: bool,
        description_set: bool,
    ) -> Optional[ProductInDB]:
        await self.ensure_indexes()
        try:
            oid = ObjectId(product_id)
        except Exception:
            return None
        patch: Dict[str, object] = {"updated_at": utcnow()}
        if name_set:
            patch["name"] = name
        if description_set:
            patch["description"] = description
        doc = await self._col.find_one_and_update(
            {"_id": oid, "owner_user_id": owner_user_id, "is_deleted": False},
            {"$set": patch},
            return_document=ReturnDocument.AFTER,
        )
        return _doc_to_product(doc) if doc else None

    async def soft_delete_product(self, *, owner_user_id: str, product_id: str) -> bool:
        await self.ensure_indexes()
        try:
            oid = ObjectId(product_id)
        except Exception:
            return False
        result = await self._col.update_one(
            {"_id": oid, "owner_user_id": owner_user_id, "is_deleted": False},
            {"$set": {"is_deleted": True, "deleted_at": utcnow(), "updated_at": utcnow()}},
        )
        return result.modified_count > 0


class InMemoryProductRepository:
    def __init__(self):
        self._products_by_id: Dict[str, ProductInDB] = {}
        self._next = 1

    async def ensure_indexes(self) -> None:
        return

    async def create_product(self, *, owner_user_id: str, name: str, description: Optional[str]) -> ProductInDB:
        product_id = str(self._next)
        self._next += 1
        now = utcnow()
        product = ProductInDB(
            product_id=product_id,
            owner_user_id=owner_user_id,
            name=name,
            description=description,
            created_at=now,
            updated_at=now,
            is_deleted=False,
            deleted_at=None,
        )
        self._products_by_id[product_id] = product
        return product

    async def list_products(
        self,
        *,
        owner_user_id: str,
        page: int,
        page_size: int,
        name: Optional[str] = None,
        created_from: Optional[str] = None,
        created_to: Optional[str] = None,
        include_deleted: bool = False,
    ) -> Tuple[List[ProductInDB], int]:
        from_dt = parse_date(created_from or "")
        to_dt = parse_date(created_to or "")
        items = [product for product in self._products_by_id.values() if product.owner_user_id == owner_user_id]
        if not include_deleted:
            items = [product for product in items if not product.is_deleted]
        if name:
            needle = name.lower()
            items = [product for product in items if needle in product.name.lower()]
        if from_dt:
            items = [product for product in items if product.created_at >= from_dt]
        if to_dt:
            items = [product for product in items if product.created_at <= to_dt]
        items.sort(key=lambda product: product.created_at, reverse=True)
        total = len(items)
        start = max(0, (page - 1) * page_size)
        end = start + page_size
        return items[start:end], total

    async def get_product(
        self,
        *,
        owner_user_id: str,
        product_id: str,
        include_deleted: bool = False,
    ) -> Optional[ProductInDB]:
        product = self._products_by_id.get(product_id)
        if not product or product.owner_user_id != owner_user_id:
            return None
        if product.is_deleted and not include_deleted:
            return None
        return product

    async def get_latest_product(self, *, owner_user_id: str) -> Optional[ProductInDB]:
        items, _ = await self.list_products(owner_user_id=owner_user_id, page=1, page_size=1)
        return items[0] if items else None

    async def update_product(
        self,
        *,
        owner_user_id: str,
        product_id: str,
        name: Optional[str],
        description: Optional[str],
        name_set: bool,
        description_set: bool,
    ) -> Optional[ProductInDB]:
        existing = await self.get_product(owner_user_id=owner_user_id, product_id=product_id)
        if not existing:
            return None
        updated = ProductInDB(
            product_id=existing.product_id,
            owner_user_id=existing.owner_user_id,
            name=name if name_set else existing.name,
            description=description if description_set else existing.description,
            created_at=existing.created_at,
            updated_at=utcnow(),
            is_deleted=False,
            deleted_at=None,
        )
        self._products_by_id[product_id] = updated
        return updated

    async def soft_delete_product(self, *, owner_user_id: str, product_id: str) -> bool:
        existing = await self.get_product(owner_user_id=owner_user_id, product_id=product_id)
        if not existing:
            return False
        now = utcnow()
        deleted = ProductInDB(
            product_id=existing.product_id,
            owner_user_id=existing.owner_user_id,
            name=existing.name,
            description=existing.description,
            created_at=existing.created_at,
            updated_at=now,
            is_deleted=True,
            deleted_at=now,
        )
        self._products_by_id[product_id] = deleted
        return True
