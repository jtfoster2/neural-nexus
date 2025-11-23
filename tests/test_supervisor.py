import pytest
from supervisor import detect_intent, AgentState, supervisor

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

