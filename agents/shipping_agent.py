from __future__ import annotations
import re
import time
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
    confidence: float

# Context from memory_agent / supervisor
    context_summary: Optional[str]
    context_refs: Optional[List[str]]
    preface: Optional[str]
    memory: Optional[Dict[str, Any]]

# ---------- Tool Layer --------------
Tool = Callable[..., Any]

TOOL_REGISTRY: Dict[str, Dict[str, Any]] = { #Add more tools as needed
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

    "orders:update_address": {
        "fn": lambda order_id, new_address: db.update_order_address(order_id, new_address),
        "schema": {"order_id": "str (required)", "new_address": "str (required)"},
        "desc": "Update the shipping address for a specific order.",
    }


}

STATUS_NORMALIZATION = {
    "in transit": "In Transit",
    "processing": "Processing",
    "preparing": "Preparing",
    "packed": "Preparing",
    "label created": "Preparing",
    "shipped": "Shipped",
    "delivered": "Delivered",
    "unknown": "Unknown",
}

EMAIL_REGEX = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

class ShippingAgent:
    """
    A simple plan-act-observe AI agent for shipping status.
    - Extracts/recalls email
    - Plans which tool(s) to call
    - Calls tools with retries
    - Interprets & formats results
    - Writes a helpful response back to state
    """

    def __init__(self, max_retries: int = 2, backoff_s: float = 0.4):
        self.max_retries = max_retries
        self.backoff_s = backoff_s

    # --------- entrypoint ---------
    def run(self, state: AgentState) -> AgentState:
        self._ensure_lists(state)
        state["intent"] = state.get("intent") or "shipping status"

        # 1) Perception / memory
        self._extract_email(state)
        # Extract order ID from input
        order_id = None
        text = (state.get("input") or "").strip()
        match = re.search(r"ord_\d{3,7}", text, re.IGNORECASE)
        if match:
            order_id = match.group(0)
            state["order_id"] = order_id

        email = (state.get("email") or "").strip().lower()

        if not email and not order_id:
            state["output"] = (
                "To check your shipping status, please provide your order number (for example `ord_001`)."
            )
            state["confidence"] = 0.3
            return state

        # 2) Plan: figure out required tools
        plan = self._plan(state)

        # 3) Act: execute tools (with retries) and collect observations
        observations = []
        for step in plan:
            obs = self._call_tool_with_retries(step["tool"], step["args"], state)
            observations.append({"step": step, "obs": obs})

        # 4) Observe/Reason: turn observations into normalized shipping status
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

# ----------------- Planning -----------------
    def _plan(self, state: AgentState) -> List[Dict[str, Any]]:
        email = (state.get("email") or "").lower().strip()
        order_id = (state.get("order_id") or "").strip()
        address = None
        intent = (state.get("intent") or "").lower()
        text = (state.get("input") or "").lower()

        # Prefer order_id for shipping status if present
        if intent == "shipping status" and order_id:
            return [{"tool": "orders:get_by_id", "args": {"order_id": order_id}}]

        if intent == "shipping status" and email:
            return [{"tool": "orders:list_for_user", "args": {"email": email}}]

        if intent == "check order" and order_id:
            return [{"tool": "orders:get_by_id", "args": {"order_id": order_id}}]

        if intent == "update address" and email:
            return [{"tool": "orders:update_address", "args": {"order_id": order_id, "shipping_address": address}}]

    def _call_tool_with_retries(self, tool_name: str, args: Dict[str, Any], state: AgentState):
        if tool_name not in TOOL_REGISTRY:
            raise ValueError(f"Unknown tool: {tool_name}")
        fn: Tool = TOOL_REGISTRY[tool_name]["fn"]

        retries = int(state.get("max_retries", self.max_retries))
        attempt = 0
        while True:
            attempt += 1
            try:
                state["tool_calls"].append(f"{tool_name}({', '.join(f'{k}={v!r}' for k,v in args.items())})")
                result = fn(**args)
                # Try to coerce iterables of row-like objects to plain dicts for traceability
                safe_result = self._safe_preview(result)
                state["tool_results"].append(self._truncate_for_log(safe_result))
                return result
            except Exception as e:
                state["tool_results"].append(f"[ERROR] {tool_name}: {e!r}")
                if attempt > retries:
                    raise
                # basic backoff
                time.sleep(self.backoff_s * attempt)

    # ---------- helper functions ----------

    def _safe_preview(self, value: Any) -> Any:
        try:
            if isinstance(value, list):
                return [self._row_to_dict(r) for r in value[:5]]  # limit preview
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
        Normalize status and pick latest order. Returns a structured dict suitable for UI.
        Handles both single row and list results.
        """
        if not observations:
            return {"status": "Unknown", "order_id": None, "created_at": None, "confidence": 0.3}

        obs = observations[0]["obs"]
        # Handle single row or list
        if obs is None:
            preview = []
        elif isinstance(obs, list):
            preview = [self._row_to_dict(r) for r in obs]
        else:
            preview = [self._row_to_dict(obs)]

        if not preview:
            return {"status": "Unknown", "order_id": None, "created_at": None, "confidence": 0.6}

        latest = dict(preview[0])
        raw_status = (latest.get("status") or "Unknown").strip().lower()
        status = STATUS_NORMALIZATION.get(raw_status, raw_status.capitalize())

        # confidence heuristic: delivered/shipped → higher, unknown → lower
        conf_map = {
            "Delivered": 0.95,
            "Shipped": 0.9,
            "In Transit": 0.85,
            "Preparing": 0.75,
            "Processing": 0.7,
            "Unknown": 0.5,
        }
        confidence = conf_map.get(status, 0.7)

        return {
            "status": status,
            "order_id": latest.get("order_id"),
            "created_at": latest.get("created_at"),
            "confidence": confidence,
        }

    def _format_user_message(self, result: Dict[str, Any]) -> str:
        status = result["status"]
        order_id = result.get("order_id")
        created_at = result.get("created_at")

        # If status is unknown, check if user provided an order ID
        if status == "Unknown":
            input_order_id = order_id
            # Try to get from input if not found
            if not input_order_id:
                input_order_id = None
            if input_order_id:
                return f"I couldn’t find any order with ID `{input_order_id}`."
            return "I couldn’t find any recent orders associated with your email."

        parts = []
        if order_id:
            parts.append(f"Your most recent order **{order_id}** is **{status}**.")
        else:
            parts.append(f"Your most recent order is **{status}**.")
        if created_at:
            parts.append(f"(Placed on {created_at}.)")
        return " ".join(parts)

# ---------- Backward-compatible function ----------

def shipping_agent(state: AgentState) -> AgentState:

    if not isinstance(state, dict):
        state = {"input": str(state)}
    agent = ShippingAgent()
    try:
        return agent.run(state)
    except Exception as e:
        state.setdefault("tool_calls", [])
        state.setdefault("tool_results", [])
        state["tool_results"].append(f"[FATAL] {e!r}")
        state["output"] = "Sorry—something went wrong while checking your shipping status."
        state["confidence"] = 0.2
        return state


