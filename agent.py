import os
import db
import json
from typing import TypedDict, List, Optional
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_google_genai import ChatGoogleGenerativeAI
from db import get_user_by_email, log_event, update_user_last_option


# --- Load .env ---
load_dotenv()

# --- Tools ---
def change_address(query: str) -> str: # mock tool will update when DB is connected
    try:
        return str(eval(query))
    except Exception:
        return "Error evaluating expression"

#Tool: get user orders from database
def get_user_orders(email: str) -> str:
    orders, _ = db.get_user_orders(email)
    return orders or "No orders found."

#Tool: get shipping status from database
def get_shipping_status(email: str) -> str:
    _, shipping_status = db.get_user_orders(email)
    return shipping_status or "Unknown"


# --- State definition ---
class AgentState(TypedDict): # defines the state structure for the agent, helps with logging
    input: str
    reasoning: Optional[str]
    tool_calls: List[str]
    tool_results: List[str]
    output: Optional[str]


# --- Gemini model ---
model = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash", #use gemini-2.5-lite for cheaper option
    google_api_key=os.environ["GOOGLE_API_KEY"],
    stream=True  # enable streaming
)


# --- Nodes ---
def planner(state: AgentState): # decides which tools to call
    query = state["input"]
    response = model.invoke(
        f"You are a helpful customer support assistant for CapGemini with tools.\n"
        f"Tools: change_address, get_user_orders, get_shipping_status.\n"
        f"To get order details or shipping status, call the appropriate tool with the user's email.\n"
        f"Decide if you need to call a tool.\n"
        f"Answer politely, and only about our products, services, or company policies.\n"
        f"If you don’t know, say you will connect the user to a human agent.\n"
        f"User query: {query}\n"
        f'{{"reasoning": "...", "tool_calls": ["toolname: argument", ...]}}'
    )
    try:
        parsed = json.loads(response.content)
    except Exception:
        parsed = {"reasoning": "Failed to parse", "tool_calls": []}
    state["reasoning"] = parsed["reasoning"]
    state["tool_calls"] = parsed.get("tool_calls", [])
    return state


def tool_executor(state: AgentState): #implements the tools, and calls methods, For future use. 
    #execute tool calls
    results = []
    email = state.get("email")
    for call in state.get("tool_calls", []):
        if call.startswith("change_address"):
            arg = call.split(":", 1)[-1].strip()
            results.append(change_address(arg))
        elif call.startswith("get_user_orders"):
            results.append(get_user_orders(email or ""))
        elif call.startswith("get_shipping_status"):
            results.append(get_shipping_status(email or ""))
        else:
            results.append(f"Unknown tool call: {call}")
    state["tool_results"] = results
    return state


def finalizer(state: AgentState):
    query = state["input"]
    reasoning = state.get("reasoning", "")
    tools = "\n".join(
        f"{call} → {result}"
        for call, result in zip(state.get("tool_calls", []), state.get("tool_results", []))
    )
    prompt = (
        f"User query: {query}\n"
        f"Reasoning: {reasoning}\n"
        f"Tool outputs:\n{tools}\n\n"
        f"Now give the final helpful answer to the user."
    )
    response = model.invoke(prompt)
    state["output"] = response.content
    return state


# --- Build graph ---
graph = StateGraph(AgentState)
graph.add_node("planner", planner) #decides which agents to call
graph.add_node("tool_executor", tool_executor) #executes the tools
graph.add_node("finalizer", finalizer) #finalizes the response

graph.set_entry_point("planner")
graph.add_edge("planner", "tool_executor")
graph.add_edge("tool_executor", "finalizer")
graph.add_edge("finalizer", END)

memory = MemorySaver()
app = graph.compile(checkpointer=memory) #checkpointer to save state history such as name, or other customer info in same session.

# # --- Helper function for Streamlit ---
# def ask_agent(query: str, thread_id: str = "default", email: str = None) -> str:
#     result = app.invoke(
#         {"input": query},
#         config={"configurable": {"thread_id": thread_id}}
#     )
#     return result["output"]




# --- Helper function for Streamlit --- #I modified this fucntion
def ask_agent(query: str, thread_id: str = "default", email: str = None) -> str:
    state = {"input": query}
    if email:
        state["email"] = email
    result = app.invoke(
        state,
        config={"configurable": {"thread_id": thread_id}}
    )
    return result["output"]


