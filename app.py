import streamlit as st
import json
from agent import app, ask_agent
import db
from db import detect_intent

db.init_db()

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
    st.session_state.messages = db.load_messages(st.session_state.user_email)

#Greeting text
if not st.session_state.messages:
    st.session_state.messages.append({
        "role": "assistant",
        "content": "👋 Hi there! How can I help you today?"
    })

# --- Display chat history ---
for msg in st.session_state.messages:
    st.chat_message("user").write(msg["content"])
    


#Intent handlers
def handle_order(user):
    if user:
        orders = user[4] if len(user) > 5 else user[3]
        try:
            order_list = json.loads(orders) if orders else []
        except Exception:
            order_list = []
        if order_list:
            details = "\n".join([
            f"Order ID: {o['id']} | Product: {o['product']} | Qty: {o['qty']} | Price: {o['price']} | Purchase Date: {o.get('purchase_date', 'N/A')} | Status: {o.get('status', 'N/A')} | Card Ending: {o.get('card_last4', 'N/A')}"
                for o in order_list
            ])
            return f"Here are your detailed order(s):\n{details}"
        else:
            return "No orders found."
    else:
        return "Please provide your email to look up your orders."

def handle_shipping(user, user_name):
    if user:
        shipping_status = user[5] if len(user) > 5 else user[4]
        return f"Hi {user_name}, your shipping status is: **{shipping_status or 'Unknown'}**."
    else:
        return "Please provide your email to check shipping status."

def handle_billing(user, user_name):
    if user:
        return "Routing to specialized agent for 'Billing'." #place holder
    else:
        return "Please provide your email to check shipping status."

def handle_forgot_password(user, user_name):
    if user:
        return "Routing to specialized agent for 'Forgot Password'."
    else:
        return "Please provide your email to check shipping status."

# def handle_change_email(user, user_name): ##not sure if we need this option
#     if user:
#         change_email = ""
#         return "Routing to specialized agent for 'Change Email'."
#     else:
#         return "Please provide your email to check shipping status."

def handle_change_address(user, user_name):
    if user:
        return "Routing to specialized agent for 'Change Address'."
    else:
        return "Please provide your email to check shipping status."

def handle_refund(user, user_name):
    if user:
        return "Routing to specialized agent for 'Refund'."
    else:
        return "Please provide your email to check shipping status."


def handle_live_agent(user, user_name):
    if user:
        return "Routing to specialized agent for 'Message live Agent'."
    else:
        return "Please provide your email to check shipping status."

def handle_memory(user, user_email):
    # if user_email:
    #     history = db.load_messages(user_email)
    #     reply = ""
    #     for msg in history:
    #         role_color = "blue" if msg["role"] == "user" else "green"
    #         reply += f"<div style='color:{role_color}'><b>{msg['role'].title()}:</b> {msg['content']}</div>\n"
    #     return reply or "No chat history found."
    # else:
    #     return "No chat history found."
    if user:
        return "Fetching chat history Please wait...."
    else:
        return "Please provide your email to check shipping status."

INTENT_HANDLERS = {
    "check order": lambda user, user_name: handle_order(user),
    "shipping status": lambda user, user_name: handle_shipping(user, user_name),
    "billing": handle_billing,
    "forgot password": handle_forgot_password,
    # "change email": handle_change_email,
    "change address": handle_change_address,
    "refund": handle_refund,
    "live agent": handle_live_agent,
    "memory": lambda user, user_name: handle_memory(st.session_state.user_email),
}

def handle_option(option, from_chat=False):
    user_email = st.session_state.user_email
    user_name = st.session_state.user_name or "Customer"
    user = db.get_user_by_email(user_email) if user_email else None
    normalized = option.replace('_', ' ').lower()
    handler = INTENT_HANDLERS.get(normalized)
    if handler:
        reply = handler(user, user_name)
    else:
        reply = ask_agent(option, email=user_email)
    if user_email and not from_chat:
        st.session_state.messages.append({"role": "user", "content": option})
        st.session_state.messages.append({"role": "assistant", "content": reply})
        db.save_message(user_email, "assistant", reply)
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
        user = db.get_user_by_email(user_email)
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

    #Input requires email but email not provided yet
    elif any(kw in prompt_lower for kw in [
        "shipping", "track", "delivery", "order", "purchase",
        "billing", "invoice", "refund", "change address", "change email",
        "password"
    ]) and not st.session_state.user_email:
        st.session_state.last_intent = prompt_lower
        reply = "To help with your order, shipping, billing, refund, or address change, please provide your email."

    #User has email, handle known keywords
    elif st.session_state.user_email:
        intent = detect_intent(prompt_lower)
        if intent:
            reply = handle_option(intent, from_chat=True)
        else:
            reply = ask_agent(prompt, email=st.session_state.user_email)

    #Fallback to AI
    else:
        reply = ask_agent(prompt, email=st.session_state.user_email)

    #Save messages
    if st.session_state.user_email:
        db.save_message(st.session_state.user_email, "user", prompt)
        db.save_message(st.session_state.user_email, "assistant", reply)

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
    


