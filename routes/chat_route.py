from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from starlette.responses import JSONResponse
from agents.chat_agent import chat_agent
import uuid

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


@router.post("", tags=["chat"])
async def chat_endpoint(request: ChatRequest):
    try:
        thread_id = str(uuid.uuid4())
        products = await chat_agent(thread_id=thread_id, message=request.message)
        return JSONResponse(content={"products": products})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{thread_id}", tags=["chat"])
async def chat_with_thread_id(thread_id: str):
    return JSONResponse(
        content={
            "message": "Chat endpoint with thread_id is working",
            "thread_id": thread_id,
        }
    )