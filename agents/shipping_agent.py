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

def shipping_agent(state: AgentState) -> AgentState:
    print("[AGENT] shipping_agent selected")
    user = get_shipping_status(state.get("email") or "")
    if user:
        # Adjust index to your actual column for shipping status
        shipping_status = None
        for col in user:
            if isinstance(col, str) and col.lower() in {"in transit", "delivered", "processing", "shipped", "unknown"}:
                shipping_status = col
                break
        state["output"] = f"Your shipping status is: **{shipping_status or 'Unknown'}**."
    else:
        state["output"] = "Please provide your email to check shipping status."
    return state

#Tool: get shipping status from database
def get_shipping_status(email: str) -> str:
    shipping_status = db.list_orders_for_user(email)
    return shipping_status or "Unknown"
