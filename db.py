#!/usr/bin/env python3

import sqlite3
from pathlib import Path
from contextlib import closing
from typing import Optional, Iterable, Any

DB_PATH = Path(__file__).parent / "agentic_ai.db"

# ---------------------------------------------------------------
# Schema
# ---------------------------------------------------------------
SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    email               TEXT PRIMARY KEY,
    password_hash       TEXT,
    first_name          TEXT,
    last_name           TEXT,
    phone               TEXT,
    address_line        TEXT,
    city                TEXT,
    state               TEXT,
    country             TEXT,
    zip_code            TEXT,
    created_at          TEXT DEFAULT (datetime('now')),
    is_active           INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS orders (
    order_id            TEXT PRIMARY KEY,
    email               TEXT NOT NULL REFERENCES users(email) ON DELETE CASCADE,
    status              TEXT DEFAULT 'pending',
    subtotal_cents      INTEGER DEFAULT 0,
    tax_cents           INTEGER DEFAULT 0,
    shipping_cents      INTEGER DEFAULT 0,
    discount_cents      INTEGER DEFAULT 0,
    total_cents         INTEGER,
    currency            TEXT DEFAULT 'USD',
    shipping_name       TEXT,
    shipping_address    TEXT,
    created_at          TEXT DEFAULT (datetime('now')),
    updated_at          TEXT
);

CREATE TABLE IF NOT EXISTS order_items (
    order_item_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id            TEXT NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    sku                 TEXT,
    name                TEXT,
    qty                 INTEGER,
    unit_price_cents    INTEGER,
    line_total_cents    INTEGER
);

