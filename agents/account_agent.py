import db
import re
from typing import TypedDict, Optional, List, Dict, Any
from agents import message_agent as msg

ADDRESS_RE = re.compile(r"\b\d{1,6}\s+[A-Za-z0-9 .'-]+,\s*[A-Za-z .'-]+,\s*[A-Za-z]{2}\s+\d{5}(?:-\d{4})?\b", re.IGNORECASE,) #US address
PHONE_RE = re.compile(r"\b(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b") #Phone patterns
NAME_RE = re.compile(r"\b[A-Za-z'-]{2,25}(?:\s+[A-Za-z'-]{2,25}){1,3}\b") #Name patterns

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

    

def account_agent(state: AgentState) -> AgentState:
    """
    Router for account-related intents.
    Delegates to specialized functions based on intent.
    """
    print("[AGENT] account_agent selected")
    intent = (state.get("intent") or "").lower().strip()
    text = (state.get("input") or "").strip()
    
    # Route to appropriate handler
    if intent == "change password":
        return change_password_agent(state)
    elif intent == "change address":
        return change_address_agent(state)
    elif intent == "change phone number":
        return change_phone_number_agent(state)
    elif intent == "change full name":
        return change_full_name_agent(state)
    else:
        # Check if this looks like a phone number using regex
        if PHONE_RE.search(text):
            print("[AGENT] Detected phone number via regex, routing to change_phone_number_agent")
            return change_phone_number_agent(state)
        
        # Check if this looks like an address using regex
        if ADDRESS_RE.search(text):
            print("[AGENT] Detected address via regex, routing to change_address_agent")
            return change_address_agent(state)
            
        # Check if this looks like a name using regex (like address and phone)
        print(f"[DEBUG] Checking name detection for: '{text}'")
        name_match = NAME_RE.search(text)
        print(f"[DEBUG] NAME_RE.search('{text}') = {name_match}")
        if name_match:
            print(f"[DEBUG] Name match found: '{name_match.group(0)}'")
            # Exclude common command phrases that aren't actual names
            command_phrases = ["change name", "update name", "change full name", "update full name", "my name", "the name"]
            is_command = any(phrase in text.lower() for phrase in command_phrases)
            print(f"[DEBUG] Is command phrase: {is_command}")
            if not is_command:
                print("[AGENT] Detected name via regex, routing to change_full_name_agent")
                return change_full_name_agent(state)
            else:
                print("[DEBUG] Filtered out as command phrase")
        else:
            print("[DEBUG] No name match found")
        
        # General account help
        state["output"] = (
            "I can help with account settings like updating your address, profile, or changing your password. "
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
            "I can't help you change your password. Please open Settings → Security, enter a new password, and save."
        )
    else:
        state["output"] = (
            "To change your password, go to Settings → Security and use the Change Password form. "
            "For your privacy, I won't collect passwords in chat."
        )
    return state

