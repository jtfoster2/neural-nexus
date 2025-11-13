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
    out = pa.PolicyAgent().run(state)
    assert "Return window:" in out["output"]
    assert out["confidence"] >= 0.9


def test_summary_fallback_no_keyword(tmp_path, monkeypatch):
    _write_policy(tmp_path, "Returns allowed within 30 days of the delivery date.")
    monkeypatch.chdir(tmp_path)

    state = {"input": "tell me the policy details in general"}
    out = pa.PolicyAgent().run(state)
    # Summary uses bullet points like "• Return window"
    assert "• Return window:" in out["output"]
    assert out["confidence"] >= 0.85


def test_return_eligibility_positive(tmp_path, monkeypatch):
    # Use defaults (30-day window, prepaid only for defective/incorrect, etc.)
    _write_policy(tmp_path, "")  # empty -> DEFAULTS
    monkeypatch.chdir(tmp_path)

    # Freeze "now" to a known date and keep delivery within 30 days
    monkeypatch.setattr(pa, "_now", lambda: pa.datetime(2025, 11, 12, tzinfo=pa.timezone.utc))

    state = {
        "input": "I want to return this item",
        "delivery_date": "2025-10-30",  # 13 days before frozen now
        "category": "standard goods",
        "condition": "new",
        "original_packaging": True,
        "proof_of_purchase": True,
        "is_defective": False,
        "is_incorrect_item": False,
        "country": "US",
    }
    out = pa.PolicyAgent().run(state)
    assert out["output"].startswith("Return eligible.")
    # Defaults apply a restocking fee for non-defective eligible returns
    assert "restocking fee" in out["output"].lower()
    assert out["confidence"] >= 0.85


def test_warranty_eligibility_positive(tmp_path, monkeypatch):
    # Policy with 2-year warranty to ensure eligibility
    policy_json = json.dumps({"warranty_years": 2})
    _write_policy(tmp_path, policy_json)
    monkeypatch.chdir(tmp_path)

    # Freeze now and keep purchase within 2 years
    monkeypatch.setattr(pa, "_now", lambda: pa.datetime(2025, 11, 12, tzinfo=pa.timezone.utc))

    state = {
        "input": "warranty claim for a manufacturer defect",
        "purchase_date": "2024-12-01",
        "delivery_date": None,
        "proof_of_purchase": True,
        "is_defective": True,
    }
    out = pa.PolicyAgent().run(state)
    assert "Warranty claim is eligible" in out["output"]
    assert out["confidence"] >= 0.85


def test_policy_agent_wrapper_handles_error(monkeypatch):
    # Force PolicyAgent.run to raise and verify wrapper behavior
    monkeypatch.setattr("agents.policy_agent.PolicyAgent.run", lambda self, s: 1 / 0)
    out = pa.policy_agent({"input": "anything"})
    assert "Sorry" in out["output"]
    assert out["confidence"] == 0.2
