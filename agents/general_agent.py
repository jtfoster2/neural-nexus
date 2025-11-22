import os
import db
import json
from typing import TypedDict, Optional, List, Dict, Any
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

    # Context from memory_agent / supervisor
    context_summary: Optional[str]
    context_refs: Optional[List[str]]
    preface: Optional[str]
    memory: Optional[Dict[str, Any]]

# --- Gemini model ---
model = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.environ["GOOGLE_API_KEY"],
    #stream=True  # enable streaming
)

model_fast = ChatGoogleGenerativeAI( #currenly used for summarization only. 
    model="gemini-2.5-flash-lite",
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


def _build_prompt(state: AgentState) -> str:
    """Builds a prompt that includes memory context."""
    lines: List[str] = [SYSTEM_PROMPT]

    # Builds up context from memory / prior messages
    preface = state.get("preface")
    if preface:
        lines.append("CONTEXT FROM PREVIOUS MESSAGES:")
        lines.append(preface.strip())

    # Fallback
    elif state.get("context_summary"):
        lines.append("CONTEXT SUMMARY:")
        lines.append(state["context_summary"])

    # Current user message
    user_text = state.get("input") or ""
    lines.append("USER MESSAGE:")
    lines.append(user_text.strip())

    return "\n\n".join(lines)


def general_agent(state: AgentState) -> AgentState:
    """Main general-purpose agent. Uses memory context if present."""
    if not isinstance(state, dict):
        state = {"input": str(state)} 

    prompt = _build_prompt(state)
    state.setdefault("tool_calls", [])
    state.setdefault("tool_results", [])

    try:
        resp = model.invoke(prompt)
        content = getattr(resp, "content", None) or str(resp)
        state["output"] = content.strip()
    except Exception as e:
        state["tool_results"].append(f"[ERROR] general_agent: {type(e).__name__}: {e}")
        state["output"] = (
            "Sorry—something went wrong while answering your question. "
            "Please try again in a moment."
        )

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
