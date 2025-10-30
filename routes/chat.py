from pydantic import BaseModel
from fastapi import APIRouter, HTTPException
from starlette.responses import JSONResponse
from agents.chat_agent import chat_agent
import uuid
from libs.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


class ChatRequest(BaseModel):
    message: str


@router.post("", tags=["chat"])
async def chat_endpoint(chat: ChatRequest):
    try:
        thread_id = str(uuid.uuid4())
        result = await chat_agent(thread_id=thread_id, message=chat.message)
        return JSONResponse(content={"message": result, "thread_id": thread_id})
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail=str("Internal Server Error"))


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
        logger.error(e)
        raise HTTPException(status_code=500, detail=str("Internal Server Error"))
