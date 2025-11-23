import re
from typing import TypedDict, Optional, List, Dict, Any
from datetime import datetime

import db
from agents import message_agent as msg
from agents import policy_agent


class AgentState(TypedDict):
    input: str
    email: Optional[str]
    intent: Optional[str]
    reasoning: Optional[str]
    tool_calls: List[str]
    tool_results: List[str]
    output: Optional[str]

    # Context from memory_agent / supervisor
    context_summary: Optional[str]
    context_refs: Optional[List[str]]
    preface: Optional[str]
    memory: Optional[Dict[str, Any]]

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
    print(f"[RETURN] Extracted order_id: '{order_id}' from text: '{text}'")
    if order_id:
        # Get order details
        order = _get_order_details(email, order_id)
        print(f"[RETURN] Order lookup result: {order is not None}")
        if not order:
            state["output"] = (
                "I couldn't find that order number in your account. Please check the order number and try again."
            )
            return state
        
        # format order details for display
        order_info = _format_order_details(order)

        # Check return policy eligibility
        eligibility_result = _check_return_eligibility(order, text)
        if not eligibility_result["eligible"]:
            state["output"] = (
                f"{order_info}\n\n"
                f"**Return Policy Check:**\n"
                f"{eligibility_result['reason']}\n\n"
                f"If you have questions about this decision, please contact our customer support team."
            )
            return state

        # process the return
        if _process_return(email, order_id):
            state["output"] = (
                f"Your return request has been submitted.\n\n"
                f"{order_info}\n\n"
                f"**Return Policy Check:** ✅ Approved\n"
                f"{eligibility_result['reason']}\n\n"
                f"You should receive a confirmation email with return instructions shortly."
            )
        else:
            state["output"] = (
                "Something went wrong processing this return. Please try again or contact support."
            )
        return state
    else:
        # if no return info found, ask for the order number
        state["output"] = (
            "I can help with getting a return started. Please enter your order number of the order you'd like to return (e.g., `ord_123`)."
            
        )
        return state

def _get_orderid(text: str) -> str:
    """
    Parse order IDs from free-form text.
    Accepts patterns like: ord_123, ord_electronics_40d, or just numbers like 123
    """
    if not text:
        return ""
    
    # first try to find full order IDs that already start with ord_
    ord_pattern = re.findall(r'ord_[a-zA-Z0-9_]+', text.lower())
    if ord_pattern:
        return ord_pattern[0]
    
    # if no full ord_ pattern found, look for numbers and add ord_ prefix
    lowered = text.lower()
    order_num = re.findall(r'\d+', lowered)

    if not order_num:
        return ""
    else:
        return 'ord_' + order_num[0]


def _get_order_details(email: str, order_id: str) -> Optional[Dict[str, Any]]:
    """Get order details for the specified order ID and email."""
    orders = db.list_orders_for_user(email)
    for order in orders:
        order_dict = dict(order)
        if order_dict['order_id'] == order_id:
            return order_dict
    return None


def _format_order_details(order: Dict[str, Any]) -> str:
    """Format order details in a clean, readable way."""
    order_id = order.get('order_id', 'Unknown')
    
    # format the purchase date
    created_at = order.get('created_at', '')
    try:
        if isinstance(created_at, str):
            created = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
            purchase_date = created.strftime('%B %d, %Y at %I:%M %p')
        else:
            purchase_date = 'Unknown'
    except:
        purchase_date = created_at or 'Unknown'
    
    # format pricing
    subtotal_cents = order.get('subtotal_cents', 0)
    tax_cents = order.get('tax_cents', 0)
    shipping_cents = order.get('shipping_cents', 0)
    total_cents = order.get('total_cents', 0)
    
    subtotal = subtotal_cents / 100.0
    tax = tax_cents / 100.0
    shipping = shipping_cents / 100.0
    total = total_cents / 100.0
    
    details = [
        f"**Order:** {order_id}",
        "",
        f"**Purchased on:** {purchase_date}",
        "",
        "**Order Summary:**",
        "",
        f" • Subtotal: ${subtotal:.2f}",
        "",
        f" • Tax: ${tax:.2f}",
        "",
        f" • Shipping: ${shipping:.2f}",
        "",
        f" • Total: ${total:.2f}"
    ]
    
    return "\n".join(details)

