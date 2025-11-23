from __future__ import annotations
import re
import time
from typing import TypedDict, Optional, List, Dict, Any, Callable

import db


# ---------- Shared state type ----------

class AgentState(TypedDict, total=False):
    input: str
    email: Optional[str]
    intent: Optional[str]
    reasoning: Optional[str]
    tool_calls: List[str]
    tool_results: List[str]
    output: Optional[str]
    confidence: float
    
    # Context from memory_agent / supervisor
    context_summary: Optional[str]
    context_refs: Optional[List[str]]
    preface: Optional[str]
    memory: Optional[Dict[str, Any]]



# ---------- Tool Layer ----------

Tool = Callable[..., Any]

TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "orders:list_for_user": {
        "fn": lambda email: db.list_orders_for_user(email),
        "schema": {"email": "str (required)"},
        "desc": "Return orders for a given user email, newest first.",
    },
    "orders:get_by_id": {
        "fn": lambda order_id: db.get_order_by_id(order_id),
        "schema": {"order_id": "str (required)"},
        "desc": "Return details for a specific order by its ID.",
    },
    "orders:update_shipping_address": {
        "fn": lambda order_id, shipping_address: db.set_order_shipping_address(
            order_id, shipping_address
        ),
        "schema": {
            "order_id": "str (required)",
            "shipping_address": "str (required)",
        },
        "desc": "Update the shipping address for a specific order ID.",
    },
}


# ---------- Regex helpers ----------

EMAIL_REGEX = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
ORDER_REGEX = re.compile(r"\bord_\d{3,7}\b", re.IGNORECASE)
ORDER_ADDRESS_REGEX = re.compile(r"\b\d{1,6}\s+[A-Za-z0-9 .'-]+,\s*[A-Za-z .'-]+,\s*[A-Za-z]{2}\s+\d{5}(?:-\d{4})?\b", re.IGNORECASE,) #US address


def _resolve_order_id(state: AgentState) -> str: # Try to find an order ID from memory agent

    orderid = (state.get("order_id") or "").strip().lower()
    if orderid:
        return orderid

    mem = state.get("memory") or {}
    ents = mem.get("entities") or {}
    orders_from_mem = ents.get("orders") or []
    if orders_from_mem:
        # use the last mentioned order
        return orders_from_mem[-1].lower()

    text = state.get("input") or ""
    if "ORDER_REGEX" in globals():
        m = ORDER_REGEX.search(text)
        if m:
            return m.group(0).lower()

    return ""


def _format_money(cents: Any) -> str: # needed for formatting money amounts so that they show up as $xx.xx and not $xx.x
    try:
        c = int(cents)
    except Exception:
        return "N/A"
    return f"${c/100:,.2f}" # dollars with 2 decimal places


