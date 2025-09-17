import json
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

def order_agent(state: AgentState) -> AgentState:
    user = db.get_user_by_email(state.get("email") or "")
    if user:
        # Adjust columns to match your db schema
        # For example, orders may be stored as JSON in a specific column
        try:
            # guess columns safely:
            orders_json = None
            for col in user:
                if isinstance(col, str) and col.strip().startswith("[") and "product" in col:
                    orders_json = col
                    break
            data = json.loads(orders_json) if orders_json else []
        except Exception:
            data = []

        if data:
            lines = [
                f"Order ID: {o.get('id','N/A')} | Product: {o.get('product','N/A')} | "
                f"Qty: {o.get('qty','N/A')} | Price: {o.get('price','N/A')} | "
                f"Purchase Date: {o.get('purchase_date','N/A')} | Status: {o.get('status','N/A')} | "
                f"Card Ending: {o.get('card_last4','N/A')}"
                for o in data
            ]
            state["output"] = "Here are your order details:\n" + "\n".join(lines)
        else:
            state["output"] = "No orders found."
    else:
        state["output"] = "Please provide your email to look up your orders."
    return state
