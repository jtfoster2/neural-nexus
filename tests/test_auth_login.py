import pytest
import os
import tempfile
import db
import auth

@pytest.fixture(scope="module", autouse=True)
def test_db():
    test_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    test_db_path = test_db.name
    test_db.close()
    db.DB_PATH = test_db_path
    db.init_db()
    db.add_user(
        email="test1@example.com",
        password_hash=auth.hash_password("password123"),
        first_name="Test",
        last_name="User",
        phone="+15555551111"
    )
    db.add_user(
        email="test2@example.com",
        password_hash=auth.hash_password("securepass"),
        first_name="Jane",
        last_name="Doe",
        phone="+15555552222"
    )
    db.add_user(
        email="nophone@example.com",
        password_hash=auth.hash_password("testpass"),
        first_name="No",
        last_name="Phone",
        phone=None
    )
    yield
    if os.path.exists(test_db_path):
        os.unlink(test_db_path)

def test_get_user_by_email():
    user = db.get_user("test1@example.com")
    assert user is not None
    assert user["email"] == "test1@example.com"

def test_get_user_by_phone():
    user = db.get_user_by_phone("+15555551111")
    assert user is not None
    assert user["email"] == "test1@example.com"

def test_get_user_by_phone_not_found():
    user = db.get_user_by_phone("+19999999999")
    assert user is None

def test_get_user_by_email_or_phone_with_email():
    user = db.get_user_by_email_or_phone("test2@example.com")
    assert user is not None
    assert user["email"] == "test2@example.com"

def test_get_user_by_email_or_phone_with_phone():
    user = db.get_user_by_email_or_phone("+15555552222")
    assert user is not None
    assert user["email"] == "test2@example.com"

def test_get_user_by_email_or_phone_not_found():
    user = db.get_user_by_email_or_phone("nonexistent@example.com")
    assert user is None

def test_login_with_email_success():
    success, message, email = auth.login("test1@example.com", "password123")
    assert success
    assert message == "Login successful"
    assert email == "test1@example.com"

def test_login_with_phone_success():
    success, message, email = auth.login("+15555551111", "password123")
    assert success
    assert message == "Login successful"
    assert email == "test1@example.com"

def test_login_with_email_wrong_password():
    success, message, email = auth.login("test1@example.com", "wrongpass")
    assert not success
    assert message == "Invalid password"
    assert email is None

def test_login_with_phone_wrong_password():
    success, message, email = auth.login("+15555551111", "wrongpass")
    assert not success
    assert message == "Invalid password"
    assert email is None

def test_login_user_not_found():
    success, message, email = auth.login("fake@example.com", "password123")
    assert not success
    assert message == "User not found"
    assert email is None

def test_login_returns_email_when_using_phone():
    success, message, email = auth.login("+15555552222", "securepass")
    assert success
    assert email == "test2@example.com"
    assert email != "+15555552222"

def test_login_user_without_phone():
    success, message, email = auth.login("nophone@example.com", "testpass")
    assert success
    assert email == "nophone@example.com"

def test_login_case_insensitive_email():
    success, message, email = auth.login("TEST1@EXAMPLE.COM", "password123")
    assert success
    assert email == "test1@example.com"

def test_signup_success_minimal():
    success, message = auth.signup("newuser@test.com", "password123")
    assert success
    assert message == "Signup successful"
    user = db.get_user("newuser@test.com")
    assert user is not None
    assert user["email"] == "newuser@test.com"

def test_signup_success_with_names():
    success, message = auth.signup("john.doe@test.com", "securepass", first_name="John", last_name="Doe")
    assert success
    user = db.get_user("john.doe@test.com")
    assert user is not None
    assert user["first_name"] == "John"
    assert user["last_name"] == "Doe"

def test_signup_duplicate_email():
    auth.signup("duplicate@test.com", "pass1")
    success, message = auth.signup("duplicate@test.com", "pass2")
    assert not success
    assert message == "Email already registered"

