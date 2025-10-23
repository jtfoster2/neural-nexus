
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

def billing_agent(state: AgentState) -> AgentState:
    print("[AGENT] billing_agent selected")
    #user = db.get_user(state.get("email") or "")
    return state
