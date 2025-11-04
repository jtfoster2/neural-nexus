import streamlit as st
import uuid
import json
import time
import db
from supervisor import ask_agent_events
import auth
import base64
from pathlib import Path
from datetime import datetime


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

if "page" not in st.session_state:
    st.session_state.page = "chat"


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

# ------- Chat History Functions -------

def _parse_conversation_text(raw: str):
    """
    Accepts either the JSON we save (list[{"role","content"}]) or a plain text seed like:
    "User: Hi\nAssistant: Hello!"
    Returns a list of dicts [{role, content}, ...]
    """
    if not raw:
        return []
    # Try JSON first
    try:
        data = json.loads(raw)
        if isinstance(data, list) and all(isinstance(x, dict) and "content" in x for x in data):
            # Ensure roles are sane
            out = []
            for x in data:
                role = (x.get("role") or "assistant").lower()
                if role not in {"user", "assistant"}:
                    role = "assistant"
                out.append({"role": role, "content": x.get("content", "")})
            return out
    except Exception:
        pass

    # Fallback: plain text "User:" / "Assistant:" format
    out = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.lower().startswith("user:"):
            out.append({"role": "user", "content": line[5:].strip()})
        elif line.lower().startswith("assistant:"):
            out.append({"role": "assistant", "content": line[10:].strip()})
        else:
            # Append to last message if possible
            if out:
                out[-1]["content"] += ("\n" + line)
            else:
                out.append({"role": "assistant", "content": line})
    return out

def render_chat_history_page():
    st.title("💬 Chat History")

    email = st.session_state.get("user_email")
    if not email:
        st.info("Log in to view your history.")
        return

    rows = db.list_conversations_for_user(email)  # uses email to filter
    if not rows:
        st.info("No past conversations found.")
        return

    for row in rows:
        row = dict(row)
        conv_id = row["conversation_id"]
        started_at = row.get("started_at") or ""
        # make a friendly header (timestamp may be ISO already)
        header = f"Conversation {conv_id}"
        if started_at:
            header += f" — {started_at}"

        with st.expander(header, expanded=False):
            messages = _parse_conversation_text(row.get("conversation_text") or "")
            if not messages:
                st.write("_(empty conversation)_")
            else:
                # render as simple bubbles (read-only)
                for msg in messages:
                    role = msg["role"] if msg["role"] in {"user", "assistant"} else "assistant"
                    st.chat_message(role).write(msg["content"])

    st.markdown("---")
    if st.button("⬅️ Back to chat"):
        st.session_state.page = "chat"
        st.rerun()
        
if st.session_state.get("page") == "history":
    render_chat_history_page()
    st.stop()  # prevent the live chat UI from rendering underneath

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

    # settings button  ** disabled for guest users **
    user_email = st.session_state.get("user_email", "")
    is_guest = (not user_email) or user_email.strip() == ""
    # print(f"[DEBUG] user_email: '{user_email}', is_guest: {is_guest}")  #DEBUG
    settings_clicked = st.button("⚙️ Settings", key="settings", type="tertiary", disabled=is_guest)
    
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


