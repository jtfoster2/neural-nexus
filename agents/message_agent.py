from __future__ import annotations
import os
import re
import time
from typing import TypedDict, Optional, List, Dict, Any, Callable
import db
import sendgrid
from dotenv import load_dotenv
from sendgrid_tool import send_email
from vonage import Auth, Vonage
from vonage_sms import SmsMessage, SmsResponse

# --- Load .env ---
load_dotenv()

##PLEASE NOTE THIS METHOD (send_sms_vonage) ONLY WORKS FOR Version 4
def send_sms_vonage(to_phone: str, message: str):
    print(f"[DEBUG] send_sms_vonage called with to_phone={to_phone}, message={message}")

    VONAGE_API_KEY = os.environ.get("VONAGE_API_KEY")
    VONAGE_API_SECRET = os.environ.get("VONAGE_API_SECRET")
    SMS_SENDER_ID = os.environ.get("VONAGE_SMS_SENDER_ID") or os.environ.get("VONAGE_SMS_FROM")

    if not VONAGE_API_KEY or not VONAGE_API_SECRET or not SMS_SENDER_ID:
        raise ValueError("Missing Vonage API credentials or sender ID in environment variables")

    # create Vonage client with Auth
    client = Vonage(Auth(api_key=VONAGE_API_KEY, api_secret=VONAGE_API_SECRET))

    # build SmsMessage model
    sms_message = SmsMessage(
        to=to_phone,
        from_=SMS_SENDER_ID,
        text=message,
    )

    try:
        # send via client.sms.send(...)
        response: SmsResponse = client.sms.send(sms_message)
        # SmsResponse is a Pydantic model
        print("Vonage SMS: Message sent, response:", response) #DEBUGGING
        return {
            "success": True,
            "message_id": getattr(response, "message_id", None),
            "to": to_phone,
            "error_text": None,
            "status": "0",
        }
    except Exception as e:
        print(f"[ERROR] send_sms_vonage exception: {e}") #DEBUGGING
        return {
            "success": False,
            "error_text": str(e),
            "to": to_phone,
            "message_id": None,
            "status": "exception",
        }


class AgentState(TypedDict, total=False):
    input: str
    intent: Optional[str]
    reasoning: Optional[str]
    tool_calls: List[str]
    tool_results: List[str]
    output: Optional[str]
    confidence: float

    # Messaging-specific fields
    email: Optional[str]        
    name: Optional[str]          
    order_id: Optional[str]      
    event_type: Optional[str]    
    details: Optional[str]       
    subject: Optional[str]       
    body: Optional[str]          
    cc: Optional[List[str]]
    bcc: Optional[List[str]]

    # Account-change optional fields
    old_email: Optional[str]
    new_email: Optional[str]
    old_address: Optional[str]
    new_address: Optional[str]

    # Context from memory_agent / supervisor
    context_summary: Optional[str]
    context_refs: Optional[List[str]]
    preface: Optional[str]
    memory: Optional[Dict[str, Any]]

def send_email(to_email: str, subject: str, value: str):
    print(f"[DEBUG] send_email called with to_email={to_email}, subject={subject}, value={value}")
    sendgrid_key = os.environ.get("SENDGRID_API_KEY") # Your SendGrid API key
    verified_sender = os.environ.get("SENDGRID_VERIFIED_SENDER") # Your verified sender email
    if not sendgrid_key:
        raise ValueError("Missing SENDGRID_API_KEY environment variable")

    send_grid = sendgrid.SendGridAPIClient(api_key=sendgrid_key)

    # Build JSON payload
    data = {
        "personalizations": [
            {"to": [{"email": to_email}]}
        ],
        "from": {"email": verified_sender},  
        "subject": subject,
        "content": [
            {"type": "text/plain", "value": value}
        ]
    }

    # Perform the API request
    try:
        print(f"[DEBUG] send_email sending with data: {data}")
        response = send_grid.client.mail.send.post(request_body=data)
        print(f"[DEBUG] send_email response: status_code={response.status_code}, body={response.body}")
    except Exception as e:
        print(f"[ERROR] send_email exception: {e}")
        raise
    # Return simplified result for agent logging
    return {
        "success": response.status_code in (200, 202),
        "status_code": response.status_code,
        "body": response.body.decode() if response.body else None,
        "message_id": response.headers.get("X-Message-Id")
    }


# ------------- Tool Layer -------------
Tool = Callable[..., Any]

