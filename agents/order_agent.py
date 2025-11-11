import json
from typing import TypedDict, Optional, List
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage
from dotenv import load_dotenv
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import sys
import os

# load environment variables from .env file
load_dotenv()

# Initialize SendGrid client
sendgrid_client = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))


class AgentState(TypedDict):
    input: str
    email: Optional[str]
    intent: Optional[str]
    reasoning: Optional[str]
    tool_calls: List[str]
    tool_results: List[str]
    output: Optional[str]
# order event specific fields added below
    order_event: str
    user_email: str
    order_details: str
    email_content: str
    confirmation_sent: bool = False
    log_status: str | None = None
    user_notified: bool = False
    # Define Pydantic model for order details
    order_id: str
    product_name: str
    quantity: int
    price: float
    purchase_date: str
    status: str | None = None


def order_agent(state: AgentState) -> AgentState:
    print("[AGENT] order_agent selected")
    user = db.get_user(state.get("email") or "")
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
                f"Order ID: {o.get('id', 'N/A')} | Product: {o.get('product', 'N/A')} | "
                f"Qty: {o.get('qty', 'N/A')} | Price: {o.get('price', 'N/A')} | "
                f"Purchase Date: {o.get('purchase_date', 'N/A')} | Status: {o.get('status', 'N/A')} | "
                f"Card Ending: {o.get('card_last4', 'N/A')}"
                for o in data
            ]
            state["output"] = "Here are your order details:\n" + \
                "\n".join(lines)
        else:
            state["output"] = "No orders found."
    else:
        state["output"] = "Please provide your email to look up your orders."
    return state
