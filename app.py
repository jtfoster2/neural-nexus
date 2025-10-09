import streamlit as st
import uuid
import json
import time
import db
from supervisor import ask_agent

def ask_with_spinner(prompt: str, UUID, email: str | None):
    """Show spinner while waiting for response."""
    start = time.time()
    with st.spinner("Thinking…"):
        reply = ask_agent(prompt, UUID, email)
        elapsed = time.time() - start
        # Enforce a minimum of 3s delay for realism
        if elapsed < 3:
            time.sleep(3 - elapsed)
    return reply


if "db_initialized" not in st.session_state:
    db.init_db()
    st.session_state.db_initialized = True


st.set_page_config(page_title="Customer Support Agent")

# --- Title ---
st.markdown("<h1 style='text-align: center;'>Customer Support Agent</h1>", unsafe_allow_html=True)

# --- Session setup ---
if "user_email" not in st.session_state:
    st.session_state.user_email = None

if "user_name" not in st.session_state:
    st.session_state.user_name = None

if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

# --- Email prompt ---
if not st.session_state.user_email:
    st.info("Please enter your email to begin.")
    email = st.text_input("Email address", placeholder="you@example.com")
    if email:
        st.session_state.user_email = email.strip().lower()
        st.success(f"Welcome, {st.session_state.user_email}!")
        st.rerun()

# --- Conversation ID ---
if st.session_state.user_email:
    #st.caption(f"Session ID: `{st.session_state.conversation_id}`") #DEBUGGING
    st.caption(f"User: `{st.session_state.user_email}`")

#Greeting text
if not st.session_state.messages:
    st.session_state.messages.append({
        "role": "assistant",
        "content": "👋 Hi there! How can I help you today?"
    })

# --- Display chat history ---
for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

# --- Chat input ---
if st.session_state.user_email:
    prompt = st.chat_input("Ask me anything about your order, billing, etc.")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Make sure user exists in DB before logging
        user = db.get_user(st.session_state.user_email)
        if not user:
            db.add_user(st.session_state.user_email)

        # Generate AI reply with spinner
        st.chat_message("user").write(prompt)
        reply = ask_with_spinner(prompt, st.session_state.conversation_id, st.session_state.user_email)

        # Save reply to chat history
        st.session_state.messages.append({"role": "assistant", "content": reply})

        # Persist conversation as JSON
        db.add_conversation(
            conversation_id=st.session_state.conversation_id,
            email=st.session_state.user_email,
            conversation_text=json.dumps(st.session_state.messages)
        )

        st.rerun()
else:
    st.stop()
