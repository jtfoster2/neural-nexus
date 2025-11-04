import db
import re
from typing import TypedDict, Optional, List, Dict

class AgentState(TypedDict):
    input: str
    email: Optional[str]
    intent: Optional[str]
    reasoning: Optional[str]
    tool_calls: List[str]
    tool_results: List[str]
    output: Optional[str]

def account_agent(state: AgentState) -> AgentState:
    """
    Router for account-related intents.
    Delegates to specialized functions based on intent.
    """
    print("[AGENT] account_agent selected")
    intent = (state.get("intent") or "").lower().strip()
    
    # Route to appropriate handler
    if intent == "change password":
        return change_password_agent(state)
    elif intent == "change address":
        return change_address_agent(state)
    else:
        # General account help
        state["output"] = (
            "I can help with account settings like updating your address or changing your password. "
            "Tell me what you'd like to update."
        )
        return state

def change_password_agent(state: AgentState) -> AgentState:
    """
    Handles password change requests.
    For security, we guide users to Settings instead of collecting passwords via chat.
    """
    print("[AGENT] change_password_agent selected")
    email = (state.get("email") or "").strip().lower()
    
    # GUARD! must have an email (non-guest)
    if not email or email == " ":
        state["output"] = (
            "You're currently using a guest session. Please log in or sign up to manage your password."
        )
        return state
    
    user = db.get_user(email)
    if (not user) or (not (user["password_hash"] or "")):
        state["output"] = (
            "I can help you set a password. Open Settings → Security, enter a new password, and save."
        )
    else:
        state["output"] = (
            "To change your password, go to Settings → Security and use the Change Password form. "
            "For your privacy, I won't collect passwords in chat."
        )
    return state

def change_address_agent(state: AgentState) -> AgentState:
    """
    Handles address change requests.
    Can parse inline updates or guide to Settings > Profile.
    """
    print("[AGENT] change_address_agent selected")
    text = (state.get("input") or "").strip()
    email = (state.get("email") or "").strip().lower()
    
    # GUARD! must have an email (non-guest)
    if not email or email == " ":
        state["output"] = (
            "You're currently using a guest session. Please log in or sign up to manage your address."
        )
        return state
    
    # try to parse address fields from the message
    updates = _parse_address_updates(text)
    if updates:
        _apply_address_updates(email, updates)
        user = db.get_user(email)
        pretty = _format_address(user)
        state["output"] = (
            "Your address has been updated. Current address on file:\n" + pretty
        )
        return state
    
    # show current address and instructions
    user = db.get_user(email)
    pretty = _format_address(user)
    instructions = (
        "Sure — you can update your address here by replying in one line, for example:\n"
        "address line=123 Main St, city=Atlanta, state=GA, zip=30318, country=USA\n\n"
        "Or open Settings → Profile and edit your Address section there."
    )
    state["output"] = (pretty + "\n\n" + instructions).strip()
    return state



# ----------------------
# Helper functions
# ----------------------

_ADDR_KEYS = {
    "address line": "address_line",
    "address_line": "address_line",
    "address": "address_line",
    "city": "city",
    "state": "state",
    "zip": "zip_code",
    "zipcode": "zip_code",
    "zip_code": "zip_code",
    "postal": "zip_code",
    "postal code": "zip_code",
    "country": "country",
}

def _parse_address_updates(text: str) -> Dict[str, str]:
    """
    Parse address updates from free-form text.
    Accepts patterns like: key=value or key: value
    Example: "address line=123 Main St, city=Atlanta, state=GA, zip=30318, country=USA"
    """
    if not text:
        return {}
    lowered = text.lower()
    # if none of the address are present, skip parsing
    if not any(k in lowered for k in _ADDR_KEYS.keys()):
        return {}

    # accept patterns "key=value" or "key: value" with optional commas
    pattern = re.compile(r"\b([a-z_ ]{3,12})\s*[:=]\s*([^,\n]+)")
    found = pattern.findall(text)
    updates: Dict[str, str] = {}
    for raw_key, raw_val in found:
        key = raw_key.strip().lower()
        norm = _ADDR_KEYS.get(key)
        if not norm:
            continue
        val = raw_val.strip()
        # collapse whitespace
        val = re.sub(r"\s+", " ", val)
        updates[norm] = val
    return updates

def _apply_address_updates(email: str, updates: Dict[str, str]) -> None:
    """Apply address field updates to the user's record."""
    if not updates:
        return
    if "address_line" in updates:
        db.set_user_address_line(email, updates["address_line"])
    if "city" in updates:
        db.set_user_city(email, updates["city"])
    if "state" in updates:
        db.set_user_state(email, updates["state"])
    if "zip_code" in updates:
        db.set_user_zip_code(email, updates["zip_code"])
    if "country" in updates:
        db.set_user_country(email, updates["country"])

def _format_address(user_row) -> str:
    """Format the user's address nicely for display."""
    def _row_get(row, key):
        try:
            if row is None:
                return ""
            return row[key] if key in row.keys() else ""
        except Exception:
            return ""

    parts = [
        _row_get(user_row, "address_line"),
        _row_get(user_row, "city"),
        _row_get(user_row, "state"),
        _row_get(user_row, "zip_code"),
        _row_get(user_row, "country"),
    ]
    non_empty = [p for p in parts if (p or "").strip()]
    if not non_empty:
        return "You don't have an address on file yet."
    # format nicely with commas
    return ", ".join(non_empty)