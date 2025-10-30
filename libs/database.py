# db.py
import asyncio
from typing import Optional, ClassVar

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database as SyncDatabase

from pydantic_settings import BaseSettings, SettingsConfigDict
from libs.logger import get_logger


# ──────────────────────────────────────────────
# Configuration using Pydantic Settings
# ──────────────────────────────────────────────
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongo_uri: str = "mongodb://localhost:27017"
    database_name: str = "tryLuxor"


settings = Settings()
logger = get_logger(__name__)


# ──────────────────────────────────────────────
# Custom Exceptions
# ──────────────────────────────────────────────
class DatabaseConnectionError(Exception):
    """Raised when database connection fails or is not initialized."""


# ──────────────────────────────────────────────
# Database Class
# ──────────────────────────────────────────────
class Database:
    """
    Singleton-style database connector supporting both async and sync clients.
    """

    _async_client: ClassVar[Optional[AsyncIOMotorClient]] = None
    _sync_client: ClassVar[Optional[MongoClient]] = None
    _async_db: ClassVar[Optional[AsyncIOMotorDatabase]] = None
    _sync_db: ClassVar[Optional[SyncDatabase]] = None
    _lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    @classmethod
    async def connect(cls) -> None:
        """
        Establish async & sync MongoDB connections.
        Safe to call multiple times — connection will be created only once.
        """
        async with cls._lock:
            if cls._async_client and cls._sync_client:
                return  # already connected

            try:
                cls._async_client = AsyncIOMotorClient(settings.mongo_uri)
                cls._sync_client = MongoClient(settings.mongo_uri)

                # Test connections
                await cls._async_client.admin.command("ping")
                cls._sync_client.admin.command("ping")

                # Cache DB references
                cls._async_db = cls._async_client[settings.database_name]
                cls._sync_db = cls._sync_client[settings.database_name]

                logger.info(
                    f"Connected to MongoDB → {settings.mongo_uri}/{settings.database_name}"
                )
            except Exception as e:
                logger.exception("Failed to connect to MongoDB.")
                # Reset on failure to avoid stale references
                cls._async_client = None
                cls._sync_client = None
                cls._async_db = None
                cls._sync_db = None
                raise DatabaseConnectionError(str(e)) from e

    @classmethod
    async def disconnect(cls) -> None:
        """Close both async and sync MongoDB connections."""
        if cls._async_client:
            cls._async_client.close()
            cls._async_client = None
            cls._async_db = None

        if cls._sync_client:
            cls._sync_client.close()
            cls._sync_client = None
            cls._sync_db = None

        logger.info("Disconnected from MongoDB.")

    # ──────────────────────────────────────────
    # Async Accessors
    # ──────────────────────────────────────────
    @classmethod
    async def get_async_database(cls) -> AsyncIOMotorDatabase:
        """
        Return the async database object, auto-connecting if needed.
        """
        if cls._async_db is None:
            await cls.connect()
        if cls._async_db is None:
            raise DatabaseConnectionError("Async database client not connected.")
        return cls._async_db

    @classmethod
    async def get_async_collection(cls, name: str):
        """
        Get an async collection from the database.
        """
        db = await cls.get_async_database()
        return db[name]

    # ──────────────────────────────────────────
    # Sync Accessors
    # ──────────────────────────────────────────
    @classmethod
    def get_sync_database(cls) -> SyncDatabase:
        """
        Return the sync database object.
        Raises DatabaseConnectionError if not connected.
        """
        if cls._sync_db is None:
            raise DatabaseConnectionError("Synchronous database client not connected.")
        return cls._sync_db

    @classmethod
    def get_sync_collection(cls, name: str) -> Collection:
        """
        Get a sync collection from the database.
        """
        return cls.get_sync_database()[name]
