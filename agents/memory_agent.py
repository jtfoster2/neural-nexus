import db
from typing import TypedDict, Optional, List

class AgentState(TypedDict):
    input: str
    email: Optional[str]
    intent: Optional[str]
    reasoning: Optional[str]
    tool_calls: List[str]
    tool_results: List[str]
    output: Optional[str]


def memory_agent(state: AgentState) -> AgentState:
    user = db.get_user_by_email(state.get("email") or "")
    state["output"] = (
        "Fetching chat history…"
        if user else
        "Please provide your email to fetch chat history."
    )
    return state
