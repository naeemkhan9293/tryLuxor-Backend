from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
from typing import Optional
from libs.logger import get_logger
from dotenv import load_dotenv
import os

load_dotenv()
logger = get_logger(__name__)

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")


class Database:
    client: Optional[AsyncIOMotorClient] = None
    database_name: str = "tryLuxor"

    @classmethod
    async def connect(cls):
        if cls.client is None:
            try:
                cls.client = AsyncIOMotorClient(MONGO_URI)
                await cls.client.admin.command("ping")  # Test connection
                logger.info("Successfully connected to MongoDB.")
            except Exception as e:
                logger.error(f"Failed to connect to MongoDB: {e}")
                cls.client = None
                raise e

    @classmethod
    async def disconnect(cls):
        if cls.client:
            cls.client.close()
            cls.client = None
            print("Disconnected from MongoDB.")

    @classmethod
    def get_database(cls):
        if cls.client is None:
            raise Exception("Database client not initialized. Call connect() first.")
        return cls.client[cls.database_name]

    @classmethod
    def get_collection(cls, collection_name: str):
        db = cls.get_database()
        return db[collection_name]

    @classmethod
    def get_sync_collection(cls, collection_name: str):
        # Ensure a synchronous client is used for synchronous operations
        sync_client = MongoClient(MONGO_URI)
        db = sync_client[cls.database_name]
        return db[collection_name]