def test_signup_duplicate_phone():
    ok, msg = auth.signup("dupphone1@test.com", "pass", phone="+19998887777")
    assert ok
    success, message = auth.signup("dupphone2@test.com", "pass", phone="+19998887777")
    assert not success
    assert message == "Phone number already registered"

def test_signup_email_case_insensitive():
    auth.signup("CaseSensitive@Test.com", "pass1")
    success, message = auth.signup("casesensitive@test.com", "pass2")
    assert not success
    assert message == "Email already registered"

def test_signup_password_hashed():
    success, message = auth.signup("hashed@test.com", "mypassword")
    assert success
    user = db.get_user("hashed@test.com")
    assert user["password_hash"] != "mypassword"
    assert user["password_hash"].startswith("$2b$")

def test_signup_long_password():
    long_pass = "a" * 100
    success, message = auth.signup("longpass@test.com", long_pass)
    assert success
    login_success, login_msg, email = auth.login("longpass@test.com", long_pass)
    assert login_success

def test_reset_password_success():
    auth.signup("reset@test.com", "oldpassword")
    success, message = auth.reset_password("reset@test.com", "newpassword")
    assert success
    assert message == "Password updated successfully"
    login_old = auth.login("reset@test.com", "oldpassword")
    assert not login_old[0]
    login_new = auth.login("reset@test.com", "newpassword")
    assert login_new[0]

def test_reset_password_user_not_found():
    success, message = auth.reset_password("nonexistent@test.com", "newpass")
    assert not success
    assert message == "User not found"

def test_reset_password_multiple_times():
    auth.signup("multireset@test.com", "pass1")
    auth.reset_password("multireset@test.com", "pass2")
    assert auth.login("multireset@test.com", "pass2")[0]
    auth.reset_password("multireset@test.com", "pass3")
    assert auth.login("multireset@test.com", "pass3")[0]
    assert not auth.login("multireset@test.com", "pass2")[0]

def test_reset_password_hashed_properly():
    auth.signup("hashcheck@test.com", "oldpass")
    auth.reset_password("hashcheck@test.com", "mynewpass")
    user = db.get_user("hashcheck@test.com")
    assert user["password_hash"] != "mynewpass"
    assert user["password_hash"].startswith("$2b$")

def test_guest_user_concept():
    guest_user = db.get_user("")
    assert guest_user is None
    guest_user2 = db.get_user(" ")
    assert guest_user2 is None

def test_guest_cannot_login_with_empty_credentials():
    success, message, email = auth.login("", "")
    assert not success
    assert email is None

def test_display_name_for_guest():
    display_name = auth.get_user_display_name("nonexist@test.com")
    assert display_name == "nonexist@test.com"

def test_display_name_with_first_name():
    auth.signup("displaytest@test.com", "pass", first_name="Alice")
    display_name = auth.get_user_display_name("displaytest@test.com")
    assert display_name == "Alice"

def test_display_name_without_first_name():
    auth.signup("nofirstname@test.com", "pass")
    display_name = auth.get_user_display_name("nofirstname@test.com")
    assert display_name == "nofirstname"

def test_full_user_lifecycle():
    success, msg = auth.signup("lifecycle@test.com", "pass1", first_name="Test")
    assert success
    success, msg, email = auth.login("lifecycle@test.com", "pass1")
    assert success
    assert email == "lifecycle@test.com"
    success, msg = auth.reset_password("lifecycle@test.com", "newpass")
    assert success
    success, msg, email = auth.login("lifecycle@test.com", "newpass")
    assert success
    success, msg, email = auth.login("lifecycle@test.com", "pass1")
    assert not success

def test_signup_then_login_with_phone():
    success, msg = auth.signup("phoneuser@test.com", "pass123", phone="+15555550101")
    assert success
    success, msg, email = auth.login("+15555550101", "pass123")
    assert success
    assert email == "phoneuser@test.com"
    success, msg, email = auth.login("phoneuser@test.com", "pass123")
    assert success

