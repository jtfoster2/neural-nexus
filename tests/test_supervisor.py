import sys
import types
import supervisor
from pathlib import Path

def test_detect_intent_various_keywords():
    sup = supervisor
    # map sample phrases to expected intents (as defined in the bottom INTENT_KEYWORDS)
    cases = {
        "I need help with billing and charges": "billing",
        "Can you check my order status?": "check order",
        "Where is my package, track shipping": "shipping status",
        "What's my payment status?": "check payment",
        "I want to change address to 123 Elm": "change address",
        "I need to reset password, I forgot password": "change password",
        "Please update my phone number": "change phone number",
        "How do I change my name?": "change full name",
        "Tell me about your return policy": "policy",
        "I want a refund": "refund",
        "Message agent to notify user": "message agent",
        "I want to speak to a human agent": "live agent",
        "Show my chat history": "memory",
    }
    for text, expected in cases.items():
        detected = sup.detect_intent(text)
        assert detected == expected, f"text={text!r} expected={expected!r} got={detected!r}"

def test_supervisor_sets_intent_and_routing_message():
    sup = supervisor
    sup.LAST_INTENT_BY_THREAD.clear()

    state = {
        "input": "I have a billing question about a charge",
        "email": None,
        "conversation_id": "thread-123",
        "intent": None,
        "reasoning": None,
        "tool_calls": [],
        "tool_results": [],
        "output": None,
        "routing_msg": None,
    }

    out = sup.supervisor(state)
    assert out["intent"] == "billing"
    assert out["routing_msg"] is not None and "billing" in out["routing_msg"]
    # subsequent call with same thread should not produce routing bubble
    state2 = {
        "input": "Another billing question",
        "email": None,
        "conversation_id": "thread-123",
        "intent": None,
        "reasoning": None,
        "tool_calls": [],
        "tool_results": [],
        "output": None,
        "routing_msg": None,
    }
    out2 = sup.supervisor(state2)
    assert out2["intent"] == "billing"
    assert out2["routing_msg"] is None

def test_supervisor_memory_agent_called_and_preface_added():
    sup = supervisor
    sup.LAST_INTENT_BY_THREAD.clear()

    # monkeypatch the memory_agent to return context summary and refs
    def fake_memory_agent(state):
        return {"context_summary": "recent convo summary", "context_refs": ["msg1","msg2","msg3","msg4"]}

    # inject our fake into the module
    sup.memory_agent = fake_memory_agent

    state = {
        "input": "I want to check my order",
        "email": None,
        "conversation_id": "thread-xyz",
        "intent": None,
        "reasoning": None,
        "tool_calls": [],
        "tool_results": [],
        "output": None,
        "routing_msg": None,
    }

    out = sup.supervisor(state)
    # memory_agent should have enriched state and supervisor should add a preface
    assert out.get("context_summary") == "recent convo summary"
    assert out.get("preface") is not None and "Context Summary" in out["preface"]
    assert out["intent"] == "check order"
    assert out["routing_msg"] is not None and "check order" in out["routing_msg"]