def change_address_agent(state: AgentState) -> AgentState:

    print("[AGENT] change_address_agent selected")
    text = (state.get("input") or "").strip()
    email = (state.get("email") or "").strip().lower()

    # Must have an email
    if not email:
        state["output"] = (
            "You're currently using a guest session. Please log in or sign up to manage your address."
        )
        return state

    updates: Dict[str, str] = {}

    # --------------------------------------------------
    # Tries to detect a one-line address in message
    # --------------------------------------------------
    address = ADDRESS_RE.search(text)
    if address:
        addr = address.group(0)
        parts = [p.strip() for p in addr.split(",")]
        if len(parts) == 3:
            street = parts[0]
            city = parts[1]
            state_zip = parts[2].split()
            state_abbr = state_zip[0].upper() if len(state_zip) > 0 else ""
            zip_code = state_zip[1] if len(state_zip) > 1 else ""
        else:
            street = parts[0]
            city = parts[1]
            tail = " ".join(parts[2:])
            state_zip = tail.split()
            state_abbr = state_zip[0].upper() if len(state_zip) > 0 else ""
            zip_code = state_zip[1] if len(state_zip) > 1 else ""

        updates = {
            "address_line": street,
            "city": city,
            "state": state_abbr,
            "zip_code": zip_code,
            "country": "USA",
        }

    # --------------------------------------------------
    # Applies Updates
    # --------------------------------------------------
    if updates:
        _apply_address_updates(email, updates)
        user = db.get_user(email)
        pretty = _format_address(user)
        
        # Fetch phone number
        phone = db.get_user_phone_number(email)
        print(f"[DEBUG] change_address_agent sending notification: email={email}, phone={phone}, name={db.get_user_first_name(email)}, event_type=address_updated, details=Address updated to: {pretty}")
        # send notification to both email and phone
        notification_payload = {
            "email": email,
            "phone": phone,
            "name": db.get_user_first_name(email) or "",
            "event_type": "address_updated",
            "details": f"Address updated to: {pretty}"
        }
        print(f"[DEBUG] change_address_agent notification payload: {notification_payload}")
        notification_result = msg.message_agent(notification_payload)
        print(f"[DEBUG] change_address_agent notification result: {notification_result}")
        
        details = [
            "**Address Update Confirmation**",
            "",
            "Your address has been successfully updated.",
            "", 
            "**Current Address:**",
            "",
            f" • {pretty}"
        ]
        
        state["output"] = "\n".join(details)
        return state

    # --------------------------------------------------
    # No address found
    # --------------------------------------------------
    user = db.get_user(email)
    pretty = _format_address(user)

    if not re.search(r"\d", text):
        details = [
            "**Address Update**",
            "",
            "Sure — let's update your address.",
            "",
            f"**Current Address:** \n{pretty}",
            "",
            "**Please submit your new address in the following format:**",
            "",
            " • 1600 Pennsylvania Ave, Washington, DC 20500"
        ]
        
        state["output"] = "\n".join(details)
        return state

    details = [
        f"**Current Address:** {pretty}",
        "",
        "I couldn't detect a full address in your last message.",
        "",
        "**To update your address, please submit it in the following format:**",
        "",
        " • 1600 Pennsylvania Ave, Washington, DC 20500"
    ]
    
    state["output"] = "\n".join(details)
    return state


def change_phone_number_agent(state: "AgentState") -> "AgentState":
    """
    Handles phone number change requests.
    Flow: parse -> apply -> read back -> pretty-print.

    Accepts:
      • Plain numbers: "770-555-1234", "(770) 555 1234", "+1 (770) 555-1234"
    """
    print("[AGENT] change_phone_number_agent selected")
    text = (state.get("input") or "").strip()
    email = (state.get("email") or "").strip().lower()

    # Guard
    if not email or email == " ":
        state["output"] = (
            "You're currently using a guest session. Please log in or sign up to manage your phone number."
        )
        return state

    updates: Dict[str, str] = {}

    # --------------------------------------------------
    # pulls plain number (e.g. "770-555-1234" or "(770) 555 1234")
    # --------------------------------------------------
    phone_match = PHONE_RE.search(text)
    if phone_match:
        # Extract the three groups: area code, exchange, number
        area_code, exchange, number = phone_match.groups()
        raw_digits = f"{area_code}{exchange}{number}"
        # Ensure E.164 format for US numbers
        if len(raw_digits) == 10:
            updates["phone"] = f"+1{raw_digits}"
        else:
            updates["phone"] = raw_digits

    if updates:
        try:
            _apply_phone_updates(email, updates)  # uses set_user_phone(...)
            print(f"[PHONE] wrote phone={updates['phone']} for {email}")
            
            # Fetch phone number (just updated)
            phone = updates["phone"]
            print(f"[DEBUG] change_phone_number_agent sending notification: email={email}, phone={phone}, name={db.get_user_first_name(email)}, event_type=phone_updated, details=Phone number updated to: {_pretty_phone_number(phone)}")
            # send notification to both email and phone
            notification_payload = {
                "email": email,
                "phone": phone,
                "name": db.get_user_first_name(email) or "",
                "event_type": "phone_updated",
                "details": f"Phone number updated to: {_pretty_phone_number(phone)}"
            }
            print(f"[DEBUG] change_phone_number_agent notification payload: {notification_payload}")
            notification_result = msg.message_agent(notification_payload)
            print(f"[DEBUG] change_phone_number_agent notification result: {notification_result}")
            
        except Exception as e:
            state["output"] = f"Sorry, I couldn't save your phone number ({e}). Please try again."
            return state

        saved = db.get_user_phone_number(email)  # scalar string
        print(f"[PHONE] read back phone for {email}: {saved!r}")
        pretty = _pretty_phone_number(saved) if saved else "(none on file)"
        
        details = [
            "**Phone Number Update Confirmation**",
            "",
            "Your phone number has been successfully updated.",
            "",
            "**Current Phone Number:**",
            "",
            f" • {pretty}"
        ]
        
        state["output"] = "\n".join(details)
        return state

    current = db.get_user_phone_number(email)
    pretty = _pretty_phone_number(current) if current else "(none on file)"

    # If the message has no digits, treat this as an entry request
    if not re.search(r"\d", text):
        details = [
            "**Phone Number Update**",
            "",
            "Sure — let's update your phone number.",
            "",
            f"**Current Phone Number:** \n{pretty}",
            "",
            "**Please reply with your new number in one of these formats:**",
            "",
            " • 770-555-1234",
            "",
            " • (770) 555-1234",
            "",
            "You can also open Settings → Profile and edit your Phone Number there."
        ]
        
        state["output"] = "\n".join(details)
        return state

    # Fallback instructions
    details = [
        f"**Current Phone Number:** {pretty}",
        "",
        "I couldn't detect a valid phone number in your last message.",
        "",
        "**Please reply with your new number in one of these formats:**",
        "",
        " • 770-555-1234",
        "",
        " • (770) 555-1234",
        "",
        "You can also open Settings → Profile and edit your Phone Number there."
    ]
    
    state["output"] = "\n".join(details)
    return state


