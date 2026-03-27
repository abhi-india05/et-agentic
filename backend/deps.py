from __future__ import annotations

from functools import lru_cache

from backend.db.mongo import get_database
from backend.repositories.products import MongoProductRepository, ProductRepository
from backend.repositories.users import MongoUserRepository, UserRepository


@lru_cache(maxsize=1)
def get_user_repo() -> UserRepository:
    return MongoUserRepository(get_database())


@lru_cache(maxsize=1)
def get_product_repo() -> ProductRepository:
    return MongoProductRepository(get_database())

