from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional


class Database:
    client: Optional[AsyncIOMotorClient] = None
    database_name: str = "tryLuxor"

    @classmethod
    async def connect(cls, mongo_uri: str):
        if cls.client is None:
            cls.client = AsyncIOMotorClient(mongo_uri)
            print(f"Connected to MongoDB at {mongo_uri}")

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
