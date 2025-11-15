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
    print("[AGENT] billing_agent selected")
    intent = state.get("intent") or "".lower().strip()
    # Handle different billing-related intents
    if intent == "check payment":
        state["output"] = (
            "I'm gonna check your payment!. Input your payment ID to proceed."
        )
        return get_payment_status(state)
    else: 
        state["output"] = (
            "Hello! "
            "I can help with payment-related inquiries. "
            "To check on a payment, please type check payment."
            #"To check on multiple payments, please type check mass payments."
        )
        return state

    
#Need to add version of this method for mass payments lookup?
def get_payment_status(state: AgentState) -> AgentState:
    #Check User is Logged in
    email = (state.get("email") or "").strip().lower()
    if not email or email == " ":
        state["output"] = (
            "You're currently using a guest session. Please log in to check payment status."
        )
        return state
    if "_" not in (state.get("input") or ""):
        state["output"] = "Please provide a payment ID to check its status."
        return state
    
    payment_id = (state.get("input") or "").strip()
    db_payment = db.get_payment_by_id(payment_id, email)

    #Extract fields with defaults
    status = db_payment["status"] or "Unknown"
    created_at = db_payment["created_at"]

    if status == "Unknown":
        state["output"] = "I couldn’t find any payments associated with this account and payment id."
        return state
    
    parts = []
    parts.append(f"The payment status of payment **{payment_id}** is **{status}**.")
    if created_at:
        parts.append(f"(This payment was processed at {created_at}.)")
    state["output"] = " ".join(parts)
    return state
