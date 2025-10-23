import streamlit as st
import uuid
import json
import time
import db
from supervisor import ask_agent_events

# --- Session setup ---
if "db_initialized" not in st.session_state:
    db.init_db()
    st.session_state.db_initialized = True

if "user_email" not in st.session_state:
    st.session_state.user_email = None

if "user_name" not in st.session_state:
    st.session_state.user_name = None

if "chat_started" not in st.session_state:  
    st.session_state.chat_started = False   

if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

#Sidebar
with st.sidebar:
    #use columns to center the image
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image("robot_icon.png", width=100)

    
    # st.title("AI Customer Service")
    # st.write("How can we help you today?")
    
    #centered title and subtitle
    st.markdown("<h3 style='text-align: center;'>AI Customer Service</h3>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>How can we help you today?</p>", unsafe_allow_html=True)

    #use column to center the startchat button
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("Start Chat"):
            st.session_state.chat_started = True
    st.markdown("---")
    st.markdown("""
    <style>
    .custom-button {
        background-color: rgba(0,0,0,0);
        border: none;
        color: black;
        padding: 10px 20px;
        text-decoration: none;
        display: inline-block;
        font-size: 16px;
        margin: 5px;
        cursor: pointer;
        border-radius: 5px;
    }
    .custom-button:hover {
        background-color: rgba(0,0,0,0.15)
    }
    </style>
    <div style='text-align: left;'>
        <button class='custom-button'>💬 Chat History</button>
        <button class='custom-button'>⚙️ Settings</button>
        <button class='custom-button'>⏻ Log Out</button>
    </div>
    
    """, unsafe_allow_html=True)


#Stop if chat not started         
if not st.session_state.chat_started:
    st.info("Click **Start Chat** in the sidebar to begin.")
    st.stop()

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

#Load user chat history           
if st.session_state.user_email and not st.session_state.messages:
    st.session_state.messages = db.list_conversations_for_user(st.session_state.user_email)
    print(st.session_state.messages)  #DEBUGGING

# --- Display chat history ---
for msg in st.session_state.messages:
    role = (msg.get("role") or "assistant").lower()
    if role not in {"user", "assistant"}:
        role = "assistant"
    st.chat_message(role).write(msg["content"])

# --- Email prompt ---
if not st.session_state.user_email:
    st.info("Please enter your email to begin.")
    email = st.text_input("Email address", placeholder="you@example.com")
    if email:
        st.session_state.user_email = email.strip().lower()
        st.success(f"Welcome, {st.session_state.user_email}!")
        st.rerun()

    if st.button("Continue as Guest"):
        st.session_state.chat_started = True
        st.session_state.user_name = "Guest"
        st.session_state.user_email = " "
        st.success(f"Welcome, {st.session_state.user_name}!")
        st.rerun()
def send_message_to_agent(prompt: str):

    user = db.get_user(st.session_state.user_email)
    if not user:
        db.add_user(st.session_state.user_email)

    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)


    routing_shown = False
    final_reply = None

    with st.spinner("Thinking…"):
        
        start = time.time()
        elapsed = time.time() - start # Enforce a minimum of 3s delay for realism
        if elapsed < 3:
            time.sleep(3 - elapsed)

        for kind, text in ask_agent_events(
            prompt,
            st.session_state.conversation_id,
            st.session_state.user_email
        ):
            if kind == "routing" and not routing_shown:
                # show routing as its own bubble and persist it
                st.chat_message("assistant").write(f"{text}")
                st.session_state.messages.append({"role": "assistant", "content": f"{text}"})
                routing_shown = True
            elif kind == "output":
                # final answer bubble + persist
                st.chat_message("assistant").write(text)
                st.session_state.messages.append({"role": "assistant", "content": text})
                final_reply = text

    db.add_conversation(
        conversation_id=st.session_state.conversation_id,
        email=st.session_state.user_email,
        conversation_text=json.dumps(st.session_state.messages)
    )

    st.rerun()

    return final_reply

    
# --- Chat input ---
if st.session_state.user_email:
    prompt = st.chat_input("Ask me anything about your order, billing, etc.")
    if prompt:
        send_message_to_agent(prompt)
    if st.session_state.get("pending_prompt"):
        pending_prompt = st.session_state.pop("pending_prompt")
        send_message_to_agent(pending_prompt)
else:
    st.stop()

def handle_option(option, from_chat=False): ####Modified to handle quick option buttons with streaming reply####
    user_email = st.session_state.user_email

    routing_shown = False
    final_reply = None

    with st.spinner("Thinking…"):
        for kind, text in ask_agent_events(option, st.session_state.conversation_id, email=user_email):
            if kind == "routing" and not routing_shown:
                if user_email and not from_chat:
                    st.session_state.messages.append({"role": "user", "content": option})
                st.chat_message("assistant").write(f"{text}")
                start = time.time()
                elapsed = time.time() - start
                # Enforce a minimum of 3s delay for realism
                if elapsed < 3:
                    time.sleep(3 - elapsed)
                st.session_state.messages.append({"role": "assistant", "content": f"{text}"})
                routing_shown = True
            elif kind == "output":
                st.chat_message("assistant").write(text)
                st.session_state.messages.append({"role": "assistant", "content": text})
                final_reply = text

    db.add_conversation(
        conversation_id=st.session_state.conversation_id,
        email=st.session_state.user_email,
        conversation_text=json.dumps(st.session_state.messages)
    )
    st.rerun()
    return final_reply


#Quick Options Menu
if st.session_state.user_email:
    st.markdown("---")
    st.markdown("#### Quick Options")
    col1, col2, col3, col4 = st.columns(4)
    def handle_option_button(option):
        handle_option(option)
    with col1:
        if st.button("Forgot Password", use_container_width=True):
            st.session_state.pending_prompt = "Forgot Password"
            st.rerun()
    with col2:
        if st.button("Refund", use_container_width=True):
            st.session_state.pending_prompt = "Refund"
            st.rerun()
    with col3:
        if st.button("Check Order", use_container_width=True):
            st.session_state.pending_prompt = "Check Order"
            st.rerun()
    with col4:
        if st.button("Shipping Status", use_container_width=True):
            st.session_state.pending_prompt = "Shipping Status"
            st.rerun()
    col5, col6, col7 = st.columns(3)
    with col5:
        if st.button("Change Address", use_container_width=True):
            st.session_state.pending_prompt = "Change Address"
            st.rerun()
    with col6:
        if st.button("Live Agent", use_container_width=True):
            st.session_state.pending_prompt = "Live Agent"
            st.rerun()
    with col7:
        if st.button("Billing", use_container_width=True):
            st.session_state.pending_prompt = "Billing"
            st.rerun()
