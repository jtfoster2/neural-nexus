import json
import os
import sys
import db
import re
from typing import TypedDict, Optional, List, Dict, Any
import message_agent as msg


sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')))

# Initialize database connection
db.init_db()


# Define the AgentState TypedDict


class AgentState(TypedDict):
    input: str
    email: Optional[str]
    intent: Optional[str]
    event_type: Optional[str]  # 'ORDER_EVENT' or 'CHECK_ORDER_EVENT'
    reasoning: Optional[str]
    tool_calls: List[str]
    tool_results: List[str]
    output: Optional[str]
    context_summary: Optional[str]
    context_refs: Optional[List[str]]
    memory: Optional[Dict[str, Any]]

# route event based on intent


def route_event(state: AgentState) -> str:
    """Route to order-event or check-order based on intent."""
    intent = (state.get("input") or "").lower()
    event_type = (state.get("event_type") or "").upper()

    if event_type == "ORDER_EVENT" or any(k in intent for k in ["place order", "buy", "purchase", "new order"]):
        return "order_event"
    return "check_order_event"


# Main entry point


def order_agent(state: AgentState) -> AgentState:
    print("[AGENT] order_agent selected")
    user_email = state.get("email")
    user = db.get_user(user_email or "")

    if user and user_email:
        # Get orders from the orders and order_items tables for this user
        try:
            orders = db.list_orders_for_user(user_email)
            data = []

            if orders:
                conn = db.get_connection()
                cursor = conn.cursor()

                for order in orders:
                    order_id = order['order_id']
                    # Get items for this order
                    cursor.execute(
                        "SELECT * FROM order_items WHERE order_id = ?", (order_id,))
                    items = cursor.fetchall()

                    # Get payment info
                    cursor.execute(
                        "SELECT * FROM payments WHERE order_id = ? AND email = ?", (order_id, user_email))
                    payment = cursor.fetchone()
                    card_last4 = 'N/A'
                    if payment and 'provider_txn_id' in payment.keys() and payment['provider_txn_id']:
                        card_last4 = payment['provider_txn_id'][-4:] if len(
                            payment['provider_txn_id']) >= 4 else 'N/A'

                    # Build order data
                    for item in items:
                        data.append({
                            'id': order_id,
                            'product': item['name'],
                            'qty': item['qty'],
                            'price': (item['unit_price_cents'] or 0) / 100,
                            'purchase_date': order['created_at'] if 'created_at' in order.keys() else 'N/A',
                            'status': order['status'] if 'status' in order.keys() else 'pending',
                            'card_last4': card_last4
                        })
        except Exception as e:
            print(f"Error fetching orders: {e}")
            data = []

        if data:
            lines = [
                f"Order ID: {o.get('id', 'N/A')} | Product: {o.get('product', 'N/A')} | "
                f"Qty: {o.get('qty', 'N/A')} | Price: ${o.get('price', 0):.2f} | "
                f"Purchase Date: {o.get('purchase_date', 'N/A')} | Status: {o.get('status', 'N/A')} | "
                f"Card Ending: {o.get('card_last4', 'N/A')}"
                for o in data
            ]

            # --- Email Confirmation Logic ---
            email_body = "Thank you for shopping with us! Here is a summary of your recent orders:\n\n" + \
                         "\n".join(lines) + \
                         "\n\nIf you have any questions, please reply to this email."
            email_subject = "Your Order Details and Confirmation"

            try:
                if hasattr(msg, 'send_email'):
                    msg.send_email(
                        to_email=user_email,
                        subject=email_subject,
                        value=email_body
                    )
                    email_status = f"Order summary successfully sent to {user_email}."
                else:
                    email_status = "Email function not available."
            except Exception as e:
                email_status = f"Failed to send email confirmation: {e}"

            # Update the agent's output with the details and the email status
            state["output"] = f"Here are your order details:\n{'-'*30}\n" + \
                "\n".join(lines) + \
                f"\n\n{email_status}"
        else:
            state["output"] = "No orders found."
    else:
        state["output"] = "Please provide your email to look up your orders."

    return state

# order event handler