TOOL_REGISTRY = {
    "notify:send_email": {
        "fn": lambda to, subject, body, cc=None, bcc=None: send_email(
            to_email=to,
            subject=subject,
            value=body,
        ),
        "schema": {
            "to": "str (required, email)",
            "subject": "str (required)",
            "body": "str (required)",
            "cc": "list[str] (optional)",
            "bcc": "list[str] (optional)",
        },
        "desc": "Send an email via SendGrid with optional CC/BCC."
    },
    "notify:send_sms": {
        "fn": lambda to, body: send_sms_vonage(
            to_phone=to,
            message=body
        ),
        "schema": {
            "to": "str (required, phone number)",
            "body": "str (required)",
        },
        "desc": "Send an SMS via Vonage."
    }
}

EMAIL_REGEX = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


class MessageAgent:

    """
    A simple plan-act-observe AI agent for messaging/email delivery.
    - It formats a message (subject/body) from state, calls the email tool with retries.
    - Plans which tool(s) to call
    - Calls tools with retries
    - Returns a summary in state['output']
    """
    

    def __init__(self, max_retries: int = 2, backoff_s: float = 0.5):
        self.max_retries = max_retries
        self.backoff_s = backoff_s

    # --------- entrypoint ---------
    def run(self, state: AgentState) -> AgentState:
        self._ensure_lists(state)
        state["intent"] = state.get("intent") or "send message"

        # Perception: ensures we have a recipient email if not already submitted
        self.extract_email(state)
        self.extract_phone(state)

        # Build message (allows user overrides on subject/body)
        if not state.get("subject") or not state.get("body"):
            subj, body = self._build_subject_body(
                email=state.get("email"),
                order_id=state.get("order_id"),
                event_type=state.get("event_type"),
                details=state.get("details"),
                name=state.get("name"),
            )
            state["subject"] = state.get("subject") or subj
            state["body"] = state.get("body") or body

        # Validate required fields
        problems = self._validate(state)
        print(f"[DEBUG] MessageAgent validation problems: {problems}")
        print(f"[DEBUG] MessageAgent state: email={state.get('email')}, phone={state.get('phone')}, subject={state.get('subject')}, body={state.get('body')}")
        if problems:
            state["output"] = "I can’t send the message yet:\n- " + "\n- ".join(problems)
            state["confidence"] = 0.3
            return state

        # Plan
        plan = self._plan(state)
        print(f"[DEBUG] MessageAgent plan steps: {plan}")

        # Act
        observations = []
        for step in plan:
            print(f"[DEBUG] Executing tool: {step['tool']} with args: {step['args']}")
            obs = self._call_tool_with_retries(step["tool"], step["args"], state)
            print(f"[DEBUG] Tool result: {obs}")
            observations.append({"step": step, "obs": obs})

        # Observe/Reason
        result = self._interpret(observations, state)
        print(f"[DEBUG] MessageAgent final result: {result}")

        # Communicate
        state["output"] = self._format_user_message(result, state)
        state["confidence"] = result.get("confidence", 0.85)
        return state

    def extract_phone(self, state: AgentState) -> None:
        if state.get("phone"):
            return
        text = (state.get("input") or "").strip()
        m = re.search(r"\+?[1-9]\d{1,14}", text)
        if m:
            state["phone"] = m.group(0)

    # ------------- internals -------------

    def _ensure_lists(self, state: AgentState) -> None:
        state.setdefault("tool_calls", [])
        state.setdefault("tool_results", [])

    def extract_email(self, state: AgentState) -> None:
        if state.get("email"):
            return
        text = (state.get("input") or "").strip()
        m = EMAIL_REGEX.search(text)
        if m:
            state["email"] = m.group(0).lower()

    def _validate(self, state: AgentState) -> List[str]:
        issues = []
        email_valid = state.get("email") and EMAIL_REGEX.fullmatch(state["email"])
        phone_valid = state.get("phone") and re.fullmatch(r"\+?[1-9]\d{1,14}", state["phone"])
        if not (email_valid or phone_valid):
            issues.append("Missing or invalid recipient: need at least one valid email or phone number.")
        if state.get("email") and not email_valid:
            issues.append("Invalid recipient email.")
        if state.get("phone") and not phone_valid:
            issues.append("Invalid recipient phone number.")
        if not state.get("body"):
            issues.append("Missing body.")
        return issues

    # ----------------- Planning -----------------
    def _plan(self, state: AgentState) -> List[Dict[str, Any]]:
        steps = []
        if state.get("phone"):
            steps.append({
                "tool": "notify:send_sms",
                "args": {
                    "to": state["phone"],
                    "body": state["body"],
                },
            })
        if state.get("email"):
            steps.append({
                "tool": "notify:send_email",
                "args": {
                    "to": state["email"],
                    "subject": state["subject"],
                    "body": state["body"],
                    "cc": state.get("cc") or [],
                    "bcc": state.get("bcc") or [],
                },
            })
        return steps

    def _call_tool_with_retries(self, tool_name: str, args: Dict[str, Any], state: AgentState):
        if tool_name not in TOOL_REGISTRY:
            raise ValueError(f"Unknown tool: {tool_name}")
        fn: Tool = TOOL_REGISTRY[tool_name]["fn"]

        retries = self.max_retries
        attempt = 0
        while True:
            attempt += 1
            try:
                state["tool_calls"].append(f"{tool_name}({', '.join(f'{k}={v!r}' for k,v in args.items())})")
                result = fn(**args)  # send_email.invoke({...})
                # Keep a short preview in logs
                state["tool_results"].append(self._truncate_for_log({"ok": True, "result": result}))
                return result
            except Exception as e:
                state["tool_results"].append(f"[ERROR] {tool_name}: {e!r}")
                if attempt > retries:
                    raise
                time.sleep(self.backoff_s * attempt)

    def _truncate_for_log(self, obj: Any, limit: int = 300) -> str:
        s = repr(obj)
        return s if len(s) <= limit else s[:limit] + "…"

    # --------- message templating ---------

    @staticmethod
    def _sig(name: Optional[str]) -> str:
        return (
            "\n"
            "— Capgemini Customer Support\n"
            "If you didn’t request this change, reply immediately or contact support."
        )

    @staticmethod
    def _mask_email(e: Optional[str]) -> str:
        if not e:
            return ""
        try:
            user, domain = e.split("@", 1)
            masked_user = (user[0] + "…" + user[-1]) if len(user) > 2 else (user[0] + "…" if user else "…")
            return f"{masked_user}@{domain}"
        except Exception:
            return e

    def _build_subject_body(
        self,
        email: Optional[str],
        order_id: Optional[str],
        event_type: Optional[str],
        details: Optional[str],
        name: Optional[str],
    ) -> tuple[str, str]:
        et = (event_type or "status_update").strip().lower()
        recipient = name or "there"

        # ---- Account: email changed ----
        if et in {"account_email_changed", "email_changed"}:
            subject = "Your account email was changed"
            body = (
                f"Hi {recipient},\n\n"
                "We want to let you know your account email was updated.\n\n"
                "Summary of change:\n"
                f"- Previous email: { self._mask_email(getattr(self, 'old_email', None) or '') }\n"
                f"- New email:      { self._mask_email(getattr(self, 'new_email', email) or '') }\n"
                f"{(details + '\\n') if details else ''}"
                "If you made this change, no action is needed.\n"
                "If you didn’t request this, please reply to this email immediately.\n"
                f"{ self._sig(name) }"
            )
            return subject, body

        # ---- Account: password changed ----
        if et in {"account_password_changed", "password_changed"}:
            subject = "Your password was changed"
            body = (
                f"Hi {recipient},\n\n"
                "Your account password was recently changed.\n\n"
                "Security tips:\n"
                "- If this wasn’t you, reset your password right away.\n"
                "- Enable two-factor authentication in your account settings.\n"
                "- Review recent sign-ins for anything unfamiliar.\n\n"
                f"{(details + '\\n\\n') if details else ''}"
                "Need a hand? Reply to this email and we’ll help secure your account.\n"
                f"{ self._sig(name) }"
            )
            return subject, body

        # ---- Account: address changed ----
        if et in {"account_address_changed", "address_changed"}:
            subject = "Your account address was updated"
            old_addr = getattr(self, "old_address", None)
            new_addr = getattr(self, "new_address", None)
            body = (
                f"Hi {recipient},\n\n"
                "Your account mailing/shipping address was updated.\n\n"
                "Summary of change:\n"
                f"- Previous address: {old_addr or '(not provided)'}\n"
                f"- New address:      {new_addr or '(not provided)'}\n"
                f"{(details + '\\n') if details else ''}"
                "If you didn’t request this change, reply to this email so we can investigate.\n"
                f"{ self._sig(name) }"
            )
            return subject, body
        
        # ---- Account: changed ----
        if et in {"account_updated", "account_changed"}:
            subject = "Your account has been updated"
            body = (
                f"Hi {recipient},\n\n"
                "Your account details have been updated.\n\n"
                "Summary of change:\n"
                f"{(details + '\\n') if details else ''}"
                "If you didn’t request this change, reply to this email so we can investigate.\n"
                f"{ self._sig(name) }"
            )
            return subject, body

        # ---- Common order/shipping events ----
        if et in {"shipped", "delivered", "in_transit"}:
            pretty = {
                "shipped": "Your order has shipped",
                "delivered": "Your order was delivered",
                "in_transit": "Your order is in transit",
            }[et]
            subject = f"{pretty}"
            prefix = f"**Order {order_id}** " if order_id else "Your order "
            body = (
                f"Hi {recipient},\n\n"
                f"{prefix}{pretty.lower()}.\n"
                f"{(details + '\\n') if details else ''}"
                f"{ self._sig(name) }"
            )
            return subject, body

        if et in {"action_required"}:
            subject = "Action required for your order"
            body = (
                f"Hi {recipient},\n\n"
                "We need a quick confirmation to continue processing your order.\n"
                f"{(details + '\\n') if details else ''}"
                f"{ self._sig(name) }"
            )
            return subject, body

        # ---- Final fallback (status_update / unknown) ----
        subject = "Update from Customer Support"
        body = (
            f"Hi {recipient},\n\n"
            f"{details or 'We wanted to let you know we processed your request.'}\n"
            f"{ self._sig(name) }"
        )
        return subject, body


    # --------- interpretation & UX ---------

    def _interpret(self, observations: List[Dict[str, Any]], state: AgentState) -> Dict[str, Any]:
        """Summarize tool outcome into a compact result."""
        if not observations:
            return {"sent": False, "confidence": 0.4}

        results = []
        for obs in observations:
            raw = obs["obs"]
            sent_ok = True
            message_id = None
            to = None
            try:
                if isinstance(raw, dict):
                    sent_ok = bool(raw.get("success", True))
                    message_id = raw.get("message_id") or raw.get("id")
                    to = raw.get("to")
                elif isinstance(raw, (list, tuple)) and raw:
                    message_id = getattr(raw[0], "message_id", None) if hasattr(raw[0], "message_id") else None
                    sent_ok = True
                else:
                    sent_ok = True
            except Exception:
                sent_ok = True
            results.append({"sent": sent_ok, "message_id": message_id, "to": to, "tool": obs["step"]["tool"]})

        overall_sent = all(r["sent"] for r in results)
        return {"sent": overall_sent, "results": results, "confidence": 0.9 if overall_sent else 0.5}

    def _format_user_message(self, result: Dict[str, Any], state: AgentState) -> str:
        if not result.get("sent"):
            return "I tried to send the message but it may not have gone through. Please check logs."
        outputs = []
        for r in result.get("results", []):
            mid = r.get("message_id")
            to = r.get("to") or state.get("phone") if r["tool"] == "notify:send_sms" else state.get("email")
            if r["tool"] == "notify:send_sms":
                if mid:
                    outputs.append(f"SMS sent to **{to}** (message id: `{mid}`).")
                else:
                    outputs.append(f"SMS sent to **{to}**.")
            elif r["tool"] == "notify:send_email":
                if mid:
                    outputs.append(f"Email sent to **{to}** (message id: `{mid}`).")
                else:
                    outputs.append(f"Email sent to **{to}**.")
        return "\n".join(outputs)

# --------- Backward-compatible function ---------

def message_agent(state: AgentState) -> AgentState:
    """
    Backward-compatible entry point that now delegates to the agent class.
    Required fields (minimum): email, plus either (subject & body) OR (event_type/details).
    """
    if not isinstance(state, dict):
        state = {"input": str(state)}
    agent = MessageAgent()
    try:
        return agent.run(state)
    except Exception as e:
        state.setdefault("tool_calls", [])
        state.setdefault("tool_results", [])
        state["tool_results"].append(f"[FATAL] {type(e).__name__}: {e}")
        state["output"] = f"Email failed: {type(e).__name__}: {e}"
        state["confidence"] = 0.2
        return state




