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

def account_agent(state: AgentState) -> AgentState:
    user = db.get_user_by_email(state.get("email") or "")
    state["output"] = (
        "Routing to specialized **Account** agent."
        if user else
        "Please provide your email to look into your account."
    )
    return state

def forgot_password_agent(state: AgentState) -> AgentState:
    user = db.get_user_by_email(state.get("email") or "")
    state["output"] = (
        "I can help start a password reset. Please confirm the email on file."
        if user else
        "Please provide your email to start a password reset."
    )
    return state

def change_address(query: str) -> str: # mock tool will update when DB is connected
    try:
        return str(eval(query))
    except Exception:
        return "Error evaluating expression"