def change_full_name_agent(state: AgentState) -> AgentState:
    """
    Handles full name change requests.
    Can parse inline updates or guide to Settings > Profile.
    """
    print("[AGENT] change_full_name_agent selected")
    text = (state.get("input") or "").strip()
    email = (state.get("email") or "").strip().lower()
    
    # GUARD! must have an email (non-guest)
    if not email or email == " ":
        state["output"] = (
            "You're currently using a guest session. Please log in or sign up to manage your name."
        )
        return state
    
    updates: Dict[str, str] = {}

    # --------------------------------------------------
    # Tries to detect a name in message using regex (like address)
    # --------------------------------------------------
    print(f"[DEBUG] change_full_name_agent processing: '{text}'")
    # First check for explicit format: "first=Jane, last=Doe"
    if re.search(r"\b(first|last)\s*[:=]", text.lower()):
        print("[DEBUG] Using key=value parser")
        updates = _parse_full_name_updates(text)  # Use existing key=value parser
    # Then check for simple name format using regex like address and phone
    else:
        print("[DEBUG] Using regex name detection")
        # Exclude common command phrases that aren't actual names
        command_phrases = ["change name", "update name", "change full name", "update full name", "my name", "the name"]
        is_command = any(phrase in text.lower() for phrase in command_phrases)
        print(f"[DEBUG] Is command phrase: {is_command}")
        if not is_command:
            name_match = NAME_RE.search(text)
            print(f"[DEBUG] NAME_RE.search('{text}') = {name_match}")
            if name_match:
                name = name_match.group(0)
                print(f"[DEBUG] Matched name: '{name}'")
                words = name.split()
                print(f"[DEBUG] Words: {words}")
                if len(words) == 2:
                    updates = {"first_name": words[0], "last_name": words[1]}
                elif len(words) == 1:
                    updates = {"first_name": words[0]}
                elif len(words) >= 3:
                    updates = {"first_name": words[0], "last_name": " ".join(words[1:])}
                print(f"[DEBUG] Updates: {updates}")
    
    if updates:
        _apply_full_name_updates(email, updates)
        user = db.get_user(email)
        pretty = _format_full_name(user)
        
        # Fetch phone number
        phone = db.get_user_phone_number(email)
        print(f"[DEBUG] change_full_name_agent sending notification: email={email}, phone={phone}, name={db.get_user_first_name(email)}, event_type=name_updated, details=Name updated to: {pretty}")
        # send notification to both email and phone
        notification_payload = {
            "email": email,
            "phone": phone,
            "name": db.get_user_first_name(email) or "",
            "event_type": "name_updated",
            "details": f"Name updated to: {pretty}"
        }
        print(f"[DEBUG] change_full_name_agent notification payload: {notification_payload}")
        notification_result = msg.message_agent(notification_payload)
        print(f"[DEBUG] change_full_name_agent notification result: {notification_result}")
        
        details = [
            "**Name Update Confirmation**",
            "",
            "Your full name has been successfully updated.",
            "",
            "**Current Name:**",
            "",
            f" • {pretty}"
        ]
        
        state["output"] = "\n".join(details)
        return state
    
    # show current name and instructions
    user = db.get_user(email)
    pretty = _format_full_name(user)
    
    details = [
        "**Name Update**",
        "",
        "Sure — let's update your full name.",
        "",
        f"**Current Name:** \n{pretty}",
        "",
        "**Please reply with your new name in one of these formats:**",
        "",
        " • Jane Doe",
        "",
        " • first=Jane, last=Doe",
        "",
        "You can also open Settings → Profile and edit your full name section there."
    ]
    
    state["output"] = "\n".join(details)
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
    return ", ".join(non_empty)

