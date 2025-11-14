# agents/policy_agent.py
from __future__ import annotations

from typing import TypedDict, Optional, List, Dict, Any
from pathlib import Path

from agents.general_agent import model #uses gemini as backup


class AgentState(TypedDict, total=False):
    # Core fields used across your graph
    input: str
    email: Optional[str]
    intent: Optional[str]
    reasoning: Optional[str]
    tool_calls: List[str]
    tool_results: List[str]
    output: Optional[str]
    routing_msg: Optional[str]

    # Optional order-related context that other agents may add
    order_id: Optional[str]
    status: Optional[str]
    created_at: Optional[str]
    delivered_at: Optional[str]
    delivery_date: Optional[str]
    order_date: Optional[str]
    purchase_date: Optional[str]
    request_date: Optional[str]
    item_category: Optional[str]
    is_clearance: Optional[bool]
    reason_for_return: Optional[str]

    # Context from memory_agent / supervisor
    context_summary: Optional[str]
    context_refs: Optional[List[str]]
    preface: Optional[str]
    memory: Optional[Dict[str, Any]]

def _ensure_lists(state: AgentState) -> None:
    state.setdefault("tool_calls", [])
    state.setdefault("tool_results", [])


def _load_policy_text(state: AgentState) -> str:
    
    try:
        policy_path = Path("return_policy.txt")
        return policy_path.read_text(encoding="utf-8")
    
    except Exception:
        return (
            "No return policy text could be loaded."
            "Please ensure return_policy.txt exists or the supervisor injects it."
        )


def _has_order_context(state: AgentState) -> bool: #checks if any order-related fields are present
    keys = [
        "order_id",
        "status",
        "created_at",
        "delivered_at",
        "delivery_date",
        "order_date",
        "purchase_date",
        "request_date",
        "item_category",
        "is_clearance",
        "reason_for_return",
    ]
    return any(state.get(k) not in (None, "", []) for k in keys)


def _build_order_context(state: AgentState) -> str: #builds a text summary of order-related fields
    lines: List[str] = []

    def add(label: str, key: str):
        if key in state and state.get(key) not in (None, ""):
            lines.append(f"{label}: {state[key]}")

    add("Order ID", "order_id")
    add("Status", "status")
    add("Created at", "created_at")
    add("Delivered at", "delivered_at")
    add("Delivery date", "delivery_date")
    add("Order date", "order_date")
    add("Purchase date", "purchase_date")
    add("Return request date", "request_date")
    add("Item category/type", "item_category")
    add("Reason for return", "reason_for_return")

    # Boolean flags
    if state.get("is_clearance") is True:
        lines.append("Item is a clearance/final-sale product.")

    return "\n".join(lines) if lines else "No order context provided."


def _answer_policy_question(policy_text: str, question: str) -> str:

    if not question.strip():
        return "I can answer questions about our return and warranty policy. What would you like to know?"

    prompt = f"""
        You are a customer support assistant. You MUST answer using ONLY the policy text below.

        Return & Warranty Policy:
        \"\"\"{policy_text}\"\"\"

        User's question:
        \"\"\"{question}\"\"\"

        Instructions:
        - Base your answer solely on the policy text above.
        - If the policy explicitly answers the question, quote or paraphrase the relevant part.
        - If the policy does NOT clearly specify the answer, respond with something like:
        "The policy text does not specify this clearly. Please contact support for clarification."
        - Be concise (2–5 short sentences).
        """

    resp = model.invoke(prompt)
    return getattr(resp, "content", str(resp))


def _check_eligibility(policy_text: str, question: str, order_context: str) -> str:
    """
    Eligibility check using ONLY the policy text + the order context.
    """
    prompt = f"""
    You are an assistant that determines return/warranty eligibility using ONLY the policy text below.

    Return & Warranty Policy:
    \"\"\"{policy_text}\"\"\"

    Order context:
    \"\"\"{order_context}\"\"\"

    User's question or request:
    \"\"\"{question}\"\"\"

    Tasks:
    1. Decide if the request is clearly **Eligible**, **Not eligible**, or **Unclear** based ONLY on the policy text.
    2. Briefly explain which parts of the policy you used.
    3. If anything is missing (e.g., dates or information), say the decision is **Unclear** and note what additional information is needed.

    OUTPUT FORMAT (exactly):
    Decision: <Eligible / Not eligible / Unclear>
    Reason: <short explanation in 2–4 sentences, referencing the policy text>
    """

    resp = model.invoke(prompt)
    return getattr(resp, "content", str(resp))


def policy_agent(state: AgentState) -> AgentState:
    """
    Policy agent that relies entirely on the text inside return_policy.txt

    - If there is NO order context, treat as a general question about the policy.
    - If there IS order context, treat as an eligibility check.
    """
    print("[AGENT] policy_agent selected")
    _ensure_lists(state)

    policy_text = _load_policy_text(state)

    # 🔹 Combine memory context + current question
    base_question = (state.get("input") or "").strip()
    preface = (state.get("preface") or "").strip()

    if preface:
        # Let the LLM see prior conversation context + current question
        user_question = (
            "Conversation context from previous messages:\n"
            f"{preface}\n\n"
            "User's current question:\n"
            f"{base_question}"
        )
    else:
        user_question = base_question

    has_order = _has_order_context(state)

    state["tool_calls"].append(
        f"policy_agent(mode={'eligibility' if has_order else 'qa'})"
    )

    if has_order:
        # Eligibility mode
        order_ctx = _build_order_context(state)
        result = _check_eligibility(policy_text, user_question, order_ctx)
        state["tool_results"].append("policy_agent: eligibility check completed")
        state["output"] = result
    else:
        # Pure Q&A mode
        result = _answer_policy_question(policy_text, user_question)
        state["tool_results"].append("policy_agent: qa completed")
        state["output"] = result

    return state