CREATE TABLE IF NOT EXISTS payments (
    payment_id          TEXT PRIMARY KEY,
    email               TEXT NOT NULL REFERENCES users(email) ON DELETE CASCADE,
    order_id            TEXT REFERENCES orders(order_id) ON DELETE SET NULL,
    amount_cents        INTEGER,
    currency            TEXT DEFAULT 'USD',
    status              TEXT,
    method              TEXT,
    provider            TEXT,
    provider_txn_id     TEXT,
    created_at          TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ai_conversations (
    conversation_id     TEXT PRIMARY KEY,
    email               TEXT NOT NULL REFERENCES users(email) ON DELETE CASCADE,
    started_at          TEXT DEFAULT (datetime('now')),
    ended_at            TEXT,
    conversation_text   TEXT
);


CREATE TABLE IF NOT EXISTS feedback (
    feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL REFERENCES users(email) ON DELETE CASCADE,
    conversation_id TEXT,
    message TEXT,
    feedback_type TEXT CHECK(feedback_type IN ('up','down')),
    created_at TEXT DEFAULT (datetime('now'))
);
"""
# ---------------------------------------------------------------
# FEEDBACK
# ---------------------------------------------------------------
def add_feedback(email: str, conversation_id: str, message: str, feedback_type: str) -> None:
    """Add a thumbs up/down feedback entry."""
    _exec(
        """
        INSERT INTO feedback (email, conversation_id, message, feedback_type)
        VALUES (?, ?, ?, ?)
        """,
        (email, conversation_id, message, feedback_type)
    )

def get_feedback_summary(email: str) -> dict:
    """Return count of thumbs up/down for a user."""
    rows = _query(
        "SELECT feedback_type, COUNT(*) as count FROM feedback WHERE email = ? GROUP BY feedback_type",
        (email,)
    )
    summary = {"up": 0, "down": 0}
    for row in rows:
        summary[row["feedback_type"]] = row["count"]
    return summary

# automatic overall feedback analytics for all users
def get_overall_feedback_summary() -> dict:
    """Return total thumbs up/down across all users."""
    rows = _query(
        "SELECT feedback_type, COUNT(*) as count FROM feedback GROUP BY feedback_type"
    )
    summary = {"up": 0, "down": 0}
    for row in rows:
        summary[row["feedback_type"]] = row["count"]
    return summary

# ---------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------
def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def _exec(sql: str, params: Iterable[Any]) -> None:
    with closing(get_connection()) as conn:
        conn.execute(sql, tuple(params))
        conn.commit()

def _query(sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
    with closing(get_connection()) as conn:
        cur = conn.execute(sql, tuple(params))
        return cur.fetchall()

def init_db() -> None:
    with closing(get_connection()) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        migrate_add_address_columns()  # call a method to add address columns if they don't exist
        migrate_add_phone_unique_index()  # enforce unique non-null phone numbers when possible
        ensure_example_data()
    print(f"Database initialized at {DB_PATH}")

def ensure_example_data():
    
    with closing(get_connection()) as conn:
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM users")
        if cur.fetchone()[0] > 0:
            print("Data is present.")
            return
        
        # Seed example users, orders, payments, conversations
        add_user("demo@example.com", "hashed_pw", "Demo", "User", "+15555550123")
        add_order("ord_001", "demo@example.com", subtotal_cents=1000, tax_cents=80, shipping_cents=150, shipping_address="123 Demo St, Atlanta, Ga 30318", status="shipped")
        add_order_item("ord_001", "SKU-001", "Widget", 2, 500)
        add_payment("pay_001", "demo@example.com", "ord_001", 1080, status="succeessful")
        add_conversation("conv_001", "demo@example.com", "User: Hi\nAssistant: Hello!")

        add_user("panda@example.com", "hashed_pw", "Panda", None, "+15551231234")
        add_order("ord_201", "panda@example.com", subtotal_cents=2998, tax_cents=180, shipping_cents=300, shipping_address="42 Dam Creek Road, San Diego, CA 92101", status="delivered")
        add_order_item("ord_201", "SKU-201", "Wireless Mouse", 2, 1499)
        add_payment("pay_201", "panda@example.com", "ord_201", 3478, status="successful", method="card", provider="stripe")
        add_conversation("conv_201", "panda@example.com", "User: Hi, is my mouse order on the way?\nAssistant: Your order ORD201 has been delivered successfully!")
        
        add_user("alice.johnson@example.com", "hashed_pw", "Alice", "Johnson", "+15553456789")
        add_order("ord_202", "alice.johnson@example.com",
                subtotal_cents=4999, tax_cents=300, shipping_cents=250,
                shipping_address="100 Peach Tree Blvd, Atlanta, GA 30318",
                status="preparing")
        add_order_item("ord_202", "SKU-202", "Mechanical Keyboard", 1, 4999)
        add_payment("pay_202", "alice.johnson@example.com", "ord_202", 5549, status="pending", method="card", provider="square")
        add_conversation("conv_202", "alice.johnson@example.com", "User: Can I change my shipping address?\nAssistant: Sure! Please provide the new address for order ORD202.")

        add_user("bob.smith@example.com", "hashed_pw", "Bob", "Smith", "+15557654321")
        add_order("ord_203", "bob.smith@example.com",subtotal_cents=5997, tax_cents=360, shipping_cents=200, shipping_address="9 Charger Way, Austin, TX 78701", status="shipped")
        add_order_item("ord_203", "SKU-203", "USB-C Charger", 3, 1999)
        add_payment("pay_203", "bob.smith@example.com", "ord_203", 6557, status="successful", method="paypal", provider="paypal")
        add_conversation("conv_203", "bob.smith@example.com", "User: Has my charger shipped yet?\nAssistant: Your order ORD203 has been shipped and is on the way!")

        conn.commit()
        print("Example data seeded.")


# ---------------------------------------------------------------
# USERS
# ---------------------------------------------------------------
def add_user(email: str, password_hash: Optional[str] = None,
             first_name: Optional[str] = None, last_name: Optional[str] = None,
             phone: Optional[str] = None, is_active: int = 1) -> None:
    _exec("""
        INSERT OR REPLACE INTO users (email, password_hash, first_name, last_name, phone, is_active)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (email.lower(), password_hash, first_name, last_name, phone, is_active))
    print(f"User {email} added/updated.")

def get_user(email: str) -> Optional[sqlite3.Row]:
    rows = _query("SELECT * FROM users WHERE email = ?", (email.lower(),))
    print(f"User {email} retrieved.")
    return rows[0] if rows else None

def get_user_by_phone(phone: str) -> Optional[sqlite3.Row]:
    rows = _query("SELECT * FROM users WHERE phone = ?", (phone,))
    print(f"User with phone {phone} retrieved.")
    return rows[0] if rows else None

def get_user_by_email_or_phone(identifier: str) -> Optional[sqlite3.Row]:
    #try email first
    user = get_user(identifier)
    if user:
        return user
    #then phone
    return get_user_by_phone(identifier)


def get_all_users() -> list[sqlite3.Row]:
    return _query("SELECT * FROM users")

def get_user_phone_number(email: str) -> str | None:
    rows = _query("SELECT phone FROM users WHERE email = ?", (email.lower(),))
    if not rows:
        return None
    row = rows[0]
    if hasattr(row, "keys") and "phone" in row.keys():
        return row["phone"]
    if isinstance(row, (list, tuple)) and row:
        return row[0]
    try:
        return str(row)
    except Exception:
        return None
    




