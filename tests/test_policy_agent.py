# tests/test_policy_agent.py
import json
import textwrap
import pytest
from agents import policy_agent as pa



def _write_policy(tmp_path, text):
    p = tmp_path / "return_policy.txt"
    p.write_text(text)
    return p


def test_faq_answer_no_order_context(tmp_path, monkeypatch):
    # Creates a human-readable policy; compile_policy will parse useful bits
    _write_policy(
        tmp_path,
        textwrap.dedent(
            """
            Returns: You may return items within 45 days of the delivery date.
            RMA: Items must be shipped back within 10 days of RMA approval.
            We offer a 2-year limited warranty.
            Non-returnable including digital goods, personalized, perishable.
            Restocking charges may apply (up to 20%).
            Defective or incorrect items: we cover all return shipping costs.
            International customers are responsible for all return shipping.
            """
        ).strip()
    )
    monkeypatch.chdir(tmp_path)

    state = {"input": "What is the return window?"}
    out = pa.policy_agent(state)
    assert "45 days" in out["output"]

def test_summary_fallback_no_keyword(tmp_path, monkeypatch):
    _write_policy(tmp_path, "Returns allowed within 30 days of the delivery date.")
    monkeypatch.chdir(tmp_path)

    state = {"input": "tell me the policy details in general"}
    out = pa.policy_agent(state)
    assert "returns are allowed" in out["output"].lower() #case insensitive match

def test_return_eligibility_positive(tmp_path, monkeypatch):
    # Write a simple policy file so _load_policy_text() has something to read
    _write_policy(
        tmp_path,
        "You may return most items within 30 days of delivery as long as they are in resellable condition."
    )
    monkeypatch.chdir(tmp_path)

    # Patch _check_eligibility so we don't have to hit a real LLM/model
    def fake_check(policy_text, question, order_context):
        # Sanity-check that order context is being built and passed in
        assert "Order ID: ORD123" in order_context
        assert "Delivery date: 2025-10-30" in order_context
        # Return a deterministic eligible decision
        return "Decision: Eligible\nReason: Within the 30-day return window."

    monkeypatch.setattr(pa, "_check_eligibility", fake_check)

    # Provide enough order fields so _has_order_context() returns True
    state = {
        "input": "I want to return this item",
        "order_id": "ORD123",
        "delivery_date": "2025-10-30",
        "item_category": "standard goods",
        "reason_for_return": "changed my mind",
    }

    out = pa.policy_agent(state)

    # We expect the fake eligibility decision to come back as the output
    assert out["output"].startswith("Decision: Eligible")
    # And that the agent recorded the eligibility check in tool_results
    assert "policy_agent: eligibility check completed" in out["tool_results"]


def test_warranty_eligibility_positive(tmp_path, monkeypatch):
    # Policy with 2-year warranty to ensure eligibility
    policy_json = json.dumps({"warranty_years": 2})
    _write_policy(tmp_path, policy_json)
    monkeypatch.chdir(tmp_path)

    # Patch _check_eligibility so we don't depend on a real LLM/model
    def fake_check(policy_text, question, order_context):
        # Sanity-check that policy and order context are passed in
        assert "warranty_years" in policy_text
        assert "Purchase date: 2024-12-01" in order_context
        assert "Item category/type: electronics" in order_context
        # Deterministic warranty decision
        return "Warranty claim is eligible for repair or replacement."

    monkeypatch.setattr(pa, "_check_eligibility", fake_check)

    # Provide enough order fields so _has_order_context() returns True
    state = {
        "input": "warranty claim for a manufacturer defect",
        "order_id": "ORD-W-001",
        "purchase_date": "2024-12-01",
        "item_category": "electronics",
        "is_defective": True,
        "proof_of_purchase": True,
    }

    out = pa.policy_agent(state)

    # We expect the fake warranty decision to come back as the output
    assert "Warranty claim is eligible" in out["output"]
    # And that the agent recorded the eligibility check in tool_results
    assert "policy_agent: eligibility check completed" in out["tool_results"]

def test_policy_agent_wrapper_handles_error(monkeypatch):
    # Simulate an error when reading return_policy.txt so that _load_policy_text has to go down its exception-handling path.
    def disk_error(self, *args, **kwargs):
        raise OSError("disk error")

    monkeypatch.setattr(pa.Path, "read_text", disk_error)

    # assert that the fallback policy text is passed through correctly.
    def fake_answer(policy_text: str, question: str) -> str:
        assert "No return policy text could be loaded." in policy_text
        assert "Please ensure return_policy.txt exists" in policy_text
        return "fallback: safe response"

    monkeypatch.setattr(pa, "_answer_policy_question", fake_answer)

    # Minimal state: no order context → QA mode, which will call _answer_policy_question
    state = {"input": "test error handling"}
    out = pa.policy_agent(state)

    # We should get the fake safe response, not an exception
    assert out["output"] == "fallback: safe response"
