import pytest
import types


# ---------------------------------------------------------------------
# PRE-INJECTS a fake sendgrid_tool
# ---------------------------------------------------------------------
fake_sendgrid = types.ModuleType("sendgrid_tool")
fake_sendgrid.send_email = lambda *a, **k: {"success": True, "status_code": 202, "message_id": "fake_123"}

import sys
sys.modules["sendgrid_tool"] = fake_sendgrid

from agents import message_agent as ma



def test_missing_email():
    state = {"input": "hi"}
    out = ma.MessageAgent().run(state)
    assert out["confidence"] == 0.3
    assert "Missing or invalid recipient email" in out["output"]


def test_extract_email_from_text():
    agent = ma.MessageAgent()
    s = {"input": "Contact me at Test@example.com please"}
    agent.extract_email(s)
    assert s["email"] == "test@example.com"


def test_successful_email_sent(monkeypatch):
    # Fakes the actual email send to avoid any API calls
    def fake_send_email(to_email, subject, value):
        # mimic a simplified SendGrid response
        return {"success": True, "status_code": 202, "message_id": "msg_123"}

    monkeypatch.setattr(ma, "send_email", fake_send_email)

    agent = ma.MessageAgent()
    state = {
        "email": "user@example.com",
        "order_id": "ORD-9",
        "event_type": "shipped",
        "details": "Tracking: 1Z999...",
        # agent build body/subject from these
    }
    out = agent.run(state)

    # Output formatting + overall confidence
    assert out["confidence"] >= 0.85
    assert out["output"].startswith("Email sent to **user@example.com**")
    assert "msg_123" in out["output"]

    # Tool call/result logging kept brief but present
    assert out["tool_calls"] and "notify:send_email(" in out["tool_calls"][0]
    assert out["tool_results"]


def test_message_agent_wrapper_error_handler(monkeypatch):
    monkeypatch.setattr("agents.message_agent.MessageAgent.run", lambda self, s: 1 / 0)
    out = ma.message_agent({"input": "anything"})
    assert "Email failed:" in out["output"]
    assert out["confidence"] == 0.2
