from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional, Protocol

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class UserInDB:
    user_id: str
    username: str
    password_hash: str
    created_at: datetime


class UserRepository(Protocol):
    async def ensure_indexes(self) -> None: ...
    async def create_user(self, *, username: str, password_hash: str) -> UserInDB: ...
    async def get_by_username(self, username: str) -> Optional[UserInDB]: ...
    async def get_by_id(self, user_id: str) -> Optional[UserInDB]: ...


class MongoUserRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._col = db["users"]
        self._indexes_ready = False

    async def ensure_indexes(self) -> None:
        if self._indexes_ready:
            return
        await self._col.create_index("username", unique=True)
        self._indexes_ready = True

    async def create_user(self, *, username: str, password_hash: str) -> UserInDB:
        await self.ensure_indexes()
        created_at = _utcnow()
        doc = {
            "username": username,
            "password_hash": password_hash,
            "created_at": created_at,
        }
        res = await self._col.insert_one(doc)
        return UserInDB(
            user_id=str(res.inserted_id),
            username=username,
            password_hash=password_hash,
            created_at=created_at,
        )

    async def get_by_username(self, username: str) -> Optional[UserInDB]:
        await self.ensure_indexes()
        doc = await self._col.find_one({"username": username})
        if not doc:
            return None
        return UserInDB(
            user_id=str(doc["_id"]),
            username=str(doc.get("username", "")),
            password_hash=str(doc.get("password_hash", "")),
            created_at=doc.get("created_at") or _utcnow(),
        )

    async def get_by_id(self, user_id: str) -> Optional[UserInDB]:
        await self.ensure_indexes()
        try:
            oid = ObjectId(user_id)
        except Exception:
            return None
        doc = await self._col.find_one({"_id": oid})
        if not doc:
            return None
        return UserInDB(
            user_id=str(doc["_id"]),
            username=str(doc.get("username", "")),
            password_hash=str(doc.get("password_hash", "")),
            created_at=doc.get("created_at") or _utcnow(),
        )


class InMemoryUserRepository:
    def __init__(self):
        self._users_by_id: Dict[str, UserInDB] = {}
        self._users_by_username: Dict[str, UserInDB] = {}
        self._next = 1

    async def ensure_indexes(self) -> None:
        return

    async def create_user(self, *, username: str, password_hash: str) -> UserInDB:
        if username in self._users_by_username:
            raise ValueError("Username already exists")
        user_id = str(self._next)
        self._next += 1
        user = UserInDB(
            user_id=user_id,
            username=username,
            password_hash=password_hash,
            created_at=_utcnow(),
        )
        self._users_by_id[user_id] = user
        self._users_by_username[username] = user
        return user

    async def get_by_username(self, username: str) -> Optional[UserInDB]:
        return self._users_by_username.get(username)

    async def get_by_id(self, user_id: str) -> Optional[UserInDB]:
        return self._users_by_id.get(user_id)

