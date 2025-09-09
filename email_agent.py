import os
from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage


# import the tool
from sendgrid_tool import send_order_email

# Set up the environment variable

# Define the graph state


class EmailAgentState(TypedDict):
    messages: Annotated[List[BaseMessage], lambda x, y: x + y]


# Define the LLM and bind it to the SendGrid tool
llm = ChatGoogleGenerativeAI(model="gemini-pro-1.5,temperature=0")
llm_with_tools = llm.tools([send_order_email])

# The main node that calls the LLM


def call_model(state: EmailAgentState):
    response = llm_with_tools.invoke(state['messages'])
    return {"messages": [response]}

# The node that will execute the chosen tool
