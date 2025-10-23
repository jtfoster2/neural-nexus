# supervisor.py
from typing import TypedDict, List, Optional
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

# --- Import specialist agents ---
from agents.order_agent import order_agent
from agents.shipping_agent import shipping_agent
from agents.billing_agent import billing_agent
from agents.account_agent import account_agent
from agents.message_agent import message_agent
from agents.return_agent import return_agent
from agents.live_agent_router import live_agent_router
from agents.memory_agent import memory_agent

# --- Import generalist agent components ---
from agents.general_agent import general_agent, model  #Fallback LLM


class AgentState(TypedDict):
    input: str
    email: Optional[str]
    intent: Optional[str]
    reasoning: Optional[str]
    tool_calls: List[str]
    tool_results: List[str]
    output: Optional[str]
    routing_msg: Optional[str]

#Top-level router. Determines user intent and writes it to state['intent'].
def supervisor(state: AgentState):

    text = state["input"]
    print(text)


    #Finds intent using keyword matching and LLM fallback
    intent = (detect_intent(text) or "").strip().lower()



    if not intent:
        try:
            resp = model.invoke(
                "Classify the user's intent as one of: "
                "['check order','shipping status','billing','forgot password','change address',"
                "'refund','live agent','memory','other'].\n"
                f"User: {text}\n"
                "Return just the label."
            )
            label = (getattr(resp, "content", None) or str(resp) or "").strip().lower()
            known = {
                "check order": "check order",
                "shipping status": "shipping status",
                "billing": "billing",
                "forgot password": "forgot password",
                "change address": "change address",
                "refund": "refund",
                "live agent": "live agent",
                "email agent": "message agent",
                "message agent": "message agent",
                "live agent": "live agent",
                "memory": "memory",
                "chat history": "memory",
                "other": "other", #general_agent
            }
            intent = known.get(label, "other")
        except Exception:
            intent = "other"

    state["intent"] = intent or "other"

    # States what agent is being routed to
    # ----------------
    agent_name = state.get('intent')
    routing_msg = f"Routing to **{agent_name}** agent..."
    state["routing_msg"] = routing_msg
    print(f"[DEBUG************] state['routing_msg']: {state['routing_msg']}") #debugging
    # ----------------

    return state


# ---- Build the graph ----
graph = StateGraph(AgentState)

# nodes
graph.add_node("supervisor", supervisor)
graph.add_node("order_agent", order_agent)
graph.add_node("shipping_agent", shipping_agent)
graph.add_node("billing_agent", billing_agent)
graph.add_node("account_agent", account_agent)
graph.add_node("return_agent", return_agent)
graph.add_node("live_agent_router", live_agent_router)
graph.add_node("memory_agent", memory_agent)
graph.add_node("message_agent", message_agent)
graph.add_node("general_agent", general_agent)

graph.set_entry_point("supervisor")


def route_decider(state: AgentState):
    route = (state.get("intent") or "other").lower().strip()
    print(f"[ROUTER] Intent '{route}' → agent node:")
    return route



graph.add_conditional_edges(
    "supervisor",
    route_decider,
    {
        "check order": "order_agent",
        "shipping status": "shipping_agent",
        "billing": "billing_agent",
        "forgot password": "account_agent",
        "change address": "account_agent",
        "refund": "return_agent",
        "return": "return_agent",
        "message": "message_agent",
        "message agent": "message_agent",
        "email agent": "message_agent",
        "live agent": "live_agent_router",
        "live agent": "live_agent_router",
        "memory": "memory_agent",
        "other": "general_agent", # fallback to your general agent
    },
)

# Specialists Agents
for terminal in [
    "order_agent", "shipping_agent", "billing_agent", "account_agent", 
    "return_agent", "message_agent", "live_agent_router", "memory_agent"
]:
    graph.add_edge(terminal, END)

# Generalist chain 
graph.add_edge("general_agent", END)

memory = MemorySaver()
app = graph.compile(checkpointer=memory)


def ask_agent(query: str, thread_id: str = "default", email: str | None = None) -> str:

    state: AgentState = {
        "input": query,
        "email": email,
        "intent": None,
        "reasoning": None,
        "tool_calls": [],
        "tool_results": [],
        "output": None,
        "routing_msg": None,
    }
    result = app.invoke(state, config={"configurable": {"thread_id": thread_id}})
    routing_msg = result.get("routing_msg") #extract routing message
    output = result.get("output") or ""
    if routing_msg:
        return f"{routing_msg}\n\n{output}"
    else:
        return output
    
def ask_agent_events(query: str, thread_id: str = "default", email: str | None = None):
    """
    Yields tuples of (kind, text) as the graph progresses:
      ("routing", "Routing to **…** agent...")
      ("output",  "<final agent reply>")
    """
    state: AgentState = {
        "input": query,
        "email": email,
        "intent": None,
        "reasoning": None,
        "tool_calls": [],
        "tool_results": [],
        "output": None,
        "routing_msg": None,
    }

    # Stream state updates as nodes finish
    for s in app.stream(state, config={"configurable": {"thread_id": thread_id}}, stream_mode="values"):
        if s.get("routing_msg"):
            yield ("routing", s["routing_msg"])
        if s.get("output"):
            yield ("output", s["output"])

#this is to detect keywords when users type-in the input
INTENT_KEYWORDS = {
    "check order": ["order", "orders", "check order", "my order", "track order"],
    "shipping status": ["shipping", "delivery", "where is my package", "track shipping"],
    "billing": ["billing", "payment", "charge", "invoice"],
    "change address": ["change address", "update address", "new address"],
    "change email": ["change email", "update email", "new email"],
    "forgot password": ["forgot password", "reset password", "lost password", "password"],
    "refund": ["refund", "return", "money back"],
    "message agent": ["message agent", "notify user", "email user", "send confirmation", "send me an email"],
    "email agent": ["email agent", "send email", "message"],
    "live agent": ["live agent", "human agent", "chat with agent"],
    "memory": ["history", "memory", "chat history"]
}

def detect_intent(user_input: Optional[str]):
    """Match user input against keywords to detect intent."""
    text = (user_input or "").lower()
    for intent, keywords in INTENT_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return intent
    return None
