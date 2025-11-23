import pytest
import db

@pytest.fixture(autouse=True)
def mock_db_functions(monkeypatch):
    # mock storage
    orders = {}
    users = {}

    def mock_set_order_shipping_address(order_id, address):
        if order_id in orders:
            orders[order_id]["shipping_address"] = address
    def mock_set_user_address_line(email, address_line):
        if email in users:
            users[email]["address_line"] = address_line
    def mock_get_order_by_id(order_id):
        return orders.get(order_id)
    def mock_get_user(email):
        return users.get(email)

    orders["ord_100"] = {"order_id": "ord_100", "shipping_address": "old address"}
    users["test@example.com"] = {"email": "test@example.com", "address_line": "old address"}

    monkeypatch.setattr(db, "set_order_shipping_address", mock_set_order_shipping_address)
    monkeypatch.setattr(db, "set_user_address_line", mock_set_user_address_line)
    monkeypatch.setattr(db, "get_order_by_id", mock_get_order_by_id)
    monkeypatch.setattr(db, "get_user", mock_get_user)
    yield


def test_set_order_shipping_address():
    order_id = "ord_100"
    new_address = "789 New St, Boston, MA 02118"
    db.set_order_shipping_address(order_id, new_address)
    order = db.get_order_by_id(order_id)
    assert order["shipping_address"] == new_address

def test_set_user_address_line():
    email = "test@example.com"
    new_address = "123 Test Ave, Test City, TX 75001"
    db.set_user_address_line(email, new_address)
    user = db.get_user(email)
    assert user["address_line"] == new_address

def test_get_order_by_id_not_found():
    order = db.get_order_by_id("ord_999")
    assert order is None

def test_set_order_shipping_address_invalid():
    order_id = "ord_999"
    new_address = "999 Nowhere St, No City, ZZ 00000"
    db.set_order_shipping_address(order_id, new_address)
    order = db.get_order_by_id(order_id)
    assert order is None

def test_set_user_address_line_invalid():
    email = "notfound@example.com"
    new_address = "999 Nowhere St, No City, ZZ 00000"
    db.set_user_address_line(email, new_address)
    user = db.get_user(email)
    assert user is None