# Put near your other KEY maps
_PHONE_KEYS = {
    "phone": "phone",
    "phone number": "phone",
    "phone_number": "phone",
    "tel": "phone",
    "telephone": "phone",
    "mobile": "phone",
    "cell": "phone",
    "cell phone": "phone",
    "cellphone": "phone",
}

def _parse_phone_updates(text: str) -> Dict[str, str]:
    """
    Parse phone updates from free-form text.
    Mirrors _parse_address_updates: key[:=]value pairs + synonym map.
    Normalizes to last 10 digits. Returns {'phone': '##########'} or {}.
    """
    if not text:
        return {}
    lowered = text.lower()

    if not any(k in lowered for k in _PHONE_KEYS.keys()):
        return {}

    pattern = re.compile(r"\b([a-z_ ]{3,20})\s*[:=]\s*([^,\n;]+)")
    found = pattern.findall(text)

    updates: Dict[str, str] = {}
    for raw_key, raw_val in found:
        key = raw_key.strip().lower()
        norm = _PHONE_KEYS.get(key)
        if not norm:
            continue

        val = re.sub(r"\s+", " ", raw_val.strip())

        # normalized: keep last 10 digits (drop +1, spaces, dashes, ext)
        digits = re.sub(r"\D", "", val)
        if len(digits) >= 10:
            updates[norm] = digits[-10:]
            break  # only need one
    return updates


def _apply_phone_updates(email: str, updates: Dict[str, str]) -> None:
    """Apply phone field updates to the user's record."""
    if not updates:
        return
    if "phone" in updates:
        db.set_user_phone(email, updates["phone"])

def _pretty_phone_number(phone_number: Any) -> str:
    """
    Render a phone-like value as (XXX) XXX-XXXX.
    - Accepts str/int/bytes/sqlite3.Row/etc.
    - Keeps the LAST 10 digits (drops country code / extension).
    - Falls back to the original string if < 10 digits found.
    """
    s = _safe_str(phone_number)
    if not s:
        return ""

    # Normalize various unicode spaces/dashes just in case
    s = s.replace("\u00A0", " ").replace("\u2011", "-").strip()

    # Strip everything but digits
    digits = re.sub(r"\D", "", s)

    # If we have at least 10, use the last 10 (handles +1, ext, etc.)
    if len(digits) >= 10:
        d = digits[-10:]
        return f"({d[:3]}) {d[3:6]}-{d[6:]}"

    # Not enough digits — show original so the user sees *something*
    return s


_NAME_KEYS = {
    "first": "first_name",
    "first name": "first_name", 
    "last": "last_name",
    "last name": "last_name",
    "name": "name",
}

