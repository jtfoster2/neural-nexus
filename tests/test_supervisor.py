import supervisor

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
    sup = supervisor
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