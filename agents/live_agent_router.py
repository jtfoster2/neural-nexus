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
    return state
