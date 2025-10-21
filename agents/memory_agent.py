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
    print("[AGENT] memory_agent selected")
    return state
