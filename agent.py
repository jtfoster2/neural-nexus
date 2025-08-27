from typing import TypedDict
from langgraph.graph import StateGraph, END
from langchain_community.chat_models import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage


# State
class AgentState(TypedDict):
    messages: list[str]   # history of conversation


# Connect to local mistral
llm = ChatOllama(model="mistral")

system_prompt = SystemMessage(
    content="You are a helpful customer support assistant for CapGemini. \
Answer politely, and only about our products, services, or company policies. \
If you don’t know, say you will connect the user to a human agent."
)

# Node: Call the model
def call_model(state: AgentState):
    messages = [system_prompt] + state["messages"] #takes in prompt and adds customer support system prompt
    response = llm.invoke(messages)
    return {"messages": state["messages"] + [response.content]}


# Build workflow
workflow = StateGraph(AgentState)
workflow.add_node("model", call_model)
workflow.set_entry_point("model")
workflow.add_edge("model", END)

# Compile into runnable app
app = workflow.compile()

