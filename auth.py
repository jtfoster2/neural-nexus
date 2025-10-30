import bcrypt
import db
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

def signup(email: str, password: str, first_name: Optional[str] = None, last_name: Optional[str] = None) -> Tuple[bool, str]:
    
    # sign up a new user. Returns(success, message).
    
    try:
        # check if user exists
        existing_user = db.get_user(email)
        if existing_user:
            return False, "Email already registered"
        
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
            last_name=last_name
        )
        
        # verify the user was created properly
        new_user = db.get_user(email)
        if not new_user or not new_user['password_hash']:
            return False, "Error verifying user creation"
            
        return True, "Signup successful"
    except Exception as e:
        print(f"Signup error: {str(e)}")
        return False, f"Error creating user: {str(e)}"

def login(email: str, password: str) -> Tuple[bool, str]:
    
    # authenticate a user. Returns(success, message)
    try:
        user = db.get_user(email)
        if not user:
            return False, "User not found"
        
        if not user['password_hash']:
            return False, "Password not set for this user"
        
        # debug print to check the stored hash
        print(f"Stored hash for {email}: {user['password_hash']}")
        
        if verify_password(password, user['password_hash']):
            return True, "Login successful"
        
        return False, "Invalid password"
    except Exception as e:
        print(f"Login error: {str(e)}")
        return False, "An error occurred during login. Please try again."


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