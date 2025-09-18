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

def return_agent(state: AgentState) -> AgentState:
    user = db.get_user_by_email(state.get("email") or "")
    state["output"] = (
        "Routing to specialized **Refunds** agent."
        if user else
        "Please provide your email so we can look up the purchase for a refund."
    )
    return state
