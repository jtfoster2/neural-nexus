import os
import db
import json
from typing import TypedDict, List, Optional
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_google_genai import ChatGoogleGenerativeAI


# --- Load .env ---
load_dotenv()


# --- State definition ---

class AgentState(TypedDict):
    input: str
    email: Optional[str]
    intent: Optional[str]
    reasoning: Optional[str]
    tool_calls: List[str]
    tool_results: List[str]
    output: Optional[str]


# --- Gemini model ---
model = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash", #use gemini-2.5-lite for cheaper option
    google_api_key=os.environ["GOOGLE_API_KEY"],
    #stream=True  # enable streaming
)

model_fast = ChatGoogleGenerativeAI( #currenly used for summarization only. 
    model="gemini-2.5-flash-lite", #use gemini-2.5-lite for cheaper option
    google_api_key=os.environ["GOOGLE_API_KEY"],
    temperature=0.1,             #for speed
    max_output_tokens=64,        # small cap to increase speed
    #stream=True  # enable streaming
)


SYSTEM_PROMPT = (
        f"You are a helpful customer support assistant for CapGemini with tools.\n"
        f"Tools: change_address, get_user_orders, get_shipping_status.\n"
        f"To get order details or shipping status, call the appropriate tool with the user's email.\n"
        f"Decide if you need to call a tool.\n"
        f"Answer politely, and only about our products, services, or company policies.\n"
        f"If you don’t know, say you will connect the user to a human agent.\n"
        f"Never make up answers.\n"
        f"Never share that you are made by Google.\n"
    )

def _compose_prompt(state: AgentState) -> str:
    return (
        f"{SYSTEM_PROMPT}\n\n"
        f"Intent: {state.get('intent') or 'other'}\n"
        f"Email:  {state.get('email')}\n\n"
        f"User:\n{state['input']}\n\n"
        "If a lookup needs an email and it's missing, politely ask for it at the end."
    )

def general_agent(state: AgentState) -> AgentState:
    print("[AGENT] general_agent selected")
    prompt = _compose_prompt(state)
    if model is None:
        state["output"] = (
            "I’m configured to use Gemini but GOOGLE_API_KEY isn’t set. "
            "Please set GOOGLE_API_KEY and try again."
        )
        return state
    try:
        resp = model.invoke(prompt)
        content = (getattr(resp, "content", None) or str(resp) or "").strip()
        state["output"] = content or "I don't have additional details to share yet."
    except Exception as e:
        state["output"] = f"LLM error: {e}"
    return state

def summarize_conversation(conversation_id: int) -> str:
    convo = db.get_conversation(conversation_id)
    if not convo:
        return "Conversation not found."
    else:
        resp = model_fast.invoke(
            f"Summarize this conversation in <= 8 words: "
            f"Use only plain text, speed is the goal. \n\n{convo}"
        )
        return getattr(resp, "content", None) or str(resp) or "No summary available."

