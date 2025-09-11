import sqlite3, os
from datetime import datetime


DB_FILE = "users.db"

def init_db():
    """Initialize the SQLite database and create tables if they don't exist."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        last_option TEXT,
        orders TEXT,
        shipping_status TEXT          
    )
    """)

    #chat messages table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_name TEXT,
        role TEXT,
        content TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    #event log table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS event_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        timestamp DATETIME,
        event_type TEXT,
        event_detail TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)
    conn.commit()
    conn.close()

def add_user(name, email, orders=None, shipping_status=None, last_option=None):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (name, email, orders, shipping_status, last_option) VALUES (?, ?, ?, ?, ?)",
        (name, email, orders, shipping_status, last_option)
    )
    conn.commit()
    conn.close()

def get_user_by_email(email):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()
    return user

def update_user_last_option(email, last_option):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET last_option = ? WHERE email = ?", (last_option, email))
    conn.commit()
    conn.close()

def log_event(user_id, event_type, event_detail=""):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO event_log (user_id, timestamp, event_type, event_detail) VALUES (?, ?, ?, ?)",
        (user_id, datetime.now(), event_type, event_detail)
    )
    conn.commit()
    conn.close()


def clear_all_users():
    """Delete all users and their chat messages from the database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users")
    cursor.execute("DELETE FROM chat_messages")
    conn.commit()
    conn.close()

def save_message(user_name, role, message):
    #convert list/tuple to string
    if isinstance(message, (tuple, list)):
        msg_to_save = " ".join(str(m) for m in message)
    else:
        msg_to_save = str(message)

    conn = sqlite3.connect(DB_FILE)  #use same DB_FILE as init_db
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO chat_messages (user_name, role, content) VALUES (?, ?, ?)",
        (user_name, role, msg_to_save)
    )
    conn.commit()
    conn.close()



def load_messages(user_name):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role, content FROM chat_messages WHERE user_name = ? ORDER BY id",
        (user_name,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [{"role": role, "content": content} for role, content in rows]

def update_user_order(email, orders=None, shipping_status=None):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    if orders:
        cursor.execute("UPDATE users SET orders = ? WHERE email = ?", (orders, email))
    if shipping_status:
        cursor.execute("UPDATE users SET shipping_status = ? WHERE email = ?", (shipping_status, email))
    conn.commit()
    conn.close()

def get_user_orders(email):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT orders, shipping_status FROM users WHERE email = ?", (email,))
    result = cursor.fetchone()
    conn.close()
    return result if result else (None, None)

#this is to detect keywords when users type-in the input
INTENT_KEYWORDS = {
    "check order": ["order", "orders", "check order", "my order", "track order"],
    "shipping status": ["shipping", "delivery", "where is my package", "track shipping"],
    "billing": ["billing", "payment", "charge", "invoice"],
    "change address": ["change address", "update address", "new address"],
    "change email": ["change email", "update email", "new email"],
    "forgot password": ["forgot password", "reset password", "lost password", "password"],
    "refund": ["refund", "return", "money back"],
    "email agent": ["email agent", "send email"],
    "message live agent": ["live agent", "human agent", "chat with agent"],
    "memory": ["history", "memory", "chat history"]
}

def detect_intent(user_input: str):
    """Match user input against keywords to detect intent."""
    text = user_input.lower()
    for intent, keywords in INTENT_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return intent
    return None


init_db()

#mock data for users
if __name__ == "__main__":
    init_db()
    clear_all_users()

    add_user(
        "Panda",
        "panda@example.com",
        '[{"id":"ORD001","product":"Mouse","qty":2,"price":"$29.99","purchase_date":"2025-09-01","status":"Delivered","card_last4":"1234"}]',
        "Delivered"
    )
    add_user(
        "Alice Johnson",
        "alice.johnson@example.com",
        '[{"id":"ORD002","product":"Keyboard","qty":1,"price":"$49.99","purchase_date":"2025-09-05","status":"Preparing","card_last4":"5678"}]',
        "Preparing"
    )
    add_user(
        "Bob Smith",
        "bob.smith@example.com",
        '[{"id":"ORD003","product":"USB-C Charger","qty":3,"price":"$19.99","purchase_date":"2025-09-07","status":"Shipped","card_last4":"9876"}]',
        "Shipped"
    )

    print("Database initialized and mock users added!")