def _parse_full_name_updates(text: str) -> Dict[str, str]:
    """
    Parse name updates from free-form text.
    Accepts two formats:
    1. key=value format: "first=Jane, last=Doe" 
    2. Plain name format: "Jane Doe" or "Jane Smith"
    """
    if not text:
        return {}
    
    text = text.strip()
    lowered = text.lower()
    
    # format 1: key=value format
    if any(k in lowered for k in _NAME_KEYS.keys()):
        # accept patterns "key=value" or "key: value" with optional commas
        pattern = re.compile(r"\b([a-z_ ]{3,12})\s*[:=]\s*([^,\n]+)")
        found = pattern.findall(text)
        updates: Dict[str, str] = {}
        for raw_key, raw_val in found:
            key = raw_key.strip().lower()
            norm = _NAME_KEYS.get(key)
            if not norm:
                continue
            val = raw_val.strip()
            # collapse whitespace
            val = re.sub(r"\s+", " ", val)
            updates[norm] = val
        return updates
    
    # format 2: Plain name format "FirstName LastName" (NEW FORMAT)
    if _looks_like_name(text):
        words = text.split()
        if len(words) == 2:
            return {
                "first_name": words[0],
                "last_name": words[1]
            }
        elif len(words) == 1:
            # just First name
            return {"first_name": words[0]}
        elif len(words) >= 3:
            # First name is first word, Last name is everything else
            return {
                "first_name": words[0],
                "last_name": " ".join(words[1:])
            }
    
    return {}

def _apply_full_name_updates(email: str, updates: Dict[str, str]) -> None:
    """Apply name field updates to the user's record."""
    if not updates:
        return
    if "first_name" in updates:
        db.set_user_first_name(email, updates["first_name"])
    if "last_name" in updates:
        db.set_user_last_name(email, updates["last_name"])
   

def _format_full_name(user_row) -> str:
    """Format the user's name nicely for display."""
    def _row_get(row, key):
        try:
            if row is None:
                return ""
            return row[key] if key in row.keys() else ""
        except Exception:
            return ""

    first_name = _row_get(user_row, "first_name")
    last_name = _row_get(user_row, "last_name")
    
    parts = [first_name, last_name]
    non_empty = [p for p in parts if (p or "").strip()]
    if not non_empty:
        return "You don't have your name on file yet."
    return " ".join(non_empty)  # Use space instead of comma for names

def _looks_like_name(text: str) -> bool:
    """
    Check if text looks like a person's name.
    More permissive pattern matching similar to address detection.
    """
    if not text or not text.strip():
        return False
    
    text = text.strip()
    
    # Skip obvious non-names
    if re.search(r"\d", text):  # Contains numbers
        return False
    if "@" in text:  # Email
        return False
    if any(char in text for char in "=:,;()[]{}|\\/<>?!#$%^&*"):  # Special chars
        return False
    
    # Simple pattern: 1-4 words, each word is letters/apostrophes/hyphens
    # More permissive than before - allow single names, mixed case, etc.
    words = text.split()
    
    # Should be 1-4 words (allow single names like "Madonna")
    if len(words) < 1 or len(words) > 4:
        return False
    
    # Each word should be reasonable for a name
    for word in words:
        # Allow letters, apostrophes, hyphens, and mixed case
        if not re.match(r"^[A-Za-z'-]+$", word):
            return False
        # More permissive length (1-25 characters)
        if len(word) < 1 or len(word) > 25:
            return False
    
    # If we get here, it looks like a name
    return True



def _safe_str(x: Any) -> str:
    if x is None:
        return ""
    if isinstance(x, str):
        return x
    if isinstance(x, bytes):
        try:
            return x.decode("utf-8", "ignore")
        except Exception:
            return ""
    if isinstance(x, memoryview):
        try:
            return bytes(x).decode("utf-8", "ignore")
        except Exception:
            return ""
    # sqlite3.Row or other mapping → stringify only as last resort
    try:
        if hasattr(x, "keys"):
            # If it looks like a row, try common field names
            for k in ("phone_number", "phone", "tel"):
                if k in x.keys():
                    v = x[k]
                    return v if isinstance(v, str) else str(v)
    except Exception:
        pass
    return str(x)