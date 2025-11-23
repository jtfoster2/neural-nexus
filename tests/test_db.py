import pytest
import db

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
    user = db.get_user_by_email(email)
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
    user = db.get_user_by_email(email)
    assert user is None

