import streamlit as st
import uuid
import json
import time
import db
from supervisor import ask_agent_events
import auth
import base64
from pathlib import Path

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

# CSS for signup/login
st.markdown("""
<style>
    /* Auth header styling */
    .auth-header {
        text-align: center;
        margin-bottom: 2rem;
        padding: 1rem;
        max-width: 800px;
        margin-left: auto;
        margin-right: auto;
    }
    .auth-header img {
        margin-top: 1 rem    
        margin-bottom: 1rem;
    }
    .auth-title {
        color: #2c3e50;
        font-size: 1.75rem;
        font-weight: 600;
        margin: 0.5rem 0;
    }
    
    /* Card styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
        background-color: #f1f3f4;
        padding: 10px 10px 0 10px;
        border-radius: 10px 10px 0 0;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        background-color: #ffffff;
        border-radius: 5px 5px 0 0;
        gap: 2px;
        padding: 10px 20px;
        font-weight: 500;
    }
    .stTabs [aria-selected="true"] {
        background-color: #ffffff;
        /* border-bottom: 3px solid #007bff; */
    }
    
    /* Form styling */
    .stTextInput > div > div > input {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        padding: 15px;
        border-radius: 8px;
    }
    .stTextInput > div > div > input:focus {
        /* border-color: #007bff; */
        box-shadow: 0 0 0 2px rgba(0,123,255,0.25);
    }
    
    /* Button styling */
    .stButton > button {    
        border-radius: 8px;
        padding: 10px 20px;
        font-weight: 500;
        transition: all 0.2s ease;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 2px 6px rgba(0,0,0,0.1);
    }

    /* .secondary-button > button {
        background-color: #f8f9fa;
        color: #6c757d;
    }
    .secondary-button > button:hover {
        background-color: #e9ecef;
        border-color: #dee2e6;
    } */
            
    
    /* Container styling */
    .auth-container {
        background-color: white;
        padding: 30px;
        border-radius: 12px;
        box-shadow: 0 2px 12px rgba(0,0,0,0.1);
        margin-top: 20px;
    }
    
    /* Heading styles */
    h1, h2, h3, h4, h5, h6 {
        color: #2c3e50;
        font-weight: 600;
    }
    
    /* Alert/Info styling */
    .stAlert {
        border-radius: 8px;
        padding: 15px;
    }
    
    /* Success message styling */
    .success-message {
        color: #28a745;
        padding: 10px;
        background-color: #d4edda;
        border-radius: 8px;
        margin: 10px 0;
    }
    
    /* Error message styling */
    .error-message {
        color: #dc3545;
        padding: 10px;
        background-color: #f8d7da;
        border-radius: 8px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# --- Email prompt; Authentication (before sidebar and chat) ---

# # --- Email prompt ---
# if not st.session_state.user_email:
#     st.info("Please enter your email to begin.")
#     email = st.text_input("Email address", placeholder="you@example.com")
#     if email:
#         st.session_state.user_email = email.strip().lower()
#         st.success(f"Welcome, {st.session_state.user_email}!")
#         st.rerun()

#     if st.button("Continue as Guest"):
#         st.session_state.chat_started = True
#         st.session_state.user_name = "Guest"
#         st.session_state.user_email = " "
#         st.success(f"Welcome, {st.session_state.user_name}!")
#         st.rerun()
######################

if not st.session_state.user_email:
    
    # embed Capgemini image as base64 to center it
    logo_file = Path("Capgemini.png")
    if not logo_file.exists():
        st.error("Capgemini.png not found in working directory.")
    else:
        b64 = base64.b64encode(logo_file.read_bytes()).decode()
        html = f"""
        <div style="text-align:center; margin-bottom: 1rem;">
        <img src="data:image/png;base64,{b64}" width="280" style="display:block; margin:0 auto;">
        <h2 style="color:#2c3e50; font-weight:600; margin-top:8px;">AI Customer Support</h2>
        </div>
        """
        st.markdown(html, unsafe_allow_html=True)
    # end the block of embed img as base64
    ############################################# 


    login_tab, signup_tab, guest_tab = st.tabs(["Login", "Sign up", "Continue as Guest"])

    with login_tab:
        # Initialize show_reset_form in session state if not exists
        if "show_reset_form" not in st.session_state:
            st.session_state.show_reset_form = False
            
        if not st.session_state.show_reset_form:

            # Login Form
            style='background-color: white; padding: 30px; border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.1);'
            st.markdown("""
                <div>
                    <h3 style='color: #2c3e50; margin-bottom: 10px; font-weight: 600;'>Welcome Back!</h3>
                </div>
            """, unsafe_allow_html=True)
            
            with st.container():
                st.markdown("<div style='height: 20px'></div>", unsafe_allow_html=True)

                login_email = st.text_input("Email", key="login_email", placeholder="Enter your email")
                login_password = st.text_input("Password", type="password", key="login_password", placeholder="Enter your password")
                
                # Forgot password button
                col1, col2 = st.columns([3, 1])
                with col1:
                    pass

                with col2:

                    if st.button("Forgot password?", type="tertiary", use_container_width=False):
                        st.session_state.show_reset_form = True
                        st.rerun()

                    st.markdown("<br>", unsafe_allow_html=True)

                # Login btn
                if st.button("Login", use_container_width=True):
                    if not login_email or not login_password:
                        st.error("Please enter both email and password.")
                    else:
                        success, message = auth.login(login_email.strip().lower(), login_password)
                        if success:
                            st.session_state.user_email = login_email.strip().lower()
                            st.session_state.user_name = auth.get_user_display_name(login_email.strip().lower())
                            st.session_state.chat_started = True
                            st.success(f"Welcome back, {st.session_state.user_name}!")
                            st.rerun()
                        else:
                            st.error(message)
        
        else:
            # Reset Password Form
            st.markdown("""
                <div style='background-color: white; padding: 30px; border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.1);'>
                    <h3 style='color: #2c3e50; margin-bottom: 20px; font-weight: 600;'>Reset Password</h3>
                </div>
            """, unsafe_allow_html=True)
            
            with st.container():
                st.markdown("<div style='height: 20px'></div>", unsafe_allow_html=True)
                with st.form("reset_password_form"):
                    fp_email = st.text_input("Account Email", key="fp_email", placeholder="Enter your account email")
                    fp_new = st.text_input("New Password", type="password", key="fp_new", placeholder="Enter new password")
                    fp_confirm = st.text_input("Confirm Password", type="password", key="fp_confirm", placeholder="Confirm new password")
                    
                    st.markdown("<div style='height: 10px'></div>", unsafe_allow_html=True)
                    
                    col1, col2, col3 = st.columns([1, 2, 1])
                    with col2:
                        primary_submit = st.form_submit_button("Reset Password", use_container_width=True)

                    with col2:
                        st.markdown("""
                            <div class="secondary-button">
                        """, unsafe_allow_html=True)
                        secondary_submit = st.form_submit_button("Back to Login", use_container_width=True)
                        st.markdown("</div>", unsafe_allow_html=True)
                        
                    if primary_submit:
                        if not fp_email or not fp_new:
                            st.error("Please provide your email and new password.")
                        elif fp_new != fp_confirm:
                            st.error("Passwords do not match.")
                        else:
                            ok, msg = auth.reset_password(fp_email.strip().lower(), fp_new)
                            if ok:
                                st.success(msg)
                                # Reset the form visibility and return to login
                                st.session_state.show_reset_form = False
                                st.rerun()
                            else:
                                st.error(msg)
                    
                    if secondary_submit:
                        st.session_state.show_reset_form = False
                        st.rerun()

    with signup_tab:
        st.markdown("""
            <div style='background-color: white; padding: 30px; border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.1);'>
                <h3 style='color: #2c3e50; margin-bottom: 20px; font-weight: 600;'>Create an Account</h3>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<div style='height: 20px'></div>", unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            su_first = st.text_input("First name", key="su_first", placeholder="Enter your first name")
        with col2:
            su_last = st.text_input("Last name", key="su_last", placeholder="Enter your last name")
            
        su_email = st.text_input("Email", key="su_email", placeholder="Enter your email address")
        
        # Password fields
        col3, col4 = st.columns(2)
        with col3:
            su_password = st.text_input("Password", type="password", key="su_password", placeholder="Create a password")
        with col4:
            su_confirm = st.text_input("Confirm password", type="password", key="su_confirm", placeholder="Confirm your password")
        
        st.markdown("<div style='height: 10px'></div>", unsafe_allow_html=True)
        if st.button("Create Account", use_container_width=True):
            if not su_email or not su_password:
                st.error("Please provide both email and password to create an account.")
            elif su_password != su_confirm:
                st.error("Passwords do not match.")
            else:
                success, message = auth.signup(su_email.strip().lower(), su_password, su_first or None, su_last or None)
                if success:
                    st.session_state.user_email = su_email.strip().lower()
                    st.session_state.user_name = auth.get_user_display_name(su_email.strip().lower())
                    st.session_state.chat_started = True
                    st.success("Account created and logged in.")
                    st.rerun()
                else:
                    st.error(message)

    with guest_tab:
        st.markdown("""
            <div style='background-color: white; padding: 30px; border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.1);'>
                <h3 style='color: #2c3e50; margin-bottom: 20px; font-weight: 600;'>Continue as Guest</h3>
                <p style='color: #6c757d; margin-bottom: 20px;'>You can try our services without creating an account.</p>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<div style='height: 20px'></div>", unsafe_allow_html=True)
        
        if st.button("Start as Guest", use_container_width=True):
            st.session_state.chat_started = True
            st.session_state.user_name = "Guest"
            st.session_state.user_email = " "
            st.success(f"Welcome, {st.session_state.user_name}!")
            st.rerun()

    # don't show anything else until authenticated
    st.stop()

#Sidebar
with st.sidebar:
    # center image
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image("robot_icon.png", width=100)

    st.markdown("<h3 style='text-align: center;'>AI Customer Service</h3>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>How can we help you today?</p>", unsafe_allow_html=True)
    st.markdown("---")

    
    chat_clicked = st.button("💬 Chat History", key="chat_history", type="tertiary")
    settings_clicked = st.button("⚙️ Settings", key="settings", type="tertiary")

    # only show logout if user_email exists
    logout_clicked = None
    if st.session_state.get("user_email"):
        logout_clicked = st.button("⏻ Log Out", key="logout", type="tertiary")

    # button actions
    if chat_clicked:
        st.session_state.page = "history"
    if settings_clicked:
        st.session_state.page = "settings"
    if logout_clicked:
        preserve = {"db_initialized": st.session_state.get("db_initialized", False)}
        st.session_state.clear()
        if preserve.get("db_initialized"):
            st.session_state.db_initialized = True
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
