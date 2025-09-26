from typing import Optional, Annotated, TypedDict, Sequence
from datetime import datetime
from langgraph.graph import StateGraph, message
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool as lc_tool
from langchain_google_genai import GoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from pydantic import SecretStr
import os
from dotenv import load_dotenv
from libs.database import Database  # your existing DB wrapper

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

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
    collection = Database.get_collection("products")
    total_count = await collection.count_documents({})
    if total_count == 0:
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
            return docs
    except Exception as e:
        print("Vector search failed:", e)

    docs = await collection.find(
        {
            "$or": [
                {"name": {"$regex": query, "$options": "i"}},
                {"description": {"$regex": query, "$options": "i"}},
            ]
        }
    ).to_list(length=n)
    return docs or "No products found"


# ---------- nodes ----------
def should_continue(state: AgentState):
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return "__end__"


def call_llm(state: AgentState):
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


# ---------- workflow ----------
workflow = StateGraph(AgentState)
workflow.add_node("agent", call_llm)
workflow.add_node("tools", products_look_up)
workflow.add_edge("__start__", "agent")
workflow.add_conditional_edges(
    "agent", should_continue, {"tools": "tools", "__end__": "__end__"}
)
workflow.add_edge("tools", "agent")
app = workflow.compile()


# ---------- usage ----------
async def chat_agent(thread_id: str, message: str):
    result = await app.ainvoke(
        {"messages": [HumanMessage(content=message)]},
        {"recursion_limit": 10, "configurable": {"thread_id": thread_id}},
    )
    return result["messages"][-1].content