def set_user_password_hash(email: str, password_hash: str): _exec("UPDATE users SET password_hash=? WHERE email=?", (password_hash, email.lower()))
def set_user_first_name(email: str, first_name: str): _exec("UPDATE users SET first_name=? WHERE email=?", (first_name, email.lower()))
def get_user_first_name(email: str) -> Optional[str]:
    rows = _query("SELECT first_name FROM users WHERE email = ?", (email,))
    return rows[0]["first_name"] if rows else None
def set_user_last_name(email: str, last_name: str): _exec("UPDATE users SET last_name=? WHERE email=?", (last_name, email.lower()))
def get_user_last_name(email: str) -> Optional[str]:
    rows = _query("SELECT last_name FROM users WHERE email = ?", (email,))
    return rows[0]["last_name"] if rows else None
def set_user_phone(email: str, phone: str): _exec("UPDATE users SET phone=? WHERE email=?", (phone, email.lower()))
def set_user_address_line(email: str, address_line: str): _exec("UPDATE users SET address_line=? WHERE email=?", (address_line, email.lower()))
def set_user_city(email: str, city: str): _exec("UPDATE users SET city=? WHERE email=?", (city, email.lower()))
def set_user_state(email: str, state: str): _exec("UPDATE users SET state=? WHERE email=?", (state, email.lower()))
def set_user_country(email: str, country: str): _exec("UPDATE users SET country=? WHERE email=?", (country, email.lower()))
def set_user_zip_code(email: str, zip_code: str): _exec("UPDATE users SET zip_code=? WHERE email=?", (zip_code, email.lower()))
def set_user_is_active(email: str, is_active: int): _exec("UPDATE users SET is_active=? WHERE email=?", (int(is_active), email.lower()))

# ---------------------------------------------------------------
# ORDERS
# ---------------------------------------------------------------
def add_order(order_id: str, email: str, subtotal_cents: int = 0, tax_cents: int = 0,
              shipping_cents: int = 0, discount_cents: int = 0, currency: str = "USD",
              status: str = "pending", shipping_name: Optional[str] = None,
              shipping_address: Optional[str] = None, total_cents: Optional[int] = None):
    if total_cents is None:
        total_cents = subtotal_cents + tax_cents + shipping_cents - discount_cents
    _exec("""
        INSERT OR REPLACE INTO orders
        (order_id, email, status, subtotal_cents, tax_cents, shipping_cents,
         discount_cents, total_cents, currency, shipping_name, shipping_address)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (order_id, email.lower(), status, subtotal_cents, tax_cents, shipping_cents,
          discount_cents, total_cents, currency, shipping_name, shipping_address))
    print(f"Order {order_id} for user {email} added/updated.")

# --- Key setters for Orders ---
def set_order_status(order_id: str, status: str): _exec("UPDATE orders SET status=?, updated_at=datetime('now') WHERE order_id=?", (status, order_id))
def set_order_shipping_name(order_id: str, name: str): _exec("UPDATE orders SET shipping_name=?, updated_at=datetime('now') WHERE order_id=?", (name, order_id))
def set_order_shipping_address(order_id: str, address: str): _exec("UPDATE orders SET shipping_address=?, updated_at=datetime('now') WHERE order_id=?", (address, order_id))
def set_order_total(order_id: str, total_cents: int): _exec("UPDATE orders SET total_cents=?, updated_at=datetime('now') WHERE order_id=?", (total_cents, order_id))

def get_order_by_id(order_id: str) -> Optional[sqlite3.Row]:
    rows = _query("SELECT * FROM orders WHERE order_id = ?", (order_id,))
    return rows[0] if rows else None  

def list_orders_for_user(email: str): return _query("SELECT * FROM orders WHERE email=? ORDER BY created_at DESC", (email.lower(),))


# ---------------------------------------------------------------
# ORDER ITEMS
# ---------------------------------------------------------------
def add_order_item(order_id: str, sku: str, name: str, qty: int, unit_price_cents: int):
    line_total_cents = qty * unit_price_cents
    _exec("""
        INSERT INTO order_items (order_id, sku, name, qty, unit_price_cents, line_total_cents)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (order_id, sku, name, qty, unit_price_cents, line_total_cents))
    print(f"Order item {sku} for order {order_id} added.")

