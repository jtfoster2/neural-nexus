import pytest
from agents.billing_agent import billing_agent, AgentState

def test_billing_agent_guest_session():
    state = AgentState(input="pay_123", email=None, intent="billing")
    result = billing_agent(state)
    assert "guest session" in result["output"].lower()

def test_billing_agent_missing_payment_id():
    state = AgentState(input="", email="user@example.com", intent="billing")
    result = billing_agent(state)
    assert "enter your payment id" in result["output"].lower()

def test_billing_agent_payment_not_found(monkeypatch):
    def mock_get_payment_by_id(payment_id, email):
        return None
    monkeypatch.setattr("db.get_payment_by_id", mock_get_payment_by_id)
    state = AgentState(input="pay_404", email="user@example.com", intent="billing")
    result = billing_agent(state)
    assert "couldn't find any payments" in result["output"].lower()

def test_billing_agent_payment_found(monkeypatch):
    def mock_get_payment_by_id(payment_id, email):
        return {"status": "Completed", "created_at": "2025-11-22"}
    monkeypatch.setattr("db.get_payment_by_id", mock_get_payment_by_id)
    state = AgentState(input="pay_200", email="user@example.com", intent="billing")
    result = billing_agent(state)
    assert "completed" in result["output"].lower()
    assert "2025-11-22" in result["output"]

def test_billing_agent_non_billing_intent():
    state = AgentState(input="hello", email="user@example.com", intent="other")
    result = billing_agent(state)
    assert "payment-related" in result["output"].lower()
