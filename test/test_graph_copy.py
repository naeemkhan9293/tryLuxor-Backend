from __future__ import annotations
import sys
import os

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from langgraph.graph import StateGraph, START, END, message

import re
from typing import TypedDict, Literal, Sequence, Annotated, Optional
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
    ToolMessage,
)
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


def product_lookup(state: AgentState):
    logger.info("product_lookup: Looking up products")
    """Search products in MongoDB by vector or regex."""
    try:
        # query = state.get("query")
        query = "sofa"
        if query is None:
            state["product_info"] = "No Product found"
            return {
                "messages": [
                    ToolMessage(
                        content="No Product found", tool_call_id="product_lookup_call"
                    )
                ],
                "product_info": "No Product found",
            }
        collection = Database.get_sync_collection("products")
        vector_store = MongoDBAtlasVectorSearch(
            collection=collection,
            embedding=GoogleGenerativeAIEmbeddings(
                model="text-embedding-004", google_api_key=GEMINI_API_KEY
            ),
            index_name="vector_index",
            relevance_score_fn="cosine",
        )

        result = vector_store.similarity_search_with_score(query=query)

        # Process vector search results: reconstruct Document objects without embeddings
        processed_vector_results = []
        for doc, score in result:
            doc_metadata = (
                doc.metadata.copy()
            )  # Create a copy to avoid modifying original metadata
            if "embedding" in doc_metadata:
                del doc_metadata["embedding"]
            new_doc = Document(page_content=doc.page_content, metadata=doc_metadata)
            processed_vector_results.append((new_doc, score))

        if len(processed_vector_results) > 0:
            state["product_info"] = processed_vector_results
            return {
                "messages": [
                    ToolMessage(
                        content=str(processed_vector_results),
                        tool_call_id="product_lookup_call",
                    )
                ],
                "product_info": processed_vector_results,
            }

        result = collection.find(
            {
                "$or": [
                    {"name": {"$regex": query, "$options": "i"}},
                    {"description": {"$regex": query, "$options": "i"}},
                ]
            }
        ).to_list()

        # Process regex search results: remove embeddings from each dictionary
        processed_regex_results = []
        for doc_dict in result:
            if "embedding" in doc_dict:
                doc_dict_copy = (
                    doc_dict.copy()
                )  # Create a copy to avoid modifying original
                del doc_dict_copy["embedding"]
                processed_regex_results.append(doc_dict_copy)
            else:
                processed_regex_results.append(doc_dict)

        if len(processed_regex_results) > 0:
            state["product_info"] = processed_regex_results
            return {
                "messages": [
                    ToolMessage(
                        content=str(processed_regex_results),
                        tool_call_id="product_lookup_call",
                    )
                ],
                "product_info": processed_regex_results,
            }

        state["product_info"] = (
            "No products found. Please try again with a different query."
        )
        return {
            "messages": [
                ToolMessage(
                    content=state["product_info"], tool_call_id="product_lookup_call"
                )
            ],
            "product_info": state["product_info"],
        }

    except Exception as e:
        logger.error(f"product_lookup: An error occurred during product lookup: {e}")
        error_message = f"Error: {e}"
        return {
            "messages": [
                ToolMessage(content=error_message, tool_call_id="product_lookup_call")
            ],
            "product_info": error_message,
        }


def call_llm(state: AgentState) -> AgentState:
    logger.info("call_llm: Calling LLM")
    """Call LLM to generate response based on the current state"""
    try:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prompt = ChatPromptTemplate(
            [
                SystemMessage(
                    content="""
                    `You are a helpful E-commerce Chatbot Agent for a furniture store.
                    IMPORTANT: You have access to a tool called `product_lookup`. When a customer asks about furniture items, you MUST use this tool.

                    To use the `product_lookup` tool, your response MUST be in the format:
                    TOOL_CALL: product_lookup(query="<customer_query_here>")

                    For example, if the user asks "Do you have chairs?", you should respond with:
                    TOOL_CALL: product_lookup(query="chairs")

                    If the tool returns results, provide helpful details about the furniture items.
                    If it returns an error or no results, acknowledge this and offer to help in other ways.
                    If the database appears to be empty, let the customer know that inventory might be being updated.

                    Current time: {time}`"""
                ),
                MessagesPlaceholder("messages"),
                MessagesPlaceholder("agent_scratchpad"),
            ]
        )

        llm_response: str = llm.invoke(
            prompt.format_messages(
                messages=state.get("messages"),
                time=current_time,
                agent_scratchpad=(
                    state.get("messages")[-1:] if state.get("messages") else []
                ),
            )
        )
        # print(llm_response)
        return {
            "messages": [
                AIMessage(content=llm_response)
            ],  # Only return the new message
            "llm_response": llm_response,
            "query": state.get("query"),
            "product_info": state.get("product_info"),
        }
    except Exception as e:
        logger.error(f"call_llm: An error occurred during LLM invocation: {e}")
        return state


def should_continue(
    state: AgentState,
) -> Literal["product_lookup", "call_llm", "__end__"]:
    logger.info("should_continue: Checking if LLM wants to call a tool")
    messages = state["messages"]
    last_message = messages[-1]
    logger.debug(f"should_continue: Last message: {last_message}")
    if isinstance(last_message, AIMessage):
        llm_response_content = str(last_message.content)  # Convert to string
        tool_call_pattern = r"TOOL_CALL: product_lookup\(query=\"(.*?)\"\)"
        match = re.search(tool_call_pattern, llm_response_content)
        if match:
            query = match.group(1)
            state["query"] = query
            return "product_lookup"
        else:
            return "__end__"  # LLM responded without a tool call, so end.
    elif isinstance(last_message, ToolMessage):
        return "call_llm"  # Tool just ran, call LLM to summarize/respond

    return "__end__"  # Default to end if unexpected message type


builder = StateGraph(AgentState)

builder.add_node("call_llm", call_llm)
builder.add_node(
    "product_lookup", product_lookup
)  # Directly add the function as a node

builder.add_edge(START, "call_llm")
builder.add_conditional_edges(
    "call_llm",
    should_continue,
    {"product_lookup": "product_lookup", "call_llm": "call_llm", "__end__": END},
)
builder.add_edge("product_lookup", "call_llm")

graph = builder.compile()


mock_messages = [HumanMessage(content="do you have any kind of sofa")]

initial_state: AgentState = {
    "messages": mock_messages,
    "query": None,
    "llm_response": None,
    "product_info": None,
}
final_state = graph.invoke(initial_state, config={"recursion_limit": 5})

for message in final_state["messages"]:
    print(message)
