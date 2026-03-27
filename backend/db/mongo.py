from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from backend.config.settings import settings
from backend.utils.logger import get_logger

logger = get_logger("mongo")

_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None


def _db_name_from_uri(uri: str) -> str:
    parsed = urlparse(uri)
    path = (parsed.path or "").lstrip("/")
    return path or "revops_ai"


def get_database() -> AsyncIOMotorDatabase:
    global _client, _db
    if _db is not None:
        return _db

    uri = str(settings.mongodb_uri)
    _client = AsyncIOMotorClient(uri)
    _db = _client[_db_name_from_uri(uri)]
    logger.info("mongo_connected", database=_db.name)
    return _db