def order_event(state: AgentState) -> AgentState:
    """Place order, extract data, send confirmation, notify user"""
    email = state.get("email", "")
    user = db.get_user(email)
    if not user:
        state["output"] = " User not found. Please provide valid email."
        return state

    user_name = user['name'] if 'name' in user.keys(
    ) else email.split('@')[0].title()

    # Extract order from raw_order or input
    raw = state.get("raw_order") or state.get("input", "")
    order_data = _extract_order_data(raw)

    if not order_data:
        state["output"] = " Could not extract order details."
        return state

    # Create order in database
    order_id = order_data.get("order_id", f"ord_{hash(raw) % 10000}")
    subtotal = order_data.get("subtotal_cents", 0)
    tax = order_data.get("tax_cents", 0)
    shipping = order_data.get("shipping_cents", 0)
    shipping_addr = order_data.get("shipping_address", "")

    db.add_order(order_id, email, subtotal, tax, shipping,
                 discount_cents=0, status="pending", shipping_address=shipping_addr)

    for item in order_data.get("items", []):
        db.add_order_item(
            order_id, item["sku"], item["name"], item["qty"], item["unit_price_cents"])

    # Send confirmation email
    email_state = {"email": email,
                   "input": f"Order {order_id} confirmation", "output": ""}
    try:
        if hasattr(msg, 'send_order_confirmation'):
            msg.send_order_confirmation(
                email_state, order_id, order_data["items"], subtotal + tax + shipping)
        else:
            print(f" Email function not available")
    except Exception as e:
        print(f" Email failed: {e}")

# Build response with specific format
    data = [
        {
            "id": order_id,
            "product": item["name"],
            "qty": item["qty"],
            "price": f"${item['unit_price_cents'] / 100:.2f}",
            "purchase_date": "now",
            "status": "pending",
            "card_last4": "N/A"
        }
        for item in order_data["items"]
    ]

    lines = [
        f"Order ID: {o.get('id', 'N/A')} | Product: {o.get('product', 'N/A')} | "
        f"Qty: {o.get('qty', 'N/A')} | Price: {o.get('price', 'N/A')} | "
        f"Purchase Date: {o.get('purchase_date', 'N/A')} | Status: {o.get('status', 'N/A')} | "
        f"Card Ending: {o.get('card_last4', 'N/A')}"
        for o in data
    ]

    state["output"] = f"""  ORDER PLACED SUCCESSFULLY!

  Order ID: {order_id}
  User: {user_name}

  ORDER DETAILS:
{chr(10).join(lines)}

  Total: ${(subtotal + tax + shipping) / 100:.2f}

  Confirmation email sent
  Logged to supervisor"""

    state["order_id"] = order_id
    state["tool_calls"].append(f"place_order({order_id})")
    state["tool_results"].append(f"Order {order_id} placed and confirmed")
    return state

# check order event handler


