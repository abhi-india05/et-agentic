from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Protocol

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class ProductInDB:
    product_id: str
    owner_user_id: str
    name: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime


class ProductRepository(Protocol):
    async def ensure_indexes(self) -> None: ...
    async def create_product(
        self, *, owner_user_id: str, name: str, description: Optional[str]
    ) -> ProductInDB: ...
    async def list_products(self, *, owner_user_id: str, limit: int = 50) -> List[ProductInDB]: ...
    async def get_product(self, *, owner_user_id: str, product_id: str) -> Optional[ProductInDB]: ...
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


class MongoProductRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._col = db["products"]
        self._indexes_ready = False

    async def ensure_indexes(self) -> None:
        if self._indexes_ready:
            return
        await self._col.create_index([("owner_user_id", 1), ("updated_at", -1)])
        self._indexes_ready = True

    async def create_product(
        self, *, owner_user_id: str, name: str, description: Optional[str]
    ) -> ProductInDB:
        await self.ensure_indexes()
        now = _utcnow()
        doc = {
            "owner_user_id": owner_user_id,
            "name": name,
            "description": description,
            "created_at": now,
            "updated_at": now,
        }
        res = await self._col.insert_one(doc)
        return ProductInDB(
            product_id=str(res.inserted_id),
            owner_user_id=owner_user_id,
            name=name,
            description=description,
            created_at=now,
            updated_at=now,
        )

    async def list_products(self, *, owner_user_id: str, limit: int = 50) -> List[ProductInDB]:
        await self.ensure_indexes()
        cursor = (
            self._col.find({"owner_user_id": owner_user_id})
            .sort("updated_at", -1)
            .limit(max(1, min(int(limit), 200)))
        )
        out: List[ProductInDB] = []
        async for doc in cursor:
            out.append(
                ProductInDB(
                    product_id=str(doc["_id"]),
                    owner_user_id=str(doc.get("owner_user_id", "")),
                    name=str(doc.get("name", "")),
                    description=doc.get("description"),
                    created_at=doc.get("created_at") or _utcnow(),
                    updated_at=doc.get("updated_at") or _utcnow(),
                )
            )
        return out

    async def get_product(self, *, owner_user_id: str, product_id: str) -> Optional[ProductInDB]:
        await self.ensure_indexes()
        try:
            oid = ObjectId(product_id)
        except Exception:
            return None
        doc = await self._col.find_one({"_id": oid, "owner_user_id": owner_user_id})
        if not doc:
            return None
        return ProductInDB(
            product_id=str(doc["_id"]),
            owner_user_id=str(doc.get("owner_user_id", "")),
            name=str(doc.get("name", "")),
            description=doc.get("description"),
            created_at=doc.get("created_at") or _utcnow(),
            updated_at=doc.get("updated_at") or _utcnow(),
        )

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
        patch: Dict[str, object] = {"updated_at": _utcnow()}
        if name_set:
            patch["name"] = name
        if description_set:
            patch["description"] = description
        doc = await self._col.find_one_and_update(
            {"_id": oid, "owner_user_id": owner_user_id},
            {"$set": patch},
            return_document=ReturnDocument.AFTER,
        )
        if not doc:
            return None
        return ProductInDB(
            product_id=str(doc["_id"]),
            owner_user_id=str(doc.get("owner_user_id", "")),
            name=str(doc.get("name", "")),
            description=doc.get("description"),
            created_at=doc.get("created_at") or _utcnow(),
            updated_at=doc.get("updated_at") or _utcnow(),
        )


class InMemoryProductRepository:
    def __init__(self):
        self._products_by_id: Dict[str, ProductInDB] = {}
        self._next = 1

    async def ensure_indexes(self) -> None:
        return

    async def create_product(
        self, *, owner_user_id: str, name: str, description: Optional[str]
    ) -> ProductInDB:
        product_id = str(self._next)
        self._next += 1
        now = _utcnow()
        product = ProductInDB(
            product_id=product_id,
            owner_user_id=owner_user_id,
            name=name,
            description=description,
            created_at=now,
            updated_at=now,
        )
        self._products_by_id[product_id] = product
        return product

    async def list_products(self, *, owner_user_id: str, limit: int = 50) -> List[ProductInDB]:
        items = [p for p in self._products_by_id.values() if p.owner_user_id == owner_user_id]
        items.sort(key=lambda p: p.updated_at, reverse=True)
        return items[: max(1, min(int(limit), 200))]

    async def get_product(self, *, owner_user_id: str, product_id: str) -> Optional[ProductInDB]:
        p = self._products_by_id.get(product_id)
        if not p or p.owner_user_id != owner_user_id:
            return None
        return p

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
        now = _utcnow()
        updated = ProductInDB(
            product_id=existing.product_id,
            owner_user_id=existing.owner_user_id,
            name=name if name_set else existing.name,
            description=description if description_set else existing.description,
            created_at=existing.created_at,
            updated_at=now,
        )
        self._products_by_id[product_id] = updated
        return updated
