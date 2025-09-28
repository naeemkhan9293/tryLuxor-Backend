from __future__ import annotations
import sys
import os

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from langgraph.graph import StateGraph, START, END, message
from langgraph.types import Command
from typing import TypedDict, Literal, Sequence, Annotated, Optional
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool
from langchain.agents import ToolNode
from langchain_mongodb import MongoDBAtlasVectorSearch
from libs.database import Database
from langchain_google_genai import GoogleGenerativeAIEmbeddings, GoogleGenerativeAI
from dotenv import load_dotenv
from pydantic import SecretStr
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from datetime import datetime
from langchain_core.documents import Document
from libs.logger import get_logger


load_dotenv()
GEMINI_API_KEY = SecretStr(str(os.getenv("GOOGLE_API_KEY")))
logger = get_logger(__name__)
embeddings = GoogleGenerativeAIEmbeddings(
    model="text-embedding-004", google_api_key=GEMINI_API_KEY
)
llm = GoogleGenerativeAI(
    model="gemini-2.5-flash", temperature=0.7, google_api_key=GEMINI_API_KEY
)


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], message.add_messages]
    query: str | None
    llm_response: Optional[str]
    product_info: Optional[list[tuple[Document, float]] | dict | str]


@tool("product_lookup", description="Look up products based on user query")
def product_lookup(state: AgentState):
    logger.info("product_lookup: Looking up products")
    """Search products in MongoDB by vector or regex."""
    try:
        query = state.get("query")
        if query is None:
            state["product_info"] = "No Product found"
            return state
        collection = Database.get_sync_collection("products")
        vector_store = MongoDBAtlasVectorSearch(
            collection=collection,
            embedding=GoogleGenerativeAIEmbeddings(
                model="models/text-embedding-004", google_api_key=GEMINI_API_KEY
            ),
            index_name="vector_index",
            relevance_score_fn="cosine",
        )

        result = vector_store.similarity_search_with_score(query=query)

        if len(result) > 0:
            state["product_info"] = result
            return state

        result = collection.find(
            {
                "$or": [
                    {"name": {"$regex": query, "$options": "i"}},
                    {"description": {"$regex": query, "$options": "i"}},
                ]
            }
        ).to_list()

        if len(result) > 0:
            state["product_info"] = result
            return state

        state["product_info"] = (
            "No products found. Please try again with a different query."
        )
        return state

    except Exception as e:
        logger.error(f"product_lookup: An error occurred during product lookup: {e}")
        return state


tool_node = ToolNode(tools=[product_lookup])
llm_with_tools = llm.bind_tools([product_lookup])


def call_llm(state: AgentState) -> AgentState:
    logger.info("call_llm: Calling LLM")
    """Call LLM to generate response based on the current state"""
    try:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prompt = ChatPromptTemplate(
            [
                SystemMessage(
                    content="""System message defines the AI's role and behavior
                    `You are a helpful E-commerce Chatbot Agent for a furniture store.
                    IMPORTANT: You have access to an item_lookup tool that searches the furniture inventory database. ALWAYS use this tool when customers ask about furniture items, even if the tool returns errors or empty results.

                        When using the item_lookup tool:
                        - If it returns results, provide helpful details about the furniture items
                        - If it returns an error or no results, acknowledge this and offer to help in other ways
                        - If the database appears to be empty, let the customer know that inventory might be being updated

                    Current time: {time}`"""
                ),
                MessagesPlaceholder("messages"),
            ]
        )

        llm_response = llm.invoke(
            prompt.format_messages(messages=state.get("messages"), time=current_time)
        )

        return state
    except Exception as e:
        logger.error(f"call_llm: An error occurred during LLM invocation: {e}")
        return state


builder = StateGraph(AgentState)

builder.add_node(call_llm)
builder.add_node("product_lookup", tool_node)

builder.add_edge(START, "call_llm")
builder.add_edge("product_lookup", "call_llm")
builder.add_edge("call_llm", END)

graph = builder.compile()


mock_messages = [HumanMessage(content="Do you have sofa")]

initial_state: AgentState = {
    "messages": mock_messages,
    "query": None,
    "llm_response": None,
    "product_info": None,
}
final_state = graph.invoke(initial_state, config={"recursion_limit": 5})
print("Final state:", final_state)
