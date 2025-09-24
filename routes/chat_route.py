from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from starlette.responses import JSONResponse

router = APIRouter()


@router.post("", tags=["chat"])
async def chat_endpoint():
    return JSONResponse(content={"message": "Chat endpoint is working"})


@router.post("/{thread_id}", tags=["chat"])
async def chat_with_thread_id(thread_id: str):
    return JSONResponse(
        content={
            "message": "Chat endpoint with thread_id is working",
            "thread_id": thread_id,
        }
    )
