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


class OrderItem(BaseModel):
    id: str
    product: str
    qty: int
    price: float
    purchase_date: datetime
    status: str
    card_last4: str


class AgentStateModel(BaseModel):
    input: str
    email: Optional[str] = None
    intent: Optional[str] = None
    reasoning: Optional[str] = None
    tool_calls: List[str] = []
    tool_results: List[str] = []
    output: Optional[str] = None


# Pydantic  models for data extraction using Gemini LLM


def extract_orders_details(raw_orders_json: str) -> List[OrderItem]:
    """
    Use Gemini LLM to extract structured order data from JSON string
    and validate with Pydantic.
    """

    model = genai.GenerativeModel("gemini-2.5-flash")

    prompt = f"""

    Extract structured order data from the following JSON string.
    Output as a JSON array of objects with keys: id, product, qty, price,
    purchase_date, status, card_last4.

    {raw_orders_json}

    """
    try:
        response = model.generate_content(prompt)
        extracted_json = response.text.strip()
        # Parse extracted JSON
        orders_data = json.loads(extracted_json)
        return [OrderItem(**o) for o in orders_data]
    except Exception as e:
        print(f"[GEMINI ERROR] {e}")
        return []

# --- LangGraph Logging ---


def log_orders(email: str, orders: List[OrderItem]):
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


def order_agent(state: dict) -> dict:
    print("[AGENT] order_agent selected")
    # Validate agent state
    try:
        state_model = AgentStateModel(**state)
    except ValidationError as e:
        return {"output": f"Invalid input: {e}"}
    if not state_model.email:
        state_model.output = "Please provide your email to look up your orders."
        return state_model.dict()

    # --- Get user orders from db ---

    user_data = db.get_user(state_model.email)
    if not user_data or "orders_json" not in user_data:
        state_model.output = "No orders found."
        return state_model.dict()
    raw_orders_json = user_data["orders_json"]

    # --- Extract structured orders via Gemini ---

    orders = extract_orders_details(raw_orders_json)
    if not orders:
        state_model.output = "No valid orders found."
        return state_model.dict()

    # --- Log events ---
    log_orders(state_model.email, orders)

    # --- Generate summary via Gemini ---
    model = genai.GenerativeModel("gemini-2.5-flash")
    order_list_text = "\n".join(
        [f"- {o.product} (x{o.qty}), ${o.price:.2f}, status: {o.status}" for o in orders])
    summary_prompt = f"""
    Generate a friendly summary of the following orders, suitable for displaying to the user:
    {order_list_text}

    """
    try:
        response = model.generate_content(summary_prompt)
        summary_text = response.text.strip()
    except Exception as e:
        print(f"[GEMINI ERROR] {e}")
        summary_text = "Here are your recent orders:\n" + order_list_text
    state_model.output = summary_text
    return state_model.dict()

# --- END OF AGENT DEFINITION ---
# --- LangGraph Logging ---


def log_order_confirmation(email: str, order_id: str):
    graph.log_event(
        name="order_confirmation_sent",
        metadata={
            "email": email,
            "order_id": order_id,
            "timestamp": datetime.now().isoformat()
        }
    )
    print(f"[LOG] Order confirmation logged for {email}, order {order_id}")
    # --- Send confirmation email ---
    message = Mail(
        from_email=os.getenv("SENDGRID_FROM_EMAIL"),
        to_emails=email,
        subject="Order Confirmation",
        html_content=f"Your order {order_id} has been confirmed."
    )
    try:
        sendgrid_client.send(message)
        print(f"[EMAIL] Confirmation sent to {email}")
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")


# --- END OF LOGGING FUNCTION ---
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

raw_input = """

    User: Jane Doe

    Email: jane@example.com

    Order ID: ORD-5678

    Items:

      - Laptop: 1200 USD

      - Mouse: 25 USD

    """


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


initial_state = {"input": raw_input, "email": "bob.smith@gmail.com",
                 "orders": extract_orders_details(raw_input), "tool_calls": [], "tool_results": [], "output": None}
final_state = run_order_agent(initial_state)
print(final_state["output"])
