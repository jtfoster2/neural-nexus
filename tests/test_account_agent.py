import pytest
from agents import account_agent
import auth
import db

EMAIL = "account_agent_test@example.com"
FIRST = "Test"
LAST = "User"
PHONE = "+15555550123"
ADDRESS = "123 Main St, Atlanta, GA 30318"

@pytest.fixture(autouse=True)
def setup_and_teardown():
    db._exec("DELETE FROM users WHERE email = ?", [EMAIL])
    user_by_phone = db.get_user_by_phone(PHONE)
    if user_by_phone:
        db._exec("DELETE FROM users WHERE phone = ?", [PHONE])
    ok, msg = auth.signup(EMAIL, "testpass", FIRST, LAST, PHONE)
    assert ok, f"Signup failed: {msg}"
    db.set_user_address_line(EMAIL, "123 Main St")
    db.set_user_city(EMAIL, "Atlanta")
    db.set_user_state(EMAIL, "GA")
    db.set_user_zip_code(EMAIL, "30318")
    db.set_user_country(EMAIL, "USA")
    yield

    db._exec("DELETE FROM users WHERE email = ?", [EMAIL])

def test_change_address():
    state = {
        "input": "456 Oak Ave, New York, NY 10001",
        "email": EMAIL,
        "intent": "change address"
    }
    result = account_agent.account_agent(state)
    user = db.get_user(EMAIL)
    assert "456 Oak Ave" in user["address_line"]
    assert "New York" in user["city"]
    assert "NY" in user["state"]
    assert "10001" in user["zip_code"]
    assert "Address Update Confirmation" in result["output"]

def test_change_phone():
    state = {
        "input": "(212) 555-7890",
        "email": EMAIL,
        "intent": "change phone number"
    }
    result = account_agent.account_agent(state)
    user = db.get_user(EMAIL)
    assert user["phone"] == "2125557890"
    assert "Phone Number Update Confirmation" in result["output"]

def test_change_full_name():
    state = {
        "input": "Jane Doe",
        "email": EMAIL,
        "intent": "change full name"
    }
    result = account_agent.account_agent(state)
    user = db.get_user(EMAIL)
    assert user["first_name"] == "Jane"
    assert user["last_name"] == "Doe"
    assert "Name Update Confirmation" in result["output"]

def test_change_password():
    state = {
        "input": "Please change my password",
        "email": EMAIL,
        "intent": "change password"
    }
    result = account_agent.account_agent(state)
    assert "Settings → Security" in result["output"]
