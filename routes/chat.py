from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from starlette.responses import JSONResponse
from agents.chat_agent import chat_agent
import uuid

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


@router.post("", tags=["chat"])
async def chat_endpoint(chat: ChatRequest):
    try:
        thread_id = str(uuid.uuid4())
        result = await chat_agent(thread_id=thread_id, message=chat.message)
        return JSONResponse(content={"message": result, "thread_id": thread_id})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{thread_id}", tags=["chat"])
async def chat_with_thread_id(thread_id: str, chat: ChatRequest):
    try:
        result = await chat_agent(thread_id=thread_id, message=chat.message)
        return JSONResponse(
            content={
                "message": result,
                "thread_id": thread_id,
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str("Internal Server Error"))
