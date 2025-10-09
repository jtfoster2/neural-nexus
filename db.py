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
"""

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
    print(f"Database initialized at {DB_PATH}")

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

def get_all_users() -> list[sqlite3.Row]:
    return _query("SELECT * FROM users")

def set_user_password_hash(email: str, password_hash: str): _exec("UPDATE users SET password_hash=? WHERE email=?", (password_hash, email.lower()))
def set_user_first_name(email: str, first_name: str): _exec("UPDATE users SET first_name=? WHERE email=?", (first_name, email.lower()))
def set_user_last_name(email: str, last_name: str): _exec("UPDATE users SET last_name=? WHERE email=?", (last_name, email.lower()))
def set_user_phone(email: str, phone: str): _exec("UPDATE users SET phone=? WHERE email=?", (phone, email.lower()))
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
