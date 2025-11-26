from typing import TypedDict, List, Optional
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
import os
import re
from difflib import SequenceMatcher
from pathlib import Path

# --- Specialist agents ---
from agents.order_agent import order_agent
from agents.shipping_agent import shipping_agent
from agents.billing_agent import billing_agent
from agents.account_agent import account_agent
from agents.message_agent import message_agent
from agents.return_agent import return_agent
from agents.live_agent_router import live_agent_router
from agents.memory_agent import memory_agent
from agents.policy_agent import policy_agent

# --- General LLM agent ---
from agents.general_agent import general_agent, model

LAST_INTENT_BY_THREAD: dict[str, str] = {}

class AgentState(TypedDict, total=False):
    input: str
    email: Optional[str]
    intent: Optional[str]
    reasoning: Optional[str]
    tool_calls: List[str]
    tool_results: List[str]
    output: Optional[str]
    routing_msg: Optional[str]

    # memory fields
    messages: Optional[List[dict]]
    context_summary: Optional[str]
    context_refs: Optional[List[str]]
    preface: Optional[str]
    return_policy: Optional[str]


# ============================================================
#  Keyword Intent Detection
# ============================================================

INTENT_KEYWORDS = {
    "check order": ["check order", "my order", "track order", "order status"],
    "change shipping address": ["change shipping address", "update shipping address", "shipping address"], # checked before "change address"
    "shipping status": ["shipping", "delivery", "where is my package", "track shipping"],
    "billing": ["billing", "charge", "invoice"],
    "check payment": ["payment status", "check payment", "payment"],
    "change address": ["change address", "update address", "new address"],
    "change phone number": ["change phone number", "update phone number", "new phone number", "phone="],
    "change full name": ["change full name", "update full name", "change name", "update name", "first=", "last="],
    "change email": ["change email", "update email", "new email"],
    "change password": ["change password", "reset password", "forgot password"],
    "policy": ["return policy", "warranty", "policy", "eligible for return",
               "return window", "is this under warranty", "warranty claim"],
    "refund": ["refund", "return", "money back"],
    "message agent": ["message agent", "notify user", "email user",
                      "send confirmation", "send me an email", "send email"],
    "live agent": ["live agent", "human agent", "chat with agent"],
    "memory": ["history", "memory", "chat history"],
}


def _normalize(text: str) -> str:
    """
    Simple text normalizer for intent detection:
    - handles "None" safely
    - all lowercases
    - removes punctuation
    - collapses repeated spaces
    """
    if text is None:
        return ""

    # lowercase
    t = text.lower()

    # replace any non alphanumeric or whitespace with a space
    t = re.sub(r"[^a-z0-9\s]", " ", t)

    # collapse multiple spaces
    t = re.sub(r"\s+", " ", t).strip()

    return t

def detect_intent(text: Optional[str]) -> Optional[str]:
    t_raw = text or ""
    t_norm = _normalize(t_raw)
    words = t_norm.split()

    best_intent: Optional[str] = None
    best_score: float = 0.0

    for intent, keys in INTENT_KEYWORDS.items():
        for k in keys:
            k_norm = _normalize(k)

            # returns if exact string is matched
            if k_norm and k_norm in t_norm:
                return intent

            # Typo detection: Fuzzy logic matches against each word in the user input
            for w in words:
                if not w:
                    continue
                score = SequenceMatcher(None, k_norm, w).ratio()
                if score > best_score:
                    best_score = score
                    best_intent = intent

    # Only trusts fuzzy result if similarity is high enough ******TUNING NEEDED******
    if best_score >= 0.75:
        print(f"[SUPERVISOR] Fuzzy intent match: {best_intent} (score={best_score:.2f})")
        return best_intent

    return None


def supervisor(state: AgentState):

    text = state["input"]
    print(f"[SUPERVISOR] User Input: {text}")

    # --------------------------------------------------------
    # Detect intent (keyword → LLM fallback)
    # --------------------------------------------------------
    intent = detect_intent(text)

    if not intent:
        try:
            # Include context information for the LLM
            context_info = ""
            thread_id = str(state.get("conversation_id") or "")
            prev_intent = LAST_INTENT_BY_THREAD.get(thread_id)
            if prev_intent:
                context_info = f"Previous intent was: {prev_intent}. "
            
            resp = model.invoke(
                "Classify the user's intent as one of: "
                "['check order','shipping status','check payment','billing','change password','change address',"
                "'change phone number','change full name','refund','live agent','memory','policy','other'].\n"
                "If user is already in a refund/return context and provides an order ID, classify as 'other'.\n"
                f"{context_info}User: {text}\nReturn just the label."
            )
            label = (getattr(resp, "content", None) or str(resp) or "").strip().lower()

            mapping = {
                "check order": "check order",
                "shipping status": "shipping status",
                "change shipping address": "change shipping address",
                "billing": "billing",
                "check payment": "check payment",
                "change password": "change password",
                "change address": "change address",
                "change phone number": "change phone number",
                "change full name": "change full name",
                "refund": "refund",
                "live agent": "live agent",
                "email agent": "message agent",
                "message agent": "message agent",
                "memory": "memory",
                "chat history": "memory",
                "policy": "policy",
            }
            intent = mapping.get(label, "other")

        except Exception:
            intent = "other"
            
