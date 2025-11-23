import pytest
from agents.memory_agent import memory_agent, AgentState

def test_memory_agent_no_messages():
    state = AgentState()
    result = memory_agent(state)
    assert result["context_summary"] == ""
    assert result["context_refs"] == []
    assert result["memory"] == {"entities": {}, "links": []}

def test_memory_agent_with_messages():
    messages = [
        {"role": "user", "content": "My order is ORD_12345 and payment is PAY_98765."},
        {"role": "assistant", "content": "Your order ORD_12345 is shipped."},
        {"role": "user", "content": "Can you check the payment PAY_98765?"}
    ]
    state = AgentState(messages=messages)
    result = memory_agent(state)
    assert "orders" in result["memory"]["entities"]
    assert "payments" in result["memory"]["entities"]
    assert "ORD_12345" in result["memory"]["entities"]["orders"]
    assert "PAY_98765" in result["memory"]["entities"]["payments"]
    assert isinstance(result["context_summary"], str)
    assert isinstance(result["context_refs"], list)

def test_memory_agent_with_minimal_message():
    messages = [
        {"role": "user", "content": "Hello"}
    ]
    state = AgentState(messages=messages)
    result = memory_agent(state)
    assert isinstance(result["context_summary"], str)
    assert isinstance(result["context_refs"], list)
    assert "general" in result["context_summary"]
