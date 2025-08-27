import streamlit as st
from agent import app   # import the LangGraph workflow

st.set_page_config(page_title="Customer Support Agent", page_icon="🤖")

st.title("Customer Support Agent")

# Session state to store chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for i, msg in enumerate(st.session_state.messages):
    if i % 2 == 0:  # user messages are even indexed
        st.chat_message("user").write(msg)
    else:  # AI messages
        st.chat_message("assistant").write(msg)

# Chat input
if prompt := st.chat_input("Ask me anything about your order, billing, etc."):
    # Add user msg
    st.session_state.messages.append(prompt)
    st.chat_message("user").write(prompt)
    with st.spinner("Thinking..."):    
        # Run through LangGraph agent
        state = {"messages": st.session_state.messages}
        result = app.invoke(state)

        # Append AI reply
        reply = result["messages"][-1]
        st.session_state.messages.append(reply)
        st.chat_message("assistant").write(reply)
