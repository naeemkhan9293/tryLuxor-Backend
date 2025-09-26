from typing import Optional, Annotated, TypedDict, Sequence
from libs.database import Database
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import (
    BaseMessage,
    SystemMessage,
    HumanMessage,
    ToolMessage,
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


class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], lambda x, y: x + y]


@tool
async def products_look_up(query, n=10):
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
                    {"name": {"$regex": query, "options": "i"}},
                    {"description": {"$regex": query, "options": "i"}},
                    {"categories": {"$regex": query, "options": "i"}},
                    {"embedding_text": {"$regex": query, "options": "i"}},
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


tools = [products_look_up]
llm = GoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=api_key)
model = llm.with_structured_output(tools)


def should_continue(state: AgentState):
    messages = state["messages"]
    last_message = messages[-1]
    if not last_message.tool_calls:
        return "end"
    else:
        return "continue"


def call_model(state: AgentState):
    messages = state["messages"]
    response = model.invoke(messages)
    return {"messages": [response]}


workflow = StateGraph(AgentState)

workflow.add_node("agent", call_model)
workflow.add_node("tools", ToolNode(tools))

workflow.set_entry_point("agent")

workflow.add_conditional_edges(
    "agent", should_continue, {"continue": "tools", "end": END}
)

workflow.add_edge("tools", "agent")

graph = workflow.compile()


async def chat_agent(thread_id: Optional[str] = None, message: Optional[str] = None):
    if thread_id is None or message is None:
        raise ValueError("Thread ID and message are required")
    try:
        system_message = SystemMessage(
            content="""You are a helpful assistant that helps users find products in the database.
            You can use the `products_look_up` tool to search for products.
            When the user asks for products, you should call the `products_look_up` tool with the appropriate query.
            When you have found the products, you should return them to the user.
            If you cannot find any products, you should tell the user that you could not find any products.
            Do not make up products that are not in the database.
            """
        )

        human_message = HumanMessage(content=message)
        initial_state = {"messages": [system_message, human_message]}
        response = graph.invoke(initial_state)
        last_message = response["messages"][-1]

        if not last_message.tool_calls:
            return {"message": last_message.content}

        tool_outputs = []
        for tool_call in last_message.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            if tool_name == "products_look_up":
                products = await products_look_up.ainvoke(tool_args)
                for product in products:
                    product["_id"] = str(product["_id"])
                tool_outputs.append(
                    ToolMessage(
                        content=str(products),
                        tool_call_id=tool_call["id"],
                    )
                )

        final_state = {"messages": [last_message] + tool_outputs}
        final_response = graph.invoke(final_state)

        return final_response["messages"][-1].content
    except Exception as e:
        print(f"Error processing chat message: {e}")
        raise e