class OrderAgent:
    """
    Order agent:
    - Finds which order(s) the user is asking about
    - Looks them up via tools
    - Returns a summary to the user
    """

    def __init__(self, max_retries: int = 2, backoff_s: float = 0.4):
        self.max_retries = max_retries
        self.backoff_s = backoff_s

    def run(self, state: AgentState) -> AgentState:
        self._ensure_lists(state)

        # normalize / store intent
        intent = (state.get("intent") or "check order").lower().strip()
        state["intent"] = intent

        # 1) Perception: email + order_id
        self._extract_email(state)
        self._extract_order_id(state)

        if intent in ["change order address", "change shipping address"]:
            return change_order_shipping_address_agent(state)

        # 2) Plan (default "check order" behaviour)
        email = (state.get("email") or "").strip().lower()
        order_id = (state.get("order_id") or "").strip()

        plan = self._plan(state, email=email, order_id=order_id)
        if not plan:
            if not email and not order_id:
                state["output"] = (
                    "To look up your order, please provide your order number (for example `ord_001`)."

                )
                state["confidence"] = 0.3
                return state
            else:
                state["output"] = (
                    "Please provide either your email or an order ID (for example `ord_001`) "
                    "so I can look up your order."
                )
                state["confidence"] = 0.4
                return state

        # 3) Act
        observations: List[Dict[str, Any]] = []
        for step in plan:
            obs = self._call_tool_with_retries(step["tool"], step["args"], state)
            observations.append({"step": step, "obs": obs})

        # 4) Interpret
        result = self._interpret(observations, state)

        # 5) Communicate
        state["output"] = self._format_user_message(result)
        state["confidence"] = result.get("confidence", 0.7)
        return state


    # ---------- internals ----------

    def _ensure_lists(self, state: AgentState) -> None:
        state.setdefault("tool_calls", [])
        state.setdefault("tool_results", [])
        state.setdefault("debug", False)
        state.setdefault("max_retries", self.max_retries)

    def _extract_email(self, state: AgentState) -> None:
        if state.get("email"):
            return
        text = (state.get("input") or "").strip()
        m = EMAIL_REGEX.search(text)
        if m:
            state["email"] = m.group(0).lower()

    def _extract_order_id(self, state: AgentState) -> None:
        """
        Try to find an order ID from:
        - explicit state["order_id"]
        - memory_agent entities
        - current input text
        """
        if state.get("order_id"):
            return

        # From memory_agent entities if present
        mem = state.get("memory") or {}
        ents = mem.get("entities") or {}
        orders_from_mem = ents.get("orders") or []
        if len(orders_from_mem) == 1:
            state["order_id"] = orders_from_mem[0]
            return

        # From current text
        text = (state.get("input") or "")
        m = ORDER_REGEX.search(text)
        if m:
            state["order_id"] = m.group(0)

    # ----------------- Planning -----------------
    def _plan(self, state: AgentState, *, email: str, order_id: str) -> List[Dict[str, Any]]:
        
        if order_id:
            return [{"tool": "orders:get_by_id", "args": {"order_id": order_id}}]

        if email:
            return [{"tool": "orders:list_for_user", "args": {"email": email}}]

        return []


    def _call_tool_with_retries(self, tool_name: str, args: Dict[str, Any], state: AgentState):
        if tool_name not in TOOL_REGISTRY:
            raise ValueError(f"Unknown tool: {tool_name}")
        fn: Tool = TOOL_REGISTRY[tool_name]["fn"]

        retries = int(state.get("max_retries", self.max_retries))
        attempt = 0
        while True:
            attempt += 1
            try:
                state["tool_calls"].append(
                    f"{tool_name}({', '.join(f'{k}={v!r}' for k, v in args.items())})"
                )
                result = fn(**args)
                safe_result = self._safe_preview(result)
                state["tool_results"].append(self._truncate_for_log(safe_result))
                return result
            except Exception as e:
                state["tool_results"].append(f"[ERROR] {tool_name}: {e!r}")
                if attempt > retries:
                    raise
                time.sleep(self.backoff_s * attempt)

    # ---------- helper functions ----------

    def _safe_preview(self, value: Any) -> Any:
        try:
            if isinstance(value, list):
                return [self._row_to_dict(r) for r in value[:5]]
            return value
        except Exception:
            return "<unserializable>"

    def _row_to_dict(self, row: Any) -> Dict[str, Any]:
        try:
            if isinstance(row, dict):
                return row
            return dict(row)  # e.g., sqlite Row
        except Exception:
            return {"_repr": repr(row)}

    def _truncate_for_log(self, obj: Any, limit: int = 300) -> str:
        s = repr(obj)
        return s if len(s) <= limit else s[:limit] + "…"

    def _interpret(self, observations: List[Dict[str, Any]], state: AgentState) -> Dict[str, Any]:
        """
        Normalize into a list of order dicts + confidence.
        """
        if not observations:
            return {"orders": [], "confidence": 0.3}

        obs = observations[0]["obs"]

        # db.get_order_by_id might return a single row or a list
        rows: List[Dict[str, Any]] = []
        if obs is None:
            rows = []
        elif isinstance(obs, list):
            rows = [self._row_to_dict(r) for r in obs]
        else:
            rows = [self._row_to_dict(obs)]

        return {
            "orders": rows,
            "confidence": 0.9 if rows else 0.5,
        }

    def _format_user_message(self, result: Dict[str, Any]) -> str:
        orders = result.get("orders") or []
        if not orders:
            return "I couldn’t find any orders that match your request."

        # If multiple orders, a short list is shown
        if len(orders) > 1:
            lines = ["Here are your recent orders:"]
            for r in orders[:5]:
                oid = r.get("order_id", "Unknown")
                status = (r.get("status") or "Unknown").strip().capitalize()
                subtotal = r.get("subtotal_cents")
                tax = r.get("tax_cents")
                shipping = r.get("shipping_cents")
                total = None
                try:
                    if subtotal is not None and tax is not None and shipping is not None:
                        total = int(subtotal) + int(tax) + int(shipping)
                except Exception:
                    total = None

                money = _format_money(total) if total is not None else "N/A"
                lines.append(f"- **{oid}** — {status}, total {money}")
            return "\n".join(lines)
        
        # Single order: richer description
        o = orders[0]
        oid = o.get("order_id", "Unknown")
        status = (o.get("status") or "Unknown").strip().capitalize()
        created = o.get("created_at")
        subtotal = o.get("subtotal_cents")
        tax = o.get("tax_cents")
        shipping = o.get("shipping_cents")
        total = None
        try:
            if subtotal is not None and tax is not None and shipping is not None:
                total = int(subtotal) + int(tax) + int(shipping)
        except Exception:
            total = None

        parts = [f"Order **{oid}** is currently **{status}**."]
        if created:
            parts.append(f"It was placed on {created}.")
        if total is not None:
            parts.append(f"Estimated total: {_format_money(total)}.")

        addr = o.get("shipping_address")
        if addr:
            parts.append(f"Shipping to: {addr}")

        return " ".join(parts)
    