# --- Settings page ---
if st.session_state.get("page") == "settings" and st.session_state.get("user_email"):
    st.header("Account Settings")
    
    # check if user is a guest
    if st.session_state.user_email.strip() == " ":
        st.info("You're currently using a guest session. Please log in or sign up to manage your account settings.")
        if st.button("Back to Chat"):
            st.session_state.page = None
            st.rerun()
        st.stop()
    
    user_row = db.get_user(st.session_state.user_email)

    def _row_get(row, key):
        try:
            if row is None:
                return ""
            if isinstance(row, dict):
                return row.get(key) or ""
            return row[key] if key in row.keys() else ""
        except Exception:
            return ""

    profile_tab, security_tab = st.tabs(["Profile", "Security"])

    with profile_tab:
        # display email ** disabled **
        st.text_input("Email", value=st.session_state.user_email, disabled=True, key="page_settings_email")

        # Profile fields
        first = st.text_input("First name", value=_row_get(user_row, "first_name"), key="page_settings_first")
        last = st.text_input("Last name", value=_row_get(user_row, "last_name"), key="page_settings_last")
        phone = st.text_input("Phone", value=_row_get(user_row, "phone"), key="page_settings_phone")

        # address fields
        st.markdown("### Address")
        address_line = st.text_input("Address Line", value=_row_get(user_row, "address_line"), key="page_settings_address_line")
        city = st.text_input("City", value=_row_get(user_row, "city"), key="page_settings_city")

        col_state, col_zip = st.columns(2)
        with col_state:
            state = st.text_input("State", value=_row_get(user_row, "state"), key="page_settings_state")
        with col_zip:
            zip_code = st.text_input("Zip Code", value=_row_get(user_row, "zip_code"), key="page_settings_zip")

        country = st.text_input("Country", value=_row_get(user_row, "country"), key="page_settings_country")

        # a little breathing room before buttons
        st.markdown("<div style='height: 12px'></div>", unsafe_allow_html=True)

        # single Update button for profile and address (centered)
        spacer_left, mid, spacer_right = st.columns([1, 2, 1])
        with mid:
            # add a small spacer column between the two buttons for nicer separation
            btn_col1, spacer_mid, btn_col2 = st.columns([1, 0.2, 1])
            with btn_col1:
                update_clicked = st.button("Update", key="page_update_settings", use_container_width=True)
            with btn_col2:
                back_clicked = st.button("Back to Chat", key="page_back_to_chat", use_container_width=True)

        # buttons spacing
        st.markdown("<div style='height: 12px'></div>", unsafe_allow_html=True)

        if update_clicked:
            try:
                db.set_user_first_name(st.session_state.user_email, first)
                db.set_user_last_name(st.session_state.user_email, last)
                db.set_user_phone(st.session_state.user_email, phone)
                db.set_user_address_line(st.session_state.user_email, address_line)
                db.set_user_city(st.session_state.user_email, city)
                db.set_user_state(st.session_state.user_email, state)
                db.set_user_country(st.session_state.user_email, country)
                db.set_user_zip_code(st.session_state.user_email, zip_code)
                st.success("Profile updated")
                # keep user on the Settings page; just refresh display name in session
                st.session_state.user_name = first or st.session_state.user_name
            except Exception as e:
                st.error(f"Error updating account: {e}")

        if back_clicked:
            st.session_state.page = None
            st.rerun()

    with security_tab:
        # change Password Section
        st.subheader("Change Password")
        with st.form("change_password_form"):
            current_pw = st.text_input("Current password", type="password")
            new_pw = st.text_input("New password", type="password")
            confirm_pw = st.text_input("Confirm new password", type="password")
            pw_submit = st.form_submit_button("Update Password")

        if pw_submit:
            email = st.session_state.user_email
            user = db.get_user(email)
            # GUARD against guest or missing user
            if (not user) or (not (user["password_hash"] or "")):
                st.error("Password not set for this account.")
            elif not new_pw:
                st.error("Please enter a new password.")
            elif new_pw != confirm_pw:
                st.error("New passwords do not match.")
            elif not current_pw:
                st.error("Please enter your current password.")
            else:
                if not auth.verify_password(current_pw, user["password_hash"]):
                    st.error("Current password is incorrect.")
                else:
                    ok, msg = auth.reset_password(email, new_pw)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)

        st.markdown("---")

        # delete account section
        st.subheader("Delete Account")
        st.warning("⚠️ This action is irreversible. All your data will be permanently deleted.")

        with st.form("delete_account_form"):
            confirm_delete = st.checkbox("I understand that deleting my account is permanent")
            delete_password = st.text_input("Enter your password to confirm", type="password")
            delete_submit = st.form_submit_button("Delete My Account", type="primary")

        if delete_submit:
            email = st.session_state.user_email
            user = db.get_user(email)

            if not confirm_delete:
                st.error("Please check the confirmation box to proceed.")
            elif not delete_password:
                st.error("Please enter your password to confirm deletion.")
            elif email.strip() == " ":  # GUEST user
                st.error("Guest accounts cannot be deleted.")
            elif (not user) or (not (user["password_hash"] or "")):
                st.error("Unable to verify account.")
            elif not auth.verify_password(delete_password, user["password_hash"]):
                st.error("Password is incorrect.")
            else:
                try:
                    # delete user (CASCADE will remove orders, payments, conversations)
                    db._exec("DELETE FROM users WHERE email = ?", [email])
                    st.success("Account deleted successfully. You will be logged out.")
                    time.sleep(2)
                    # clear session and redirect to login
                    preserve = {"db_initialized": st.session_state.get("db_initialized", False)}
                    st.session_state.clear()
                    if preserve.get("db_initialized"):
                        st.session_state.db_initialized = True
                    st.rerun()
                except Exception as e:
                    st.error(f"Error deleting account: {e}")

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
        if st.button("Change Password", use_container_width=True):
            st.session_state.pending_prompt = "Change Password"
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
