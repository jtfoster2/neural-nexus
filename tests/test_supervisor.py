
import pytest
from supervisor import detect_intent, AgentState, supervisor
import supervisor as sup

def test_detect_intent_order_address():
    text = "ord_208 123 Main St, Atlanta, GA 30301"
    intent = detect_intent(text)
    assert intent == "change shipping address"

def test_detect_intent_profile_address():
    text = "change address to 456 Oak Ave, Marietta, GA 30098"
    intent = detect_intent(text)
    assert intent == "change address"

def test_detect_intent_ambiguous():
    text = "I want to change something about my address for ord_208"
    intent = detect_intent(text)
    assert intent is None

def test_detect_intent_missing_order_id():
    text = "update shipping address to 123 Main St, Atlanta, GA 30301"
    intent = detect_intent(text)
    assert intent == "change shipping address"

def test_detect_intent_conflicting_keywords():
    text = "ord_208 change address to 123 Main St, Atlanta, GA 30301"
    intent = detect_intent(text)
    assert intent == "change shipping address"

def test_supervisor_routing_order_agent():
    state = AgentState(input="ord_208 123 Main St, Atlanta, GA 30301")
    result = supervisor(state)
    assert result["intent"] == "change shipping address"

def test_supervisor_llm_fallback():
    state = AgentState(input="I need help with my account password")
    result = supervisor(state)
    assert result["intent"] in ["change password", "other"]

def test_supervisor_sets_intent_and_routing_message():
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
    # subsequent call with same thread should not produce routing loop
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
    sup.LAST_INTENT_BY_THREAD.clear()

    # monkeypatch the memory_agent to return context summary and refs
    def fake_memory_agent(state):
        return {"context_summary": "recent convo summary", "context_refs": ["msg1","msg2","msg3","msg4"]}

    # inject the fake agent into the module
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