def _check_return_eligibility(order: Dict[str, Any], user_input: str) -> Dict[str, Any]:
    """Check if the order is eligible for return according to policy."""
    # build order context for policy agent
    item_category = _determine_item_category(order)
    
    # calculate days since purchase
    from datetime import datetime
    created_at = order.get('created_at', '')
    try:
        purchase_date = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
        days_since_purchase = (datetime.now() - purchase_date).days
    except:
        days_since_purchase = 0
    
    order_context = {
        "order_id": order.get('order_id'),
        "status": order.get('status'),
        "created_at": created_at,
        "purchase_date": created_at,
        "item_category": item_category,
        "is_clearance": _is_clearance_item(order),
        "reason_for_return": _extract_return_reason(user_input)
    }
    
    # create a more explicit input for the policy agent
    policy_input = (
        f"Customer wants to return order {order.get('order_id')} purchased {days_since_purchase} days ago. "
        f"Item category: {item_category}. "
        f"Reason: {_extract_return_reason(user_input)}. "
        f"Is this return eligible under our policy?"
    )
    
    # create policy agent state
    policy_state = {
        "input": policy_input,
        "tool_calls": [],
        "tool_results": [],
        **order_context
    }
    
    # run policy check
    result_state = policy_agent.policy_agent(policy_state)
    policy_output = result_state.get("output", "")
    
    # debug logging
    print(f"[RETURN_POLICY] Policy agent output: {policy_output}")
    print(f"[RETURN_POLICY] Order context: {order_context}")
    
    #pParse the policy decision
    if "Decision: Eligible" in policy_output:
        return {
            "eligible": True,
            "reason": _extract_policy_reason(policy_output)
        }
    elif "Decision: Not eligible" in policy_output:
        return {
            "eligible": False,
            "reason": _extract_policy_reason(policy_output)
        }
    elif "Decision: Unclear" in policy_output:
        # for unclear cases, let's do a basic check ourselves
        # if it's within 60 days and not a restricted category, approve it
        from datetime import datetime
        created_at = order.get('created_at', '')
        try:
            purchase_date = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
            days_since_purchase = (datetime.now() - purchase_date).days
            category = _determine_item_category(order)
            
            # basic eligibility logic
            if days_since_purchase <= 60:
                if category == "Electronics" and days_since_purchase <= 30:
                    return {"eligible": True, "reason": "Electronics return within 30-day policy limit."}
                elif category in ["Consumables"]:
                    return {"eligible": False, "reason": "Consumables are non-returnable once opened unless defective."}
                elif category not in ["Electronics"]:
                    return {"eligible": True, "reason": "Return within 60-day policy limit for general merchandise."}
                else:
                    return {"eligible": False, "reason": f"Electronics must be returned within 30 days. This item is {days_since_purchase} days old."}
            else:
                return {"eligible": False, "reason": f"Return window expired. Items must be returned within 60 days. This order is {days_since_purchase} days old."}
        except:
            return {"eligible": False, "reason": "Unable to determine order date for policy check."}
    else:
        # if no decision format found, default to requiring manual review
        return {
            "eligible": False,
            "reason": f"Return eligibility requires manual review. Please contact customer support with your order details. (Debug: {policy_output[:100]}...)"
        }


