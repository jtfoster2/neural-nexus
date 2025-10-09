import db
from typing import TypedDict, Optional, List


def message_agent(state: AgentState) -> AgentState:
    print("[AGENT] message_agent selected")
    user = db.get_user(state.get("email") or "")
    state["output"] = (
        "Fetching chat history…"
        if user else
        "Please provide your email to fetch chat history."
    )
    return state