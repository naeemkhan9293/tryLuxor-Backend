import uvicorn
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException
from starlette.responses import JSONResponse
from routes import chat_route
from libs.database import Database
import os
from dotenv import load_dotenv

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    await Database.connect(MONGO_URI)
    yield
    await Database.disconnect()


app = FastAPI(debug=True, lifespan=lifespan)


@app.get("/")
async def read_root():
    return JSONResponse(content={"message": "Server is running"})


@app.get("/seed-database")
async def seed_db():
    try:
        from seeds.seed_database import seed_database

        await seed_database()
        return JSONResponse(content={"message": "Database seeded successfully"})
    except Exception as e:
        return HTTPException(status_code=500, detail=str(e))


app.include_router(chat_route.router, prefix="/chat", tags=["chat"])