def check_order_event(state: AgentState) -> AgentState:
    """Query order details for support issues."""
    email = state.get("email", "")
    user = db.get_user(email)
    if not user:
        state["output"] = " User not found."
        return state

    user_name = user['name'] if 'name' in user.keys(
    ) else email.split('@')[0].title()
    query = state.get("input", "").lower()

    # Extract order ID or list all
    # Only match if "ord" is followed by underscore or dash and alphanumeric
    order_id_match = re.search(r'\b(ord[_-]\w+)\b', query, re.IGNORECASE)

    if order_id_match:
        # Specific order lookup
        order_id = order_id_match.group(1)
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM orders WHERE order_id = ? AND email = ?", (order_id, email))
        order = cursor.fetchone()

        if not order:
            state["output"] = f" Order {order_id} not found."
            state["tool_calls"].append(f"check_order({order_id})")
            state["tool_results"].append(f"Order {order_id} not found")
            return state

        cursor.execute(
            "SELECT * FROM order_items WHERE order_id = ?", (order_id,))
        items = cursor.fetchall()

        # Get payment info
        cursor.execute(
            "SELECT * FROM payments WHERE order_id = ? AND email = ?", (order_id, email))
        payment = cursor.fetchone()
        card_last4 = 'N/A'
        if payment and 'provider_txn_id' in payment.keys() and payment['provider_txn_id']:
            card_last4 = payment['provider_txn_id'][-4:] if len(
                payment['provider_txn_id']) >= 4 else 'N/A'

        # Build data with specific format
        data = [
            {
                "id": order_id,
                "product": item['name'],
                "qty": item['qty'],
                "price": f"${(item['unit_price_cents'] or 0) / 100:.2f}",
                "purchase_date": order['created_at'] if 'created_at' in order.keys() else 'N/A',
                "status": order['status'] if 'status' in order.keys() else 'pending',
                "card_last4": card_last4
            }
            for item in items
        ]

        lines = [
            f"Order ID: {o.get('id', 'N/A')} | Product: {o.get('product', 'N/A')} | "
            f"Qty: {o.get('qty', 'N/A')} | Price: {o.get('price', 'N/A')} | "
            f"Purchase Date: {o.get('purchase_date', 'N/A')} | Status: {o.get('status', 'N/A')} | "
            f"Card Ending: {o.get('card_last4', 'N/A')}"
            for o in data
        ]

        total = ((order['subtotal_cents'] or 0) + (order['tax_cents']
                 or 0) + (order['shipping_cents'] or 0)) / 100

        state["output"] = f"""Hi {user_name}! 

  ORDER DETAILS:
{chr(10).join(lines)}

  Total: ${total:.2f}
  Shipping: {order['shipping_address'] if 'shipping_address' in order.keys() else 'N/A'}

  Need help? Reply with: modify order {order_id} | cancel order {order_id} | track {order_id}"""

        state["tool_calls"].append(f"check_order({order_id})")
        state["tool_results"].append(f"Order {order_id} details retrieved")

    else:
        # List all orders
        orders = db.list_orders_for_user(email)
        if not orders:
            state["output"] = f"Hi {user_name}! You have no orders yet."
            return state

        all_lines = []
        for order in orders:
            order_id = order['order_id']
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM order_items WHERE order_id = ?", (order_id,))
            items = cursor.fetchall()

            cursor.execute(
                "SELECT * FROM payments WHERE order_id = ? AND email = ?", (order_id, email))
            payment = cursor.fetchone()
            card_last4 = 'N/A'
            if payment and 'provider_txn_id' in payment.keys() and payment['provider_txn_id']:
                card_last4 = payment['provider_txn_id'][-4:] if len(
                    payment['provider_txn_id']) >= 4 else 'N/A'

            data = [
                {
                    "id": order_id,
                    "product": item['name'],
                    "qty": item['qty'],
                    "price": f"${(item['unit_price_cents'] or 0) / 100:.2f}",
                    "purchase_date": order['created_at'] if 'created_at' in order.keys() else 'N/A',
                    "status": order['status'] if 'status' in order.keys() else 'pending',
                    "card_last4": card_last4
                }
                for item in items
            ]

            lines = [
                f"Order ID: {o.get('id', 'N/A')} | Product: {o.get('product', 'N/A')} | "
                f"Qty: {o.get('qty', 'N/A')} | Price: {o.get('price', 'N/A')} | "
                f"Purchase Date: {o.get('purchase_date', 'N/A')} | Status: {o.get('status', 'N/A')} | "
                f"Card Ending: {o.get('card_last4', 'N/A')}"
                for o in data
            ]
            all_lines.extend(lines)

        state["output"] = f"""Hi {user_name}! 

  YOUR ORDERS ({len(orders)}):
{chr(10).join(all_lines)}

  For details: check order [order_id]"""

        state["tool_calls"].append(f"list_orders({email})")
        state["tool_results"].append(f"Retrieved {len(orders)} orders")

    return state
# extract order data from raw input


def _extract_order_data(raw: str) -> Dict[str, Any]:
    """Extract order data from raw input."""
    try:
        if "{" in raw:
            return json.loads(raw)
        # Parse simple format: "Product x Qty @ Price"
        items = []
        for match in re.finditer(r'(\w+[\w\s]*)\s*x?\s*(\d+)\s*@?\s*\$?(\d+\.?\d*)', raw):
            items.append({
                "sku": f"SKU-{hash(match.group(1)) % 1000}",
                "name": match.group(1).strip(),
                "qty": int(match.group(2)),
                "unit_price_cents": int(float(match.group(3)) * 100)
            })
        if items:
            subtotal = sum(i["qty"] * i["unit_price_cents"] for i in items)
            return {
                "order_id": f"ord_{hash(raw) % 10000}",
                "items": items,
                "subtotal_cents": subtotal,
                "tax_cents": int(subtotal * 0.08),
                "shipping_cents": 500,
                "shipping_address": "User address"
            }
    except Exception as e:
        print(f" Extract error: {e}")
    return {}

    # -------------------------
# Example usage of order_agent
# run order agent
initial_state = {"input": "", "email": "demo@example.com",
                 "tool_calls": [], "tool_results": [], "output": None}
final_state = order_agent(initial_state)
print(final_state["output"])
