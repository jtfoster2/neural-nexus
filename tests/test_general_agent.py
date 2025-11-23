import pytest
from agents.general_agent import general_agent, AgentState

class DummyModel:
    def invoke(self, prompt):
        class Resp:
            content = "This is a test response."
        return Resp()

def test_general_agent_basic(monkeypatch):
    monkeypatch.setattr("agents.general_agent.model", DummyModel())
    state = AgentState(input="Hello, what are your hours?", email="user@example.com")
    result = general_agent(state)
    assert "test response" in result["output"].lower()
    assert isinstance(result["tool_calls"], list)
    assert isinstance(result["tool_results"], list)

def test_general_agent_error(monkeypatch):
    class ErrorModel:
        def invoke(self, prompt):
            raise RuntimeError("Model error!")
    monkeypatch.setattr("agents.general_agent.model", ErrorModel())
    state = AgentState(input="Hi", email="user@example.com")
    result = general_agent(state)
    assert "went wrong" in result["output"].lower()
    assert any("error" in r.lower() for r in result["tool_results"])

def test_general_agent_preface(monkeypatch):
    monkeypatch.setattr("agents.general_agent.model", DummyModel())
    state = AgentState(input="Can you help?", preface="Previous: User asked about shipping.")
    result = general_agent(state)
    assert "test response" in result["output"].lower()

def test_general_agent_context_summary(monkeypatch):
    monkeypatch.setattr("agents.general_agent.model", DummyModel())
    state = AgentState(input="Can you help?", context_summary="User wants help with billing.")
    result = general_agent(state)
    assert "test response" in result["output"].lower()