##################################################################
    # --------------------------------------------------------
    # Context-aware intent override for agent continuity
    # --------------------------------------------------------
    thread_id = str(state.get("conversation_id") or "")
    prev_intent = LAST_INTENT_BY_THREAD.get(thread_id)

    # # suppress routing to account_agent after order address update
    # last_action = state.get("last_action")
    # if last_action == "order_address_updated":
    #     LAST_INTENT_BY_THREAD[thread_id] = "change shipping address"
    #     print("[SUPERVISOR] Set previous intent to change shipping address after order address update.")
    # if (
    #     prev_intent == "change shipping address" and
    #     intent == "change address" and
    #     last_action == "order_address_updated"
    # ):
    #     intent = "change shipping address"
    #     print("[SUPERVISOR] Suppressing profile address update after order address change.")

    # if classified as "other" but we're in specific agent context, stay there
    # these agents ask users to provide specific IDs that could be misclassified by the LLM
    if intent == "other" and prev_intent in ["refund", "return", "billing", "check payment", "change address", "change phone number", "change full name"]:
        intent = prev_intent
        print(f"[SUPERVISOR] Context override: staying in {prev_intent} agent")
##################################################################

    state["intent"] = intent


    # --------------------------------------------------------
    # Inject return_policy.txt for policy_agent
    # --------------------------------------------------------
    if intent == "policy":
        policy_path = Path("return_policy.txt")
        if policy_path.exists():
            state["return_policy"] = policy_path.read_text()
            print("[SUPERVISOR] return_policy.txt added into context.")
        else:
            print("[SUPERVISOR] return_policy.txt NOT FOUND!")


    # --------------------------------------------------------
    # Calls memory agent prior to routing
    # --------------------------------------------------------
    try:
        enriched = memory_agent(state)
        state.update(enriched)
        print("[SUPERVISOR] Memory agent added context.")
    except Exception as e:
        print(f"[SUPERVISOR] Memory agent failed: {e}")


    # --------------------------------------------------------
    # Injects context into preface for other agents
    # --------------------------------------------------------
    preface = ""
    if state.get("context_summary"):
        preface += f"Context Summary: {state['context_summary']}\n"

    if state.get("context_refs"):
        preface += "Relevant recent messages:\n"
        for r in state["context_refs"][:3]:
            preface += f"- {r}\n"

    if preface:
        state["preface"] = preface
        print("[SUPERVISOR] Preface added to state.")


    # --------------------------------------------------------
    # Routing message
    # --------------------------------------------------------
    intent_label = (state.get("intent") or "other").lower().strip()
    thread_id = str(state.get("conversation_id") or "")

    prev_intent = LAST_INTENT_BY_THREAD.get(thread_id)

    if prev_intent == intent_label:
        # Same agent as last time for this conversation → no routing message
        state["routing_msg"] = None
        print(f"[SUPERVISOR] Continuing with: {intent_label} (no routing bubble)")
    else:
        # Agent changed → show routing message once
        LAST_INTENT_BY_THREAD[thread_id] = intent_label
        state["routing_msg"] = f"Routing to **{intent_label}** agent..."
        print(f"[SUPERVISOR] Routing to: {intent_label}")

    return state


# ============================================================
#  Build Graph 
# ============================================================

graph = StateGraph(AgentState)

graph.add_node("supervisor", supervisor)
graph.add_node("order_agent", order_agent)
graph.add_node("shipping_agent", shipping_agent)
graph.add_node("billing_agent", billing_agent)
graph.add_node("account_agent", account_agent)
graph.add_node("return_agent", return_agent)
graph.add_node("live_agent_router", live_agent_router)
graph.add_node("memory_agent", memory_agent)
graph.add_node("message_agent", message_agent)
graph.add_node("policy_agent", policy_agent)
graph.add_node("general_agent", general_agent)

graph.set_entry_point("supervisor")


def route_decider(state: AgentState):
    route = (state.get("intent") or "other").lower().strip()
    print(f"[ROUTER] Intent '{route}' → agent node")
    return route


graph.add_conditional_edges(
    "supervisor",
    route_decider,
    {
        "check order": "order_agent",
        "shipping status": "shipping_agent",
        "billing": "billing_agent",
        "change order address": "order_agent",
        "change shipping address": "order_agent",

        "check payment": "billing_agent",
        "change address": "account_agent",
        "change phone number": "account_agent",
        "change full name": "account_agent",
        "change password": "account_agent",

        "refund": "return_agent",
        "return": "return_agent",

        "message": "message_agent",
        "message agent": "message_agent",
        "email agent": "message_agent",

        "live agent": "live_agent_router",
        "policy": "policy_agent",
        "memory": "memory_agent",

        "other": "general_agent",
    },
)

for terminal in [
    "order_agent","shipping_agent","billing_agent","account_agent",
    "return_agent","message_agent","live_agent_router","memory_agent","policy_agent"
]:
    graph.add_edge(terminal, END)

graph.add_edge("general_agent", END)

memory = MemorySaver()
app = graph.compile(checkpointer=memory)

# ============================================================
#  Event Query Interface for streamlit/UI
# ============================================================

def ask_agent_events(query: str, thread_id: str = "default", email: str | None = None):

    state: AgentState = {
        "input": query,
        "email": email,
        "conversation_id": thread_id, # current conversation/thread
        "intent": None,
        "reasoning": None,
        "tool_calls": [],
        "tool_results": [],
        "output": None,
        "routing_msg": None,
    }

    for s in app.stream(state, config={"configurable": {"thread_id": thread_id}}, stream_mode="values"):
        if s.get("routing_msg"):
            yield ("routing", s["routing_msg"])
        if s.get("output"):
            yield ("output", s["output"])