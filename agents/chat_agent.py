from typing import Optional, Annotated, TypedDict, Sequence
from datetime import datetime
from langgraph.graph import StateGraph, message, END, START
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool as lc_tool
from langchain_google_genai import GoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from pydantic import SecretStr
import os
from dotenv import load_dotenv
from libs.database import Database  # your existing DB wrapper
from libs.logger import get_logger

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

logger = get_logger(__name__)

embeddings = GoogleGenerativeAIEmbeddings(
    model="text-embedding-004",
    google_api_key=SecretStr(api_key) if api_key else None,
)

llm = GoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.7,
    google_api_key=SecretStr(api_key) if api_key else None,
)


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], message.add_messages]


# ---------- tool ----------
@lc_tool
async def products_look_up(query: str, n: int = 10):
    """Search products in MongoDB by vector or regex."""
    try:
        collection = Database.get_collection("products")
        total_count = await collection.count_documents({})
        if total_count == 0:
            logger.info("products_look_up: No products found in collection.")
            return "No products found"

        try:
            vector_query = await embeddings.aembed_query(query)
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
            docs = await collection.aggregate(pipeline).to_list(length=n)
            if docs:
                logger.info(
                    f"products_look_up: Found {len(docs)} products via vector search."
                )
                return docs
        except Exception as e:
            logger.warning(
                f"products_look_up: Vector search failed for query '{query}': {e}"
            )

        docs = await collection.find(
            {
                "$or": [
                    {"name": {"$regex": query, "$options": "i"}},
                    {"description": {"$regex": query, "$options": "i"}},
                ]
            }
        ).to_list(length=n)
        if docs:
            logger.info(
                f"products_look_up: Found {len(docs)} products via regex search."
            )
            return docs
        else:
            logger.info(
                f"products_look_up: No products found for query '{query}' via regex search."
            )
            return "No products found"
    except Exception as e:
        logger.error(f"products_look_up: An unexpected error occurred: {e}")
        return "An error occurred while looking up products."


# ---------- nodes ----------
def should_continue(state: AgentState):
    try:
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            logger.debug("should_continue: Agent decided to use tools.")
            return "tools"
        logger.debug("should_continue: Agent decided to end.")
        return "__end__"
    except Exception as e:
        logger.error(f"should_continue: An error occurred: {e}")
        return "__end__"  # Fallback to end in case of error


def call_llm(state: AgentState):
    logger.info("calling llm...")
    try:
        prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessage(
                    content="""You are a helpful e-commerce chatbot.
                                 Always call the `products_look_up` tool when the user asks about products."""
                ),
                MessagesPlaceholder("messages"),
            ]
        )
        current_time = datetime.now().isoformat()
        msgs = prompt.format_messages(messages=state["messages"], time=current_time)
        result = llm.invoke(msgs)
        return {"messages": [result]}
    except Exception as e:
        logger.error(f"call_llm: An error occurred during LLM invocation: {e}")
        return {"messages": [AIMessage(content=f"An error occurred: {e}")]}


# ---------- workflow ----------
workflow = StateGraph(AgentState)
workflow.add_node(call_llm)
workflow.add_node(products_look_up)
workflow.add_edge(START, "call_llm")
workflow.add_conditional_edges(
    "agent", should_continue, {"tools": "tools", "END": "END"}
)
workflow.add_edge("tools", "agent")
app = workflow.compile()


# ---------- usage ----------
async def chat_agent(thread_id: str, message: str):
    try:
        logger.info(
            f"chat_agent: Invoking agent for thread_id: {thread_id}, message: {message}"
        )
        result = await app.ainvoke(
            {"messages": [HumanMessage(content=message)]},
            {"recursion_limit": 10, "configurable": {"thread_id": thread_id}},
        )
        final_content = result["messages"][-1].content
        logger.info(
            f"chat_agent: Agent invocation successful. Response: {final_content}"
        )
        return final_content
    except Exception as e:
        logger.error(
            f"chat_agent: An error occurred during agent invocation for thread_id {thread_id}: {e}"
        )
        return f"An error occurred while processing your request: {e}"
