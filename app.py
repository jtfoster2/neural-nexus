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
from agents.general_agent import summarize_conversation
from agents import message_agent as msg



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


# --- Email prompt; Authentication (before sidebar and chat) ---
if not st.session_state.user_email:
    
    # --- Modern Landing Page ---
    # Load logo before rendering container to prevent empty container flash
    logo_file = Path("Capgemini.png")
    if not logo_file.exists():
        st.error("Capgemini.png not found in working directory.")
        b64 = ""
    else:
        b64 = base64.b64encode(logo_file.read_bytes()).decode()
    # Only render container after logo is loaded
    if b64 or not logo_file.exists():
        with st.container(border=True):
            st.markdown(f"""
            <div style='max-width: 500px; width: 100%; margin: 0 auto;'>
                <div style='background: #fff; border-radius: 12px; padding: 0; display: flex; justify-content: center; align-items: center; margin-bottom: 24px;'>
                    <img src='data:image/png;base64,{b64}' width='240' style='display:block; border-radius: 12px; background: #fff;'>
                </div>
                <h3 style='color:#007bff; font-size:1.25rem; font-weight:500; text-align:center; margin-bottom:24px;'>AI Customer Support for Modern Businesses</h3>
                <p style='color:#495057; font-size:1.1rem; text-align:center; margin-bottom:32px;'>Delivering instant, reliable, and friendly support for your customers. Try our intelligent chat, seamless account management, and more.</p>
            </div>
            """, unsafe_allow_html=True)
            col1, col2, col3 = st.columns([1,2,1])
            with col2:
                login_clicked = st.button("Login", use_container_width=True, key="welcome_login")
                signup_clicked = st.button("Sign up", use_container_width=True, key="welcome_signup")
                guest_clicked = st.button("Continue as Guest", use_container_width=True, key="welcome_guest")
            st.markdown("<div style='text-align:center; color:#6c757d; font-size:0.95rem; margin-bottom:0;'>No account needed to try our services!</div>", unsafe_allow_html=True)
            st.markdown("<div style='text-align:center; color:#adb5bd; font-size:0.75rem; margin-top:18px; margin-bottom:3px;'>Designed by Neural Nexus</div>", unsafe_allow_html=True)

    # --- Login Dialog ---
    if login_clicked:
        @st.dialog("Login")
        def login_dialog():
            st.markdown(f"""
            <div style='max-width: 400px; width: 100%; margin: 0 auto;'>
                <div style='background: #fff; border-radius: 12px; padding: 8px; display: flex; justify-content: center; align-items: center; margin-bottom: 12px;'>
                    <img src='data:image/png;base64,{b64}' width='180' style='display:block; border-radius: 12px; background: #fff;'>
                </div>
                <h3 style='color: #2c3e50; margin-bottom: 8px; font-weight: 600; text-align:center;'>Welcome Back!</h3>
                <p style='color: #6c757d; text-align:center;'>Sign in to your account</p>
            </div>
            """, unsafe_allow_html=True)
            with st.form("login_form"):
                login_email = st.text_input("Email or Phone Number", key="login_email", placeholder="Enter your email or phone number")
                login_password = st.text_input("Password", type="password", key="login_password", placeholder="Enter your password")
                if st.form_submit_button("Login", use_container_width=True):
                    if not login_email or not login_password:
                        st.error("Please enter both email/phone and password.")
                    else:
                        success, message, user_email = auth.login(login_email.strip(), login_password)
                        if success:
                            st.session_state.user_email = user_email
                            st.session_state.user_name = auth.get_user_display_name(user_email)
                            st.session_state.chat_started = True
                            st.success(f"Welcome back, {st.session_state.user_name}!")
                            st.rerun()
                        else:
                            st.error(message)
            st.markdown("<div style='height: 10px'></div>", unsafe_allow_html=True)
            if st.button("Forgot password?", type="tertiary", use_container_width=True, key="login_forgot_password_dialog"):
                st.session_state.show_reset_form = True
                st.rerun()
        login_dialog()

    # --- Signup Dialog ---
    if signup_clicked:
        @st.dialog("Sign up")
        def signup_dialog():
            st.markdown(f"""
            <div style='max-width: 400px; width: 100%; margin: 0 auto;'>
                <div style='background: #fff; border-radius: 12px; padding: 8px; display: flex; justify-content: center; align-items: center; margin-bottom: 12px;'>
                    <img src='data:image/png;base64,{b64}' width='180' style='display:block; border-radius: 12px; background: #fff;'>
                </div>
                <h3 style='color: #2c3e50; margin-bottom: 8px; font-weight: 600; text-align:center;'>Create an Account</h3>
                <p style='color: #6c757d; text-align:center;'>Join CapeGemini AI Customer Service today</p>
            </div>
            """, unsafe_allow_html=True)
            with st.container(border=True):
                col1, col2 = st.columns(2)
                with col1:
                    su_first = st.text_input("First name", key="su_first", placeholder="Enter your first name")
                with col2:
                    su_last = st.text_input("Last name", key="su_last", placeholder="Enter your last name")
                su_email = st.text_input("Email", key="su_email", placeholder="Enter your email address")
                su_phone = st.text_input("Phone (optional)", key="su_phone", placeholder="e.g., +15555550123")
                col3, col4 = st.columns(2)
                with col3:
                    su_password = st.text_input("Password", type="password", key="su_password", placeholder="Create a password")
                with col4:
                    su_confirm = st.text_input("Confirm password", type="password", key="su_confirm", placeholder="Confirm your password")
                st.markdown("<div style='height: 10px'></div>", unsafe_allow_html=True)
                if st.button("Create Account", use_container_width=True, key="signup_create_account_dialog"):
                    if not su_email or not su_password:
                        st.error("Please provide both email and password to create an account.")
                    elif su_password != su_confirm:
                        st.error("Passwords do not match.")
                    else:
                        success, message = auth.signup(
                            su_email.strip().lower(),
                            su_password,
                            su_first or None,
                            su_last or None,
                            (su_phone.strip() if su_phone and su_phone.strip() else None)
                        )
                        if success:
                            st.session_state.user_email = su_email.strip().lower()
                            st.session_state.user_name = auth.get_user_display_name(su_email.strip().lower())
                            st.session_state.chat_started = True
                            st.success("Account created and logged in.")
                            st.rerun()
                        else:
                            st.error(message)
        signup_dialog()

    # --- Guest Dialog ---
    if guest_clicked:
        @st.dialog("Continue as Guest")
        def guest_dialog():
            st.markdown(f"""
            <div style='max-width: 400px; width: 100%; margin: 0 auto;'>
                <div style='background: #fff; border-radius: 12px; padding: 8px; display: flex; justify-content: center; align-items: center; margin-bottom: 12px;'>
                    <img src='data:image/png;base64,{b64}' width='180' style='display:block; border-radius: 12px; background: #fff;'>
                </div>
                <h3 style='color: #2c3e50; margin-bottom: 8px; font-weight: 600; text-align:center;'>Continue as Guest</h3>
                <p style='color: #6c757d; text-align:center;'>Try our services without creating an account</p>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Start as Guest", use_container_width=True, key="guest_start_dialog"):
                st.session_state.chat_started = True
                st.session_state.user_name = "Guest"
                st.session_state.user_email = " "
                st.success(f"Welcome, {st.session_state.user_name}!")
                st.rerun()
        guest_dialog()

    # --- Reset Password Dialog ---
    if st.session_state.get("show_reset_form"):
        @st.dialog("Reset Password")
        def reset_password_dialog():
            st.markdown(f"""
            <div style='max-width: 400px; width: 100%; margin: 0 auto;'>
                <div style='background: #fff; border-radius: 12px; padding: 8px; display: flex; justify-content: center; align-items: center; margin-bottom: 12px;'>
                    <img src='data:image/png;base64,{b64}' width='180' style='display:block; border-radius: 12px; background: #fff;'>
                </div>
                <h3 style='color: #2c3e50; margin-bottom: 8px; font-weight: 600; text-align:center;'>Reset Password</h3>
                <p style='color: #6c757d; text-align:center;'>Enter your details to reset your password</p>
            </div>
            """, unsafe_allow_html=True)
            with st.form("reset_password_form_dialog"):
                fp_email = st.text_input("Account Email", key="fp_email", placeholder="Enter your account email")
                fp_new = st.text_input("New Password", type="password", key="fp_new", placeholder="Enter new password")
                fp_confirm = st.text_input("Confirm Password", type="password", key="fp_confirm", placeholder="Confirm new password")
                st.markdown("<div style='height: 10px'></div>", unsafe_allow_html=True)
                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("Reset Password", use_container_width=True):
                        if not fp_email or not fp_new:
                            st.error("Please provide your email and new password.")
                        elif fp_new != fp_confirm:
                            st.error("Passwords do not match.")
                        else:
                            ok, msg = auth.reset_password(fp_email.strip().lower(), fp_new)
                            if ok:
                                st.success(msg)
                                st.session_state.show_reset_form = False
                                st.rerun()
                            else:
                                st.error(msg)
                with col2:
                    if st.form_submit_button("Back to Login", use_container_width=True):
                        st.session_state.show_reset_form = False
                        st.rerun()
        reset_password_dialog()

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

        
if st.session_state.get("page") == "history":
    ph = st.empty()

    #Does ALL loading/computation off-screen inside spinner (writes nothing until done)
    with ph.container():
        with st.spinner("Loading chat history..."):
            email = st.session_state.get("user_email")
            rows = db.list_conversations_for_user(email) if email else []
            prepared = []  # (header, started_at, messages)

            for row in rows or []:
                r = dict(row)
                conv_id = r["conversation_id"]
                started_at = r.get("started_at") or ""
                header = summarize_conversation(conv_id)  # fast model; cached if you like
                messages = _parse_conversation_text(r.get("conversation_text") or "")
                prepared.append((header, started_at, messages))

    
    ph.empty()
    st.title("💬 Chat History")

    if not email:
        st.info("Log in to view your history.")
    elif not prepared:
        st.info("No past conversations found.")
        st.markdown("---")
        if st.button("⬅️ Back to chat", key="history_back_to_chat_empty"):
            st.session_state.page = "chat"
            st.rerun()
    else:
        for header, started_at, messages in prepared:
            title = header + (f" — {started_at}" if started_at else "")
            with st.expander(title, expanded=False):
                if not messages:
                    st.write("_(empty conversation)_")
                else:
                    for msg in messages:
                        role = msg.get("role") if msg.get("role") in {"user","assistant"} else "assistant"
                        st.chat_message(role).write(msg.get("content",""))

        st.markdown("---")
        if st.button("⬅️ Back to chat", key="history_back_to_chat"):
            st.session_state.page = "chat"
            st.rerun()

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

    

    # settings button  ** disabled for guest users **
    user_email = st.session_state.get("user_email", "")
    is_guest = (not user_email) or user_email.strip() == ""
    # print(f"[DEBUG] user_email: '{user_email}', is_guest: {is_guest}")  #DEBUG
    history_clicked = st.button("💬 Chat History", key="chat_history", type="tertiary", disabled=is_guest)
    settings_clicked = st.button("⚙️ Settings", key="settings", type="tertiary", disabled=is_guest)
    
    # only show logout if user_email exists
    logout_clicked = None
    if st.session_state.get("user_email"):
        logout_clicked = st.button("⏻ Log Out", key="logout", type="tertiary")

    # button actions
    if history_clicked:
        st.session_state.page = "history"
        st.rerun()
    if settings_clicked:
        st.session_state.page = "settings"
        st.rerun()
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
        if st.button("Back to Chat", key="page_back_to_chat_guest"):
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
                email = st.session_state.user_email

                db.set_user_first_name(st.session_state.user_email, first)
                db.set_user_last_name(st.session_state.user_email, last)
                db.set_user_phone(st.session_state.user_email, phone)
                db.set_user_address_line(st.session_state.user_email, address_line)
                db.set_user_city(st.session_state.user_email, city)
                db.set_user_state(st.session_state.user_email, state)
                db.set_user_country(st.session_state.user_email, country)
                db.set_user_zip_code(st.session_state.user_email, zip_code)
                # Notify user by email and SMS about profile update
                notification_body = "Your account profile has been updated."
                msg.message_agent({
                    "email": email,
                    "phone": phone,
                    "name": db.get_user_first_name(email) or "",
                    "event_type": "account_changed",
                    "body": notification_body,
                })
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
def offer_feedback(msg):
    col = st.columns([4,1,1,4])
    with col[1]:
        up = st.button("👍", key=f"feedback_up_{id(msg)}_{len(st.session_state.messages)}", help="Helpful", use_container_width=False)
    with col[2]:
        down = st.button("👎", key=f"feedback_down_{id(msg)}_{len(st.session_state.messages)}", help="Not Helpful", use_container_width=False)
        # Style: no visible button styling, only emoji are visible and clickable
        st.markdown(f"""
            <style>
            button[data-feedback='{id(msg)}_{len(st.session_state.messages)}'] {{
                background: none !important;
                border: none !important;
                box-shadow: none !important;
                padding: 0 !important;
                min-width: 0 !important;
                outline: none !important;
            }}
            button[data-feedback='{id(msg)}_{len(st.session_state.messages)}'] span {{
                background: none !important;
                border: none !important;
                border-radius: 0 !important;
                padding: 0 !important;
                font-size: 1.1rem;
                transition: none;
            }}
            button[data-feedback='{id(msg)}_{len(st.session_state.messages)}']:hover span {{
                text-shadow: 0 0 4px #2222;
            }}
            </style>
        """, unsafe_allow_html=True)
    if up:
        db.add_feedback(
            email=st.session_state.user_email,
            conversation_id=st.session_state.conversation_id,
            message=msg["content"],
            feedback_type="up"
        )
        st.success("Thank you for your feedback!")
    if down:
        db.add_feedback(
            email=st.session_state.user_email,
            conversation_id=st.session_state.conversation_id,
            message=msg["content"],
            feedback_type="down"
        )
        st.success("Thank you for your feedback!")
if st.session_state.user_email:
    #st.caption(f"Session ID: `{st.session_state.conversation_id}`") #DEBUGGING
    st.write(f"User: `{st.session_state.user_email}`")

#Greeting text
if not st.session_state.messages:
    st.session_state.messages.append({
        "role": "assistant",
        "content": "👋 Hi there! How can I help you today?"
    })

#Load user chat history           
if st.session_state.user_email and not st.session_state.messages:
    st.session_state.messages = db.list_conversations_for_user(st.session_state.user_email)

# --- Display chat history ---
for msg in st.session_state.messages:
    role = (msg.get("role") or "assistant").lower()
    if role not in {"user", "assistant"}:
        role = "assistant"
    st.chat_message(role).write(msg["content"])
    # Show tiny thumbs feedback only for assistant messages after the most recent user message
    idx = st.session_state.messages.index(msg)
    # Find the last user message
    last_user_idx = None
    for i in range(len(st.session_state.messages)-1, -1, -1):
        if (st.session_state.messages[i].get("role") or "assistant").lower() == "user":
            last_user_idx = i
            break
    # Show thumbs for the first actionable assistant message after a user message
    if last_user_idx is not None:
        # Find the first actionable assistant message after last user message
        found = False
        for j in range(last_user_idx + 1, len(st.session_state.messages)):
            m = st.session_state.messages[j]
            r = (m.get("role") or "assistant").lower()
            content = (m.get("content") or "").lower()
            is_actionable = not ("routing to" in content or "routing..." in content or "route to" in content or "transferring" in content)
            if r == "assistant" and is_actionable:
                if msg == m:
                    offer_feedback(msg)
                found = True
                break

# --- Feedback helper function ---
def offer_feedback(msg):
    col = st.columns([3,2,3])
    with col[1]:
        up = st.button("👍", key=f"feedback_up_{id(msg)}_{len(st.session_state.messages)}", help="Helpful", use_container_width=True)
        down = st.button("👎", key=f"feedback_down_{id(msg)}_{len(st.session_state.messages)}", help="Not Helpful", use_container_width=True)
        if up:
            db.add_feedback(
                email=st.session_state.user_email,
                conversation_id=st.session_state.conversation_id,
                message=msg["content"],
                feedback_type="up"
            )
            st.success("Thank you for your feedback!")
        if down:
            db.add_feedback(
                email=st.session_state.user_email,
                conversation_id=st.session_state.conversation_id,
                message=msg["content"],
                feedback_type="down"
            )
            st.success("Thank you for your feedback!")
        

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
        if st.button("Change Name", use_container_width=True, key="chat_change_name"):
            st.session_state.pending_prompt = "Change Name"
            st.rerun()
    with col2:
        if st.button("Change Phone", use_container_width=True, key="chat_change_phone"):
            st.session_state.pending_prompt = "Change Phone Number"
            st.rerun()
    with col3:
        if st.button("Change Address", use_container_width=True, key="chat_change_address"):
            st.session_state.pending_prompt = "Change Address"
            st.rerun()
    with col4:
        if st.button("Live Agent", use_container_width=True, key="chat_live_agent"):
            st.session_state.pending_prompt = "Live Agent"
            st.rerun()
    
    col5, col6, col7, col8 = st.columns(4)
    with col5:
        if st.button("Shipping Status", use_container_width=True, key="chat_shipping_status"):
            st.session_state.pending_prompt = "Shipping Status"
            st.rerun()
    with col6:
        if st.button("Check Order", use_container_width=True, key="chat_check_order"):
            st.session_state.pending_prompt = "Check Order"
            st.rerun()
    with col7:
        if st.button("Refund", use_container_width=True, key="chat_refund"):
            st.session_state.pending_prompt = "Refund"
            st.rerun()
    with col8:
        if st.button("Billing", use_container_width=True, key="chat_billing"):
            st.session_state.pending_prompt = "Billing"
            st.rerun()