def _determine_item_category(order: Dict[str, Any]) -> str:
    """Determine the category of items in the order for policy checking."""
    order_id = order.get('order_id', '')
    
    # get order items to determine category
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT sku, name 
            FROM order_items 
            WHERE order_id = ?
        """, (order_id,))
        items = cursor.fetchall()
        conn.close()
        
        # analyze item names/SKUs to determine category
        for item in items:
            sku = (item[0] or '').lower()
            name = (item[1] or '').lower()
            
            # Electronics keywords
            if any(word in sku + ' ' + name for word in [
                'iphone', 'ipad', 'laptop', 'computer', 'phone', 'tablet', 
                'headphones', 'speaker', 'camera', 'tv', 'monitor', 'electronics'
            ]):
                return "Electronics"
            
            # Apparel keywords  
            elif any(word in sku + ' ' + name for word in [
                'shirt', 'pants', 'dress', 'jacket', 'shoes', 'clothing',
                'apparel', 'wear', 'jeans', 'sweater', 'hoodie'
            ]):
                return "Apparel and Wearables"
            
            # Footwear keywords
            elif any(word in sku + ' ' + name for word in [
                'shoes', 'boots', 'sneakers', 'sandals', 'footwear'
            ]):
                return "Footwear"
            
            # Home goods keywords
            elif any(word in sku + ' ' + name for word in [
                'kitchen', 'home', 'decor', 'furniture', 'lamp', 'table'
            ]):
                return "Home Goods"
            
            # Accessories (Non-Electronics) keywords
            elif any(word in sku + ' ' + name for word in [
                'wallet', 'belt', 'bag', 'purse', 'handbag', 'backpack',
                'tool', 'tools', 'hammer', 'screwdriver', 'wrench',
                'watch', 'jewelry', 'necklace', 'bracelet', 'ring',
                'sunglasses', 'hat', 'cap', 'scarf', 'gloves'
            ]):
                return "Accessories (Non-Electronics)"
            
            # Consumables keywords
            elif any(word in sku + ' ' + name for word in [
                'cleaning', 'cleaner', 'soap', 'detergent', 'oil', 'oils',
                'coating', 'polish', 'wax', 'spray', 'liquid', 'cream',
                'lotion', 'shampoo', 'conditioner', 'food', 'snack',
                'supplement', 'vitamin', 'medicine', 'consumable'
            ]):
                return "Consumables"
        
        # check if it's a bundle/kit
        if len(items) > 1:
            return "Bundles and Kits"
        elif any(word in sku + ' ' + name for word in [
            'bundle', 'kit', 'set', 'pack', 'combo', 'collection'
        ]):
            return "Bundles and Kits"
        
        # default to general merchandise if no specific category found
        return "general merchandise"
        
    except Exception as e:
        print(f"Error determining item category: {e}")
        return "general merchandise"


def _is_clearance_item(order: Dict[str, Any]) -> bool:
    """Check if any items in the order are clearance/final sale."""
    # this would check the order_items table for clearance flags
    # for now, returning False as we don't have this data structure
    # incase he wants us to implement cleanrance item but i doubt it
    return False


def _extract_return_reason(user_input: str) -> str:
    """Extract the reason for return from user input."""
    # simple keyword matching for common return reasons
    user_input_lower = user_input.lower()
    
    if any(word in user_input_lower for word in ["defective", "broken", "damaged", "not working"]):
        return "defective item"
    elif any(word in user_input_lower for word in ["wrong", "incorrect", "mistake"]):
        return "incorrect item received"
    elif any(word in user_input_lower for word in ["changed mind", "don't want", "don't need"]):
        return "changed mind"
    elif any(word in user_input_lower for word in ["doesn't fit", "too small", "too large", "wrong size"]):
        return "sizing issue"
    else:
        return "customer initiated return"


def _extract_policy_reason(policy_output: str) -> str:
    """Extract the reason from policy agent output."""
    lines = policy_output.split('\n')
    for line in lines:
        if line.startswith("Reason:"):
            return line.replace("Reason:", "").strip()
    
    # if no specific reason found, return the full output cleaned up
    return policy_output.replace("Decision: Eligible", "").replace("Decision: Not eligible", "").strip()

def _process_return(email: str, orderid: str) -> bool:
    """Process the return request for the given order ID and email."""
    print("Attempting to process return for order: ", orderid)
    
    # Validate order exists and belongs to user
    order = _get_order_details(email, orderid)
    if not order:
        print("Couldn't find order by extracted ID or doesn't belong to user: ", orderid)
        return False

    db.set_order_status(orderid, "return requested")
    print(orderid, " marked as returned in database.")
    msg.message_agent({
        "email": email,
        "order_id": orderid,
        "name": db.get_user_first_name(email) or "",
        "event_type": "return_requested",
    })
    return True