# ---------------------------------------------------------------
# PAYMENTS
# ---------------------------------------------------------------
def add_payment(payment_id: str, email: str, order_id: Optional[str], amount_cents: int,
                status: str = "processing", method: str = "card", provider: str = "stripe",
                currency: str = "USD", provider_txn_id: Optional[str] = None):
    _exec("""
        INSERT OR REPLACE INTO payments
        (payment_id, email, order_id, amount_cents, currency, status, method, provider, provider_txn_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (payment_id, email.lower(), order_id, amount_cents, currency, status, method, provider, provider_txn_id))
    print(f"Payment {payment_id} for user {email} added/updated.")

def get_payment_by_id(payment_id: str, email: str) -> Optional[sqlite3.Row]:
    rows = _query("SELECT * FROM payments WHERE payment_id = ? AND email = ?", (payment_id.lower(), email.lower()))
    return rows[0] if rows else None
# --- Key setters for Payments ---
def set_payment_status(payment_id: str, status: str): _exec("UPDATE payments SET status=? WHERE payment_id=?", (status, payment_id))
def set_payment_method(payment_id: str, method: str): _exec("UPDATE payments SET method=? WHERE payment_id=?", (method, payment_id))

def list_payments_for_user(email: str): return _query("SELECT * FROM payments WHERE email=? ORDER BY created_at DESC", (email.lower(),))

# ---------------------------------------------------------------
# AI CONVERSATIONS
# ---------------------------------------------------------------
def add_conversation(conversation_id: str, email: str, conversation_text: str):
    _exec("""
        INSERT OR REPLACE INTO ai_conversations (conversation_id, email, conversation_text)
        VALUES (?, ?, ?)
    """, (conversation_id, email.lower(), conversation_text))
    print(f"Conversation {conversation_id} for user {email} added/updated.")

# --- Key setters for Conversations ---
def set_conversation_ended(conversation_id: str): _exec("UPDATE ai_conversations SET ended_at=datetime('now') WHERE conversation_id=?", (conversation_id,))
def set_conversation_text(conversation_id: str, text: str): _exec("UPDATE ai_conversations SET conversation_text=? WHERE conversation_id=?", (text, conversation_id))

def list_conversations_for_user(email: str): return _query("SELECT * FROM ai_conversations WHERE email=? ORDER BY started_at DESC", (email.lower(),))
def get_conversation(conversation_id: int) -> Optional[str]:
    rows = _query("SELECT conversation_text FROM ai_conversations WHERE conversation_id = ?", (conversation_id,))
    if not rows:
        return None
    row = rows[0]
    return row["conversation_text"] if "conversation_text" in row.keys() else None


# ---------------------------------------------------------------
# Migrations - Handles schema changes for existing databases (Added Address and Unique phone number to users table)
# ---------------------------------------------------------------
def migrate_add_address_columns():
    """Add address columns to users table if they don't exist."""
    with closing(get_connection()) as conn:
        # Check if address_line column exists
        cur = conn.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cur.fetchall()]
        
        if 'address_line' not in columns:
            print("Adding address columns to users table...")
            conn.execute("ALTER TABLE users ADD COLUMN address_line TEXT")
            conn.execute("ALTER TABLE users ADD COLUMN city TEXT")
            conn.execute("ALTER TABLE users ADD COLUMN state TEXT")
            conn.execute("ALTER TABLE users ADD COLUMN country TEXT")
            conn.execute("ALTER TABLE users ADD COLUMN zip_code TEXT")
            conn.commit()
            print("Address columns added successfully.")
        else:
            print("Address columns already exist.")

def migrate_add_phone_unique_index():
    """Create a unique index on users.phone for non-null values to prevent duplicates.
    This is a no-op if duplicates already exist or the index is present.
    """
    with closing(get_connection()) as conn:
        try:
            #check if index already exists
            cur = conn.execute("PRAGMA index_list(users)")
            indexes = [row[1] for row in cur.fetchall()]
            if "idx_users_phone_unique" in indexes:
                return

            #detect duplicates that would break a unique index
            dupes = conn.execute(
                "SELECT phone, COUNT(*) c FROM users WHERE phone IS NOT NULL GROUP BY phone HAVING c > 1"
            ).fetchall()
            if dupes:
                print("[Migration] Skipping creation of unique phone index due to existing duplicate phone numbers.")
                return

            #create a partial unique index
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_phone_unique ON users(phone) WHERE phone IS NOT NULL"
            )
            conn.commit()
            print("[Migration] Created unique index on users.phone (non-null).")
        except Exception as e:
            #non-fatal; log and continue
            print(f"[Migration] Failed to create unique phone index: {e}")

# ---------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------
if __name__ == "__main__":
    init_db()
    add_user("demo@example.com", "hashed_pw", "Demo", "User", "+15555550123")
    add_order("ord_001", "demo@example.com", subtotal_cents=1000, tax_cents=80)
    add_order_item("ord_001", "SKU-001", "Widget", 2, 500)
    add_payment("pay_001", "demo@example.com", "ord_001", 1080, status="succeeded")
    add_conversation("conv_001", "demo@example.com", "User: Hi\nAssistant: Hello!")
    print("Example data seeded.")