def change_order_shipping_address_agent(state: AgentState) -> AgentState:
    

    text = (state.get("input") or "").strip()
    email = (state.get("email") or "").strip().lower()

    # 1) Resolve order_id (prefer state, else parse from text)
    order_id = _resolve_order_id(state)
    if order_id:
        state["order_id"] = order_id  # keep it in state for logging / tools
    else:
        state["output"] = (
            "To change a shipping address, please provide your order ID "
            "along with your request (for example `ord_405 123 Street Rd, City, GA 30030`)."
        )
        return state


    if not order_id:
        state["output"] = (
            "To change a shipping address, please provide your order ID "
            "along with your request (for example `ord_405 123 Street Rd, City, GA 30030`)."
        )
        return state

    # 2) Look up the order
    try:
        row = db.get_order_by_id(order_id)
    except Exception as e:
        state["output"] = f"Sorry, I couldn't look up order `{order_id}` ({e})."
        return state

    if not row:
        state["output"] = f"I couldn’t find any order with ID `{order_id}`."
        return state

    try:
        order = dict(row)
    except Exception:
        order = row

    status = (order.get("status") or "").strip().lower()
    current_addr = order.get("shipping_address") or "(no shipping address on file)"

    # 3) Only allow change if not shipped/delivered/etc.
    BLOCKED_STATUSES = {"shipped", "delivered", "cancelled", "returned", "refunded"}
    if status in BLOCKED_STATUSES:
        state["output"] = (
            f"Order `{order_id}` is currently **{status}**, so the shipping "
            "address can no longer be changed.\n\n"
            f"Current shipping address on file:\n{current_addr}"
        )
        return state

    # 4) Try to detect a new address in THIS message
    updates_addr = None
    addr = ORDER_ADDRESS_REGEX.search(text)
    if addr:
        updates_addr = addr.group(0).strip()

    # 5) If we found a new address, update and confirm
    if updates_addr:
        try:
            db.set_order_shipping_address(order_id, updates_addr)
        except Exception as e:
            state["output"] = (
                f"Sorry, I couldn't update the shipping address for `{order_id}` ({e}). "
                "Please try again in a moment."
            )
            return state

        updated = db.get_order_by_id(order_id)
        try:
            updated_order = dict(updated)
        except Exception:
            updated_order = updated

        new_addr = updated_order.get("shipping_address") or updates_addr
        state["output"] = (
            f"The shipping address for order `{order_id}` has been updated.\n\n"
            f"New shipping address on file:\n{new_addr}"
        )
        state["last_action"] = "order_address_updated"
        return state
    
    # 6) No address in this message → entry / instructions
    state["output"] = (
        f"Order `{order_id}` is currently **{status or 'unknown'}**.\n"
        f"Current shipping address on file:\n{current_addr}\n\n"
        "You can update the shipping address for this order as long as it has not shipped yet.\n\n"
        "Please reply with the new shipping address in one line, for example:\n"
        "1600 Pennsylvania Ave, Washington, DC 20500"
    )
    return state

# ---------- Backward-compatible function ----------

def order_agent(state: AgentState) -> AgentState:
    """
    Simple wrapper so existing code that calls `order_agent({...})`
    keeps working.
    """
    if not isinstance(state, dict):
        state = {"input": str(state)}
    agent = OrderAgent()
    try:
        return agent.run(state)
    except Exception as e:
        state.setdefault("tool_calls", [])
        state.setdefault("tool_results", [])
        state["tool_results"].append(f"[FATAL] {e!r}")
        state["output"] = "Sorry—something went wrong while looking up your order."
        state["confidence"] = 0.2
        return state