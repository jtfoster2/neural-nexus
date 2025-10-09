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

def live_agent_router(state: AgentState) -> AgentState:
    print("[AGENT] live_agent_router selected")
    user = db.get_user(state.get("email") or "")
    state["output"] = (
        "Connecting you with a live agent now… (placeholder)"
        if user else
        "Please provide your email and I’ll connect you with a live agent."
    )
    return state
