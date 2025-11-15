from datetime import datetime
import db
import os
import json
from typing import TypedDict, Optional, List
from pydantic import BaseModel, ValidationError
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import google.generativeai as genai

# Initialize database connection
db.init_db()


# load environment variables from .env file
load_dotenv()
# Configure Google Gemini API
genai.configure(api_key=os.getenv("GOOGLE_GEMINI_API_KEY"))

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


# ---langraph Logger---
graph = StateGraph(AgentState)

# Define Pydantic model for order details


class Order(BaseModel):
    id: str
    product: str
    qty: int
    price: float
    purchase_date: datetime
    status: str
    card_last4: str


class Orders(BaseModel):
    input: str
    email: Optional[str] = None
    intent: Optional[str] = None
    reasoning: Optional[str] = None
    tool_calls: List[str] = []
    tool_results: List[str] = []
    output: Optional[str] = None


# Pydantic  models for data extraction using Gemini LLM


def orders(orders: str) -> List[Order]:
    """
    Use Gemini LLM to extract structured order data from JSON string
    and validate with Pydantic.
    """

    model = genai.GenerativeModel("gemini-2.5-flash")

    prompt = f"""

    Extract structured order data from the following JSON string.
    Output as a JSON array of objects with keys: id, product, qty, price,
    purchase_date, status, card_last4.

    {orders}

    """
    try:
        response = model.generate_content(prompt)
        extracted_json = response.text.strip()
        # Parse extracted JSON
        orders_data = json.loads(extracted_json)
        return [Order(**o) for o in orders_data]
    except Exception as e:
        print(f"[GEMINI ERROR] {e}")
        return []

# --- LangGraph Logging ---


def log_orders(email: str, orders: List[Order]):
    for order in orders:
        graph.log_event(
            name="order_viewed",
            metadata={
                "email": email,
                "order_id": order.id,
                "status": order.status,
                "timestamp": datetime.now().isoformat()
            }
        )
    print(f"[LOG] {len(orders)} orders logged for {email}")


# ---agent definition---
def order_agent(state: AgentState) -> AgentState:
    print("[AGENT] order_agent selected")
    user = db.get_user(state.get("email") or "")
    if user:
        # Adjust columns to match your db schema
        # For example, orders may be stored as JSON in a specific column
        try:
            # guess columns safely:
            orders_json = "input"
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


# ---run order agent---
result = order_agent({
    "input": "Show me my recent orders",
    "email": "<user_email>",
    "intent": "order_lookup",
    "reasoning": "User wants to see their recent orders",
    "tool_calls": [],
    "tool_results": [],
})
print(result["output"])
# test order agent with sample input--


def run_order_agent(state: AgentState) -> AgentState:
    if not isinstance(state, dict):
        state = {"input": str(state)}
    try:
        return order_agent(state)
    except Exception as e:
        state.setdefault("tool_calls", [])
        state.setdefault("tool_results", [])
        state["tool_results"].append(f"[FATAL] {e!r}")
        state["output"] = "Sorry—something went wrong while checking your orders."
        return state


# example usage:
# initial_state = {"input": "Show me my recent orders", "email": "user@example.com"}
# test order agent with sample input--
input = """

    User: Jane Doe

    Email: jane@example.com

    Order ID: ORD-5678

    Items:

      - Laptop: 1200 USD

      - Mouse: 25 USD

    """


initial_state = {"input": input, "email": "jane@example.com",
                 "orders": orders(input), "tool_calls": [], "tool_results": [], "output": None}
final_state = run_order_agent(initial_state)
print(final_state["output"])
