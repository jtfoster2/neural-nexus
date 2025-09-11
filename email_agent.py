import os
from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage


# import the tool
from sendgrid_tool import send_order_email

# set up environment variables
os.environ["GEMINI_API_KEY"] = "YOUT_GERMINI_API_KEY"
os.environ["SENDER_EMAIL"] = "your_verified_sender@example.com"

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

# The tool exercution node


def call_tool(state: EmailAgentState):
    last_message = state['messages'][-1]
    tool_calls = last_message.tool_calls
    tool_results = []

    for tool_call in tool_calls:
        tool_name = tool_call['name']
        tool_args = tool_call['args']
        if tool_name == 'send_order_email':
            result = send_order_email.invoke(tool_args)
    tool_results.append(AIMessage(content=f"Tool call sucessful: {result}"))
    return {"messages": tool_results}

# Router logic


def should_continue(state: EmailAgentState):
    last_massage = (state['message'][-1])
    if last_massage.tool_calls:
        return "continue"
    else:
        return "end"


# Build the Langgraph workflow
workflow = StateGraph(EmailAgentState)
workflow.add_node("llm", call_model)
workflow.add_node("tool", call_tool)
workflow.add_edge("tool", "llm")
workflow.add_conditional_edges("llm", should_continue, {
                               "conitnue": "tool", "end": END})
workflow.set_conditional_entry_point("llm")
graph = workflow.compile()
