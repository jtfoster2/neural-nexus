from __future__ import annotations
from typing import TypedDict, Optional, List, Dict, Any, Callable
import db

class AgentState(TypedDict, total=False):
    input: str
    email: Optional[str]
    intent: Optional[str]
    reasoning: Optional[str]
    tool_calls: List[str]
    tool_results: List[str]
    output: Optional[str]
    
# ---------- billing_agent functionalities ----------
def billing_agent(state: AgentState) -> AgentState:
    intent = state.get("intent") or "".lower().strip()
    # Handle different billing-related intents
    if intent == "check payment":
        return get_payment_status(state)
    else: 
        state["output"] = state["output"] = (
            "Hello! "
            "I can help check the status of payments associated with your account. "
            "Please enter the payment ID of the payment you would like to check."
        )
        return state

    
#Need to add version of this method for mass payments lookup?
def get_payment_status(state: AgentState) -> AgentState:
    
    #Check User is Logged In
    email = (state.get("email") or "").strip().lower()
    if not email or email == " ":
        state["output"] = (
            "You're currently using a guest session. Please log in to check payment status."
        )
        return state
    
    state["output"] = "Please provide a payment ID to check its status."
    payment_id = state.get("input", "").strip()
    result = db.get_payment_status(payment_id)
    status = result["status"]
    payment_id = result.get("payment_id")
    created_at = result.get("created_at")
    if status == "Unknown" or not status:
        return "I couldn’t find any payments associated with this account and payment id."
    parts = []
    if payment_id:
        parts.append(f"The payment status of payment **{payment_id}** is **{status}**.")
    if created_at:
        parts.append(f"(This payment was processed at {created_at}.)")
    state["output"] = " ".join(parts)
    return state


