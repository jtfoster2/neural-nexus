import bcrypt
import db
from agents import message_agent as msg
from typing import Optional, Tuple

def hash_password(password: str) -> str:
    # hash a password using bcrypt
    try:
        # convert string to bytes and truncate if needed
        if isinstance(password, str):
            password = password.encode('utf-8')
        if len(password) > 72:
            password = password[:72]
            
        # generate salt and hash password
        salt = bcrypt.gensalt()
        password_hash = bcrypt.hashpw(password, salt)
        
        # convert bytes back to string for storage
        return password_hash.decode('utf-8')
    except Exception as e:
        print(f"Hashing error: {str(e)}")
        raise

def verify_password(password: str, password_hash: str) -> bool:
    # verify a password against its hash.
    if not password_hash or not isinstance(password_hash, str):
        return False
    try:
        # convert inputs to bytes
        if isinstance(password, str):
            password = password.encode('utf-8')
        if isinstance(password_hash, str):
            password_hash = password_hash.encode('utf-8')
            
        # truncate password if needed
        if len(password) > 72:
            password = password[:72]
            
        # check password
        return bcrypt.checkpw(password, password_hash)
    except Exception as e:
        print(f"Password verification error: {str(e)}")
        return False

def signup(email: str, password: str, first_name: Optional[str] = None, last_name: Optional[str] = None, phone: Optional[str] = None) -> Tuple[bool, str]:
    
    # sign up a new user. Returns(success, message).
    
    try:
        # check if user exists
        existing_user = db.get_user(email)
        if existing_user:
            return False, "Email already registered"
        
        # optional: normalize phone and check uniqueness
        if phone is not None:
            phone = phone.strip()
            if phone == "":
                phone = None
            else:
                # ensure phone not already registered
                try:
                    existing_phone_user = db.get_user_by_phone(phone)
                except Exception:
                    existing_phone_user = None
                if existing_phone_user:
                    return False, "Phone number already registered"

        # hash password and create user
        password_hash = hash_password(password)
        
        # verify the hash is valid before storing it
        if not password_hash or len(password_hash) < 20:  # Basic validation of hash
            return False, "Error generating secure password hash"
            
        # debug to verify hash format
        print(f"Generated hash for new user {email}: {password_hash}")
        
        db.add_user(
            email=email,
            password_hash=password_hash,
            first_name=first_name,
            last_name=last_name,
            phone=phone
        )
        
        # verify the user was created properly
        new_user = db.get_user(email)
        if not new_user or not new_user['password_hash']:
            return False, "Error verifying user creation"
            
        return True, "Signup successful"
    except Exception as e:
        print(f"Signup error: {str(e)}")
        return False, f"Error creating user: {str(e)}"

def login(email_or_phone: str, password: str) -> Tuple[bool, str, Optional[str]]:
    """
    Authenticate a user by email or phone number. 
    Returns (success, message, user_email).
    user_email will be None if login fails, otherwise contains the user's email address.
    """
    try:
        user = db.get_user_by_email_or_phone(email_or_phone)
        if not user:
            return False, "User not found", None
        
        if not user['password_hash']:
            return False, "Password not set for this user", None
        
        # debug print to check the stored hash
        user_email = user['email']  # always return email for session
        print(f"Stored hash for {user_email}: {user['password_hash']}")
        
        if verify_password(password, user['password_hash']):
            return True, "Login successful", user_email
        
        return False, "Invalid password", None
    except Exception as e:
        print(f"Login error: {str(e)}")
        return False, "An error occurred during login. Please try again.", None


def reset_password(email: str, new_password: str) -> Tuple[bool, str]:
    """
    Reset a user's password. Hashes the new password and updates the DB.
    Returns (success, message).
    """
    try:
        user = db.get_user(email)
        if not user:
            return False, "User not found"

        # Hash new password and update
        password_hash = hash_password(new_password)
        if not password_hash or len(password_hash) < 20:
            return False, "Failed to generate password hash"

        db.set_user_password_hash(email, password_hash)

        msg.message_agent({ #sends notification email to user
            "email": email,
            "name": db.get_user_first_name(email) or "",
            "event_type": "account_password_changed",
        })
        return True, "Password updated successfully"
    except Exception as e:
        print(f"Reset password error: {str(e)}")
        return False, f"Error resetting password: {str(e)}"

def get_user_display_name(email: str) -> str:
    # get users display name from first_name or email
    user = db.get_user(email)
    if not user:
        return email
    
    if user['first_name']:
        return user['first_name']
    return email.split('@')[0]