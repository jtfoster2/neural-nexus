import streamlit as st
import json
from supervisor import ask_agent, detect_intent
import db_old
import time
import uuid
import re


db_old.init_db()

st.set_page_config(page_title="Customer Support Agent")

# --- Title ---
st.markdown("<h1 style='text-align: center;'>Customer Support Agent</h1>", unsafe_allow_html=True)

# --- Session state for chat history ---
if "messages" not in st.session_state:
    st.session_state.messages = [] #Stores chat history in structure {"role": "user"/"assistant", "content": str}

if "user_email" not in st.session_state:
    st.session_state.user_email = None

if "user_name" not in st.session_state:
    st.session_state.user_name = None

if "last_intent" not in st.session_state:
    st.session_state.last_intent = None

if "check_order_followup" not in st.session_state:
    st.session_state.check_order_followup = False

#Load user chat history - Not working properly atm
if st.session_state.user_email and not st.session_state.messages:
    st.session_state.messages = db_old.load_messages(st.session_state.user_email)

#Greeting text
if not st.session_state.messages:
    st.session_state.messages.append({
        "role": "assistant",
        "content": "👋 Hi there! How can I help you today?"
    })

# --- Display chat history ---
for msg in st.session_state.messages:
    role = (msg.get("role") or "assistant").lower()
    if role not in {"user", "assistant"}:
        role = "assistant"
    st.chat_message(role).write(msg["content"])

def ask_with_spinner(prompt: str, email: str | None): # show spinner while waiting for response
    start = time.time()
    with st.spinner("Thinking…"):
        reply = ask_agent(prompt, email=email)
        elapsed = time.time() - start
        # Enforce a minimum of 3s total to avoid “snap” responses
        if elapsed < 3:
            time.sleep(3 - elapsed)
    return reply

def handle_option(option, from_chat=False):
    user_email = st.session_state.user_email
    user_name = st.session_state.user_name or "Customer"
    user = db_old.get_user_by_email(user_email) if user_email else None
    normalized = option.replace('_', ' ').lower()
    reply = ask_with_spinner(option, email=user_email)
    if user_email and not from_chat:
        st.session_state.messages.append({"role": "user", "content": option})
        st.session_state.messages.append({"role": "assistant", "content": reply})
        db_old.save_message(user_email, "assistant", reply)
        st.rerun()
    return reply



# --- Chat input ---
if prompt := st.chat_input("Ask me anything about your order, billing, etc.", key="chat_input_main"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    prompt_lower = prompt.lower()
    reply = None

    #User provides email
    if "@" in prompt and "." in prompt and not st.session_state.user_email:
        user_email = prompt.strip().lower()
        user = db_old.get_user_by_email(user_email)
        if user:
            st.session_state.user_email = user_email
            st.session_state.user_name = user[1]

            #if a previous intent was waiting for email
            if st.session_state.last_intent:
                normalized_intent = detect_intent(st.session_state.last_intent)
                reply = handle_option(normalized_intent, from_chat=True)
                st.session_state.last_intent = None
            else:
                reply = f"Welcome back, **{user[1]}**! How can I help you today? You can type your request your choose the options below."
        else:
            reply = "Sorry, we couldn't find your email. Please register or try again."

    #User has email, handle known keywords
    elif st.session_state.user_email:
        intent = detect_intent(prompt_lower)
        if intent:
            reply = handle_option(intent, from_chat=True)
        else:
            st.chat_message("user").write(prompt)
            reply = ask_with_spinner(prompt, email=st.session_state.user_email)

    #Fallback to AI
    else:
        st.chat_message("user").write(prompt)
        reply = ask_with_spinner(prompt, email=st.session_state.user_email)

    #Save messages
    if st.session_state.user_email:
        db_old.save_message(st.session_state.user_email, "user", prompt)
        db_old.save_message(st.session_state.user_email, "assistant", reply)

    st.session_state.messages.append({"role": "assistant", "content": reply})
    st.rerun()



#Quick Options Menu
if st.session_state.user_email:
    st.markdown("---")
    st.markdown("#### Quick Options")
    col1, col2, col3, col4 = st.columns(4)
    def handle_option_button(option):
        handle_option(option)
    with col1:
        if st.button("Forgot Password", use_container_width=True):
            handle_option_button("Forgot Password")
    with col2:
        if st.button("Refund", use_container_width=True):
            handle_option_button("Refund")
    with col3:
        if st.button("Check Order", use_container_width=True):
            handle_option_button("Check Order")
    with col4:
        if st.button("Shipping Status", use_container_width=True):
            handle_option_button("Shipping Status")
    col5, col6, col7 = st.columns(3)
    with col5:
        if st.button("Change Address", use_container_width=True):
            handle_option_button("Change Address")
    with col6:
        if st.button("Live Agent", use_container_width=True):
            handle_option_button("Live Agent")
    with col7:
        if st.button("Billing", use_container_width=True):
            handle_option_button("Billing")
    # with col8:
    #     if st.button("Chat History", use_container_width=True): #will impliment it later
    #         handle_option_button("Chat History")
    


