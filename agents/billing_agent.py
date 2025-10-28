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

# ---------- Tool Layer --------------
Tool = Callable[..., Any]

TOOL_REGISTRY: Dict[str, Dict[str, Any]] = { #Add more tools as needed
    # Placeholder tool for listing payments for a user, if needed in future
    # "payments:list_for_user": {
    #     "fn": lambda email: db.list_payments_for_user(email),
    #     "schema": {"email": "str (required)"},
    #     "desc": "Return all payments for a given user email, newest first.",
    # },

    "payments:get_by_id": {
        "fn": lambda email, payment_id: db.get_payment_by_id(email, payment_id),
        "schema": {"email": "str (required)", "payment_id": "str (required)"},
        "desc": "Return details for a specific payment by its ID.",
    }


}

STATUS_NORMALIZATION = {
    "successful": "Successful",
    "pending": "Pending",
    "unknown": "Unknown",
}

EMAIL_REGEX = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

class BillingAgent:
    """
    A simple plan-act-observe AI agent for payment status.
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
        state["intent"] = state.get("intent") or "payment status"

        # 1) Perception / memory
        self._extract_email(state)

        email = (state.get("email") or "").strip().lower()
        if not email:
            state["output"] = "Please provide your email so I can check your payment status."
            state["confidence"] = 0.4
            return state

        # 2) Plan: figure out required tools
        plan = self._plan(state)

        # 3) Act: execute tools (with retries) and collect observations
        observations = []
        for step in plan:
            obs = self._call_tool_with_retries(step["tool"], step["args"], state)
            observations.append({"step": step, "obs": obs})

        # 4) Observe/Reason: turn observations into normalized payment status
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
        
        # expand as needed
        email = (state.get("email") or "").lower().strip()
        payment_id = None
        intent = (state.get("intent") or "").lower()
        text = (state.get("input") or "").lower()
        # Placeholder code for possible future mass payment lookup
        # if intent == "payment status" and email:
        #     return [{"tool": "payments:list_for_user", "args": {"email": email}}]

        if intent == "check payment" and payment_id:
            return [{"tool": "payments:get_by_id", "args": {"payment_id": payment_id}}]

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
        Normalize status and pick latest payment. Returns a structured dict suitable for UI.
        """
        if not observations:
            return {"status": "Unknown", "payment_id": None, "created_at": None, "confidence": 0.3}

        # We expect a single observation from payments:get_by_id
        payments = observations[0]["obs"] or []
        preview = [self._row_to_dict(r) for r in payments]
        if not preview:
            return {"status": "Unknown", "payment_id": None, "created_at": None, "confidence": 0.6}

        latest = dict(preview[0])
        raw_status = (latest.get("status") or "Unknown").strip().lower()
        status = STATUS_NORMALIZATION.get(raw_status, raw_status.capitalize())

        # confidence heuristic: successful>pending → higher, unknown → lower
        conf_map = {
            "successful": 0.95,
            "pending": 0.9,
            "Unknown": 0.5,
        }
        confidence = conf_map.get(status, 0.7)

        return {
            "status": status,
            "payment_id": latest.get("payment_id"),
            "created_at": latest.get("created_at"),
            "confidence": confidence,
        }
    #Need to add version of this method for mass payment lookup
    def _format_user_message(self, result: Dict[str, Any]) -> str:
        status = result["status"]
        payment_id = result.get("payment_id")
        created_at = result.get("created_at")

        if status == "Unknown":
            return "I couldn’t find any payments associated with this email and payment id."

        parts = []
        if payment_id:
            parts.append(f"The payment status of **{payment_id}** is **{status}**.")
        else:
            parts.append(f"The payment status is **{status}**.")
        if created_at:
            parts.append(f"(Processed at {created_at}.)")
        return " ".join(parts)

# ---------- Backward-compatible function ----------
# def billing_agent(state: AgentState) -> AgentState:
#     print("[AGENT] billing_agent selected")
#     user = db.get_user(state.get("email") or "")
#     state["output"] = (
#         "Routing to specialized agent for **Billing**."
#         if user else
#         "Please provide your email to look into billing."
#     )
#     return state

