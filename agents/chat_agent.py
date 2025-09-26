from typing import Optional, Annotated, TypedDict, Sequence
import json
from libs.database import Database
from langchain_core.messages import (
    BaseMessage,
    SystemMessage,
    HumanMessage,
)
from langchain_core.tools import tool
from langchain_google_genai import GoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from pydantic import SecretStr
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")


embeddings = GoogleGenerativeAIEmbeddings(
    model="text-embedding-004", google_api_key=SecretStr(api_key) if api_key else None
)

@tool
async def products_look_up(query: str, n: int = 10) -> list:
    """
    Looks up products in the database based on a query.

    Args:
        query (str): The query to search for.
        n (int, optional): The number of products to return. Defaults to 10.

    Returns:
        list: A list of products that match the query.
    """
    try:
        collection = Database.get_collection("products")
        total_count = await collection.count_documents({})

        if total_count == 0:
            return []

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
            for product in result:
                product["_id"] = str(product["_id"])
            return result

        result = await collection.find(
            {
                "$or": [
                    {"name": {"$regex": query, "options": "i"}},
                    {"description": {"$regex": query, "options": "i"}},
                    {"categories": {"$regex": query, "options": "i"}},
                    {"embedding_text": {"$regex": query, "options": "i"}},
                ]
            }
        ).to_list(length=n)

        if len(result) > 0:
            print("return by normal regex search")
            for product in result:
                product["_id"] = str(product["_id"])
            return result

        return []

    except Exception as e:
        print(f"Error processing chat message: {e}")
        raise e


async def chat_agent(thread_id: Optional[str] = None, message: Optional[str] = None):
    if thread_id is None or message is None:
        raise ValueError("Thread ID and message are required")
    try:
        llm = GoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=api_key)
        model_with_tools = llm.bind(tools=[products_look_up])

        system_message = SystemMessage(
            content="You are a helpful assistant that helps users find products in the database."
        )
        human_message = HumanMessage(content=message)
        messages = [system_message, human_message]

        ai_response = await model_with_tools.ainvoke(messages)

        if hasattr(ai_response, 'tool_calls') and ai_response.tool_calls:
            products = []
            for tool_call in ai_response.tool_calls:
                if tool_call["name"] == "products_look_up":
                    result = await products_look_up.ainvoke(tool_call["args"])
                    if isinstance(result, list):
                        products.extend(result)
            return products
        else:
            # This is for debugging to see what's coming back
            return [{"error": "No tool calls found or unexpected response", "response_type": str(type(ai_response)), "content": str(ai_response)}]

    except Exception as e:
        print(f"Error processing chat message: {e}")
        raise e