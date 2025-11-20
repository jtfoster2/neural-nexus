import pytest
from db import get_user, set_user_first_name, set_user_last_name, set_user_phone, set_user_address_line, set_user_city, set_user_state, set_user_country, set_user_zip_code
from auth import reset_password, verify_password, signup

EMAIL = "settings_test@example.com"
FIRST = "Test"
LAST = "User"
PHONE = "+1234567890"
ADDRESS_LINE = "123 Test St"
CITY = "Testville"
STATE = "TS"
COUNTRY = "Testland"
ZIP_CODE = "12345"

@pytest.fixture(autouse=True)
def setup_and_teardown():
    import db
    db.init_db()  # ensure schema is created
    db._exec("DELETE FROM users WHERE email = ?", [EMAIL])
    ok, msg = signup(EMAIL, "initpass", FIRST, LAST, PHONE)
    assert ok, f"Signup failed: {msg}"
    set_user_address_line(EMAIL, ADDRESS_LINE)
    set_user_city(EMAIL, CITY)
    set_user_state(EMAIL, STATE)
    set_user_country(EMAIL, COUNTRY)
    set_user_zip_code(EMAIL, ZIP_CODE)
    yield
    db._exec("DELETE FROM users WHERE email = ?", [EMAIL])

def test_update_profile():
    user = get_user(EMAIL)
    assert user["first_name"] == FIRST
    assert user["last_name"] == LAST
    assert user["phone"] == PHONE
    assert user["address_line"] == ADDRESS_LINE
    assert user["city"] == CITY
    assert user["state"] == STATE
    assert user["country"] == COUNTRY
    assert user["zip_code"] == ZIP_CODE

def test_change_password():
    ok, msg = reset_password(EMAIL, "oldpass123")
    assert ok
    user = get_user(EMAIL)
    assert verify_password("oldpass123", user["password_hash"])
    ok, msg = reset_password(EMAIL, "newpass456")
    assert ok
    user = get_user(EMAIL)
    assert verify_password("newpass456", user["password_hash"])

def test_delete_account():
    ok, msg = reset_password(EMAIL, "deletepass")
    assert ok
    user = get_user(EMAIL)
    assert verify_password("deletepass", user["password_hash"])
    import db
    db._exec("DELETE FROM users WHERE email = ?", [EMAIL])
    user = get_user(EMAIL)
    assert user is None
