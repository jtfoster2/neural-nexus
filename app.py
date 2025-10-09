import streamlit as st
import uuid
import json
import time
import db
from supervisor import ask_agent

if "db_initialized" not in st.session_state:
    db.init_db()
    st.session_state.db_initialized = True
    db.add_user("demo@example.com", "hashed_pw", "Demo", "User", "+15555550123")
    db.add_order("ord_001", "demo@example.com", subtotal_cents=1000, tax_cents=80, shipping_cents=150, shipping_address="123 Demo St, Atlanta, Ga 30318", status="shipped")
    db.add_order_item("ord_001", "SKU-001", "Widget", 2, 500)
    db.add_payment("pay_001", "demo@example.com", "ord_001", 1080, status="succeessful")
    db.add_conversation("conv_001", "demo@example.com", "User: Hi\nAssistant: Hello!")
    print (db.get_all_users())  #DEBUGGING    


    print("Example data seeded.")

st.set_page_config(page_title="Customer Support Agent", layout="wide")


# --- Session setup ---
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

def handle_option(option, from_chat=False):
    user_email = st.session_state.user_email
    reply = ask_with_spinner(option, st.session_state.conversation_id, email=user_email)
    if user_email and not from_chat:
        st.session_state.messages.append({"role": "user", "content": option})
        st.session_state.messages.append({"role": "assistant", "content": reply})
        db.add_conversation(
            conversation_id=st.session_state.conversation_id,
            email=st.session_state.user_email,
            conversation_text=json.dumps(st.session_state.messages)
        )
        st.rerun()
    return reply

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
    