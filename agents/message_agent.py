from __future__ import annotations
import os
import re
import time
from typing import TypedDict, Optional, List, Dict, Any, Callable
import db
import sendgrid
from dotenv import load_dotenv
from sendgrid_tool import send_email

# --- Load .env ---
load_dotenv()

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

def send_email(to_email: str, subject: str, value: str):

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
    response = send_grid.client.mail.send.post(request_body=data)

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
            value=body,          # match your send_email signature
        ),
        "schema": {
            "to": "str (required, email)",
            "subject": "str (required)",
            "body": "str (required)",
            "cc": "list[str] (optional)",
            "bcc": "list[str] (optional)",
        },
        "desc": "Send an email via SendGrid with optional CC/BCC."
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
        state["intent"] = state.get("intent") or "send email"

        # Perception: ensures we have a recipient email if not already submitted
        self.extract_email(state)

        # Build message (allows user overrides on subject/body)
        if not state.get("subject") or not state.get("body"):
            subj, body = self._build_subject_body(
                email=state.get("email"),
                order_id=state.get("order_id"),
                event_type=state.get("event_type"),
                details=state.get("details"),
                name=state.get("name"),
            )
            state.setdefault("subject", subj)
            state.setdefault("body", body)

        # Validate required fields
        problems = self._validate(state)
        if problems:
            state["output"] = "I can’t send the email yet:\n- " + "\n- ".join(problems)
            state["confidence"] = 0.3
            return state

        # Plan 
        plan = self._plan(state)

        # Act 
        observations = []
        for step in plan:
            obs = self._call_tool_with_retries(step["tool"], step["args"], state)
            observations.append({"step": step, "obs": obs})

        # Observe/Reason
        result = self._interpret(observations, state)

        # Communicate
        state["output"] = self._format_user_message(result, state)
        state["confidence"] = result.get("confidence", 0.85)
        return state

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
        if not state.get("email") or not EMAIL_REGEX.fullmatch(state["email"]):  # type: ignore[index]
            issues.append("Missing or invalid recipient email.")
        if not state.get("subject"):
            issues.append("Missing subject.")
        if not state.get("body"):
            issues.append("Missing body.")
        return issues

    # ----------------- Planning -----------------
    def _plan(self, state: AgentState) -> List[Dict[str, Any]]:
        # Single-step: send the email using the notify tool
        return [{
            "tool": "notify:send_email",
            "args": {
                "to": state["email"],
                "subject": state["subject"],
                "body": state["body"],
                "cc": state.get("cc") or [],
                "bcc": state.get("bcc") or [],
            },
        }]

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

    def _build_subject_body(
        self,
        email: Optional[str],
        order_id: Optional[str],
        event_type: Optional[str],
        details: Optional[str],
        name: Optional[str],
    ) -> tuple[str, str]:
        """
        Build (subject, body) from order + event. Safe for f-strings (no backslashes inside {...}).
        """
        et = (event_type or "status_update").strip().lower()
        pretty_id = f"Order {order_id}" if order_id else "Your order"
        recipient = name or "there"

        # Helper: ensure optional details line(s) end with a newline when present
        def details_block(s: Optional[str], extra_newlines: int = 1) -> str:
            if not s:
                return ""
            return s + ("\n" * extra_newlines)

        if et in {"shipped", "shipping", "label_created"}:
            subject = f"{pretty_id} has shipped"
            body = (
                f"Hi {recipient},\n\n"
                f"Good news — {pretty_id} has shipped.\n"
                f"{details_block(details)}"
                "We’ll share more tracking updates as they’re available.\n\n"
                "Thanks!"
            )
        elif et in {"delivered"}:
            subject = f"{pretty_id} was delivered"
            body = (
                f"Hi {recipient},\n\n"
                f"{pretty_id} has been delivered.\n"
                f"{details_block(details, extra_newlines=2)}"
                "If anything looks off, just reply to this email.\n\n"
                "Best,"
            )
        elif et in {"in_transit", "eta_update"}:
            subject = f"{pretty_id}: in transit"
            body = (
                f"Hi {recipient},\n\n"
                f"{pretty_id} is currently in transit.\n"
                f"{details_block(details)}"
                "We’ll keep you posted on the ETA.\n\n"
                "Thanks!"
            )
        elif et in {"issue", "action_required"}:
            subject = f"Action needed on {pretty_id}"
            body = (
                f"Hi {recipient},\n\n"
                "We need a quick confirmation regarding "
                f"{pretty_id}.\n"
                f"{details_block(details)}"
                "Reply to this email and we’ll take care of it.\n\n"
                "Thanks!"
            )
        else:
            subject = f"{pretty_id}: update"
            body = (
                f"Hi {recipient},\n\n"
                f"Here’s an update on {pretty_id}.\n"
                f"{details_block(details)}"
                "Reach out if you have questions.\n\n"
                "Best,"
            )

        return subject, body


    # --------- interpretation & UX ---------

    def _interpret(self, observations: List[Dict[str, Any]], state: AgentState) -> Dict[str, Any]:
        """Summarize tool outcome into a compact result."""
        if not observations:
            return {"sent": False, "confidence": 0.4}

        raw = observations[0]["obs"]
        sent_ok = True
        message_id = None

        # Try to infer success/message id from common shapes
        try:
            if isinstance(raw, dict):
                sent_ok = bool(raw.get("success", True))
                message_id = raw.get("message_id") or raw.get("id")
            elif isinstance(raw, (list, tuple)) and raw:
                # e.g., SendGrid responses
                message_id = getattr(raw[0], "message_id", None) if hasattr(raw[0], "message_id") else None
                sent_ok = True
            else:
                sent_ok = True
        except Exception:
            sent_ok = True

        return {"sent": sent_ok, "message_id": message_id, "confidence": 0.9 if sent_ok else 0.5}

    def _format_user_message(self, result: Dict[str, Any], state: AgentState) -> str:
        if not result.get("sent"):
            return "I tried to send the email but it may not have gone through. Please check logs."
        mid = result.get("message_id")
        to = state.get("email")
        if mid:
            return f"Email sent to **{to}** (message id: `{mid}`)."
        return f"Email sent to **{to}**."

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
        



