from typing import Optional, Annotated, TypedDict, Sequence
from libs.database import Database
from langgraph.graph import StateGraph, message
from langchain_core.messages import (
    BaseMessage,
    SystemMessage,
    HumanMessage,
    ToolMessage,
)
from langchain_core.tools import tool
from langchain_google_genai import GoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from pydantic import SecretStr
from starlette.responses import JSONResponse
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")


embeddings = GoogleGenerativeAIEmbeddings(
    model="text-embedding-004", google_api_key=SecretStr(api_key) if api_key else None
)


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], message.add_messages]


# @tool
async def products_look_up(query, n=10):
    try:
        collection = Database.get_collection("products")
        total_count = await collection.count_documents({})

        if total_count == 0:
            return "No products found"

        vector_query = embeddings.embed_query(query)

        pipeline = [
            {
                "$vectorSearch": {
                    "index": "vector_index",
                    "path": "embedding",
                    "queryVector": vector_query,
                    "numCandidates": total_count,
                    "limit": n,
                }
            }
        ]

        result = await collection.aggregate(pipeline).to_list(length=n)
        if len(result) > 0:
            print("return by vector search")
            return result

        result = await collection.find(
            {
                "$or": [
                    {"name": {"$regex": query, "$option": "i"}},
                    {"description": {"$regex": query, "$options": "i"}},
                    {"categories": {"$regex": query, "$options": "i"}},
                    {"embedding_text": {"$regex": query, "$options": "i"}},
                ]
            }
        ).to_list(length=n)

        if len(result) > 0:
            print("return by normal regex search")
            return result

        return "No products found"

    except Exception as e:
        print(f"Error processing chat message: {e}")
        raise e


async def chat_agent(thread_id: Optional[str] = None, message: Optional[str] = None):
    if thread_id is None or message is None:
        raise ValueError("Thread ID and message are required")
    try:
        products = await products_look_up(message)
        if isinstance(products, str):
            return [] # Return an empty list if no products are found
        for product in products:
            product["_id"] = str(product["_id"])
        return products
    except Exception as e:
        print(f"Error processing chat message: {e}")
        raise e
