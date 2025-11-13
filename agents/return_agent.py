import re
from typing import TypedDict, Optional, List, Dict

import db
from agents import message_agent as msg


class AgentState(TypedDict):
    input: str
    email: Optional[str]
    intent: Optional[str]
    reasoning: Optional[str]
    tool_calls: List[str]
    tool_results: List[str]
    output: Optional[str]

def return_agent(state: AgentState) -> AgentState:
    print("[AGENT] return_agent selected")
    text = (state.get("input") or "").strip()
    email = (state.get("email") or "").strip().lower()

    # GUARD! must have an email (non-guest)
    if not email or email == " ":
        state["output"] = (
            "You're currently using a guest session. Please log in or sign up to start a return."
        )
        return state

    # Attempt to extract order ID from user input
    order_id = _get_orderid(text)
    if order_id:
        # Apply the return request
        if _process_return(email, order_id):
            state["output"] = (
                "Your request for a return has been initiated. You should receive a confirmation email shortly."
            )
        else:
            state["output"] = (
                "Something went wrong with processing this return. Either this order ID is invalid, not tied to your account, or the order is not eligible for return."
            )
        return state
    else:
        # If no return info found, ask for the order number
        state["output"] = (
            "I can help with getting a return started or answering questions about our return policy. "
            "Tell me the order number of the order you'd like to return."
        )
        return state

def _get_orderid(text: str) -> str:
    """
        Parse order IDs from free-form text.
        Accepts patterns like: key=value or key: value
        Example: "order id=ord_12345 or order id=12345"
        Inputs should be normalized to 'ord_12345' format.
        """
    if not text:
        return {}
    lowered = text.lower()
    order_num = re.findall(r'\d+', lowered)

    if not order_num:
        return {}
    else:
        return 'ord_' + order_num[0]

def _process_return(email:str, orderid: str) -> bool:
    """ Process the return request for the given order ID and email."""
    print("Attempting to process return for order: ", orderid)
    user = db.get_user(email)
    if not orderid:
        print("Couldn't find order by extracted ID: ", orderid)
        return False

    db.set_order_status(orderid, "return requested")
    print(orderid, " marked as returned in database.")
    msg.message_agent({  # sends notification email to user
        "email": email,
        "order_id": orderid,
        "name": db.get_user_first_name(email) or "",
        "event_type": "return_requested",
    })
    return True
