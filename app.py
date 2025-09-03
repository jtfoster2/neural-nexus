import streamlit as st
from agent import app, ask_agent #imported ask_agent function to prevent AttributeError

st.set_page_config(page_title="Customer Support Agent")

# --- Title ---
st.markdown("<h1 style='text-align: center;'>Customer Support Agent</h1>", unsafe_allow_html=True) #Centered title

# --- Session state for chat history ---
if "messages" not in st.session_state:
    st.session_state.messages = []  #Stores chat history in structure {"role": "user"/"assistant", "content": str} 

# --- Display chat history ---
for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.chat_message("user").write(msg["content"])
    else:
        st.chat_message("assistant").write(msg["content"])

# --- Chat input ---
if prompt := st.chat_input("Ask me anything about your order, billing, etc."):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)

    with st.spinner("Thinking..."):
        reply = ask_agent(prompt, thread_id="customer-support")  # calls agent
        st.session_state.messages.append({"role": "assistant", "content": reply})
        st.chat_message("assistant").write(reply)
