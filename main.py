import uvicorn
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException
from starlette.responses import JSONResponse

from routes import chat
from libs.database import Database
from libs.logger import get_logger
from routes.product import router as product_router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Connecting to database...")
    await Database.connect()
    logger.info("Database connected.")
    yield
    logger.info("Disconnecting from database...")
    await Database.disconnect()
    logger.info("Database disconnected.")


app = FastAPI(debug=True, lifespan=lifespan)


@app.get("/")
async def read_root():
    logger.info("Root endpoint accessed.")
    return JSONResponse(content={"message": "Server is running"})


@app.get("/seed-database")
async def seed_db():
    try:
        from seeds.seed_database import seed_database

        await seed_database()
        logger.info("Database seeded successfully.")
        return JSONResponse(content={"message": "Database seeded successfully"})
    except Exception as e:
        logger.error(f"Error seeding database: {e}", exc_info=True)
        return HTTPException(status_code=500, detail=str(e))


app.include_router(chat.router, prefix="/chat", tags=["chat"])
app.include_router(product_router, prefix="/products", tags=["products"])
