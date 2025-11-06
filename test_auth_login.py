import unittest
import os
import tempfile
import db
import auth

#unit tests for all authentication; login by email/phone, signup, reset password, and guest

class TestAuthentication(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        #set up test database once for all tests. Use a temp db for testing
        cls.test_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        cls.test_db_path = cls.test_db.name
        cls.test_db.close()
        
        db.DB_PATH = cls.test_db_path
        
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
    
    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.test_db_path): #clean up test db
            os.unlink(cls.test_db_path)
    
    ######################################################################

    #database function and lookup tests

    def test_get_user_by_email(self):
        #test getting user by email
        user = db.get_user("test1@example.com")
        self.assertIsNotNone(user)
        self.assertEqual(user["email"], "test1@example.com")
    
    def test_get_user_by_phone(self):
        #test getting user by phone number
        user = db.get_user_by_phone("+15555551111")
        self.assertIsNotNone(user)
        self.assertEqual(user["email"], "test1@example.com")
    
    def test_get_user_by_phone_not_found(self):
        #test getting user by non-existent phone
        user = db.get_user_by_phone("+19999999999")
        self.assertIsNone(user)
    
    def test_get_user_by_email_or_phone_with_email(self):
        #test unified lookup with email
        user = db.get_user_by_email_or_phone("test2@example.com")
        self.assertIsNotNone(user)
        self.assertEqual(user["email"], "test2@example.com")
    
    def test_get_user_by_email_or_phone_with_phone(self):
        #test unified lookup with phone
        user = db.get_user_by_email_or_phone("+15555552222")
        self.assertIsNotNone(user)
        self.assertEqual(user["email"], "test2@example.com")
    
    def test_get_user_by_email_or_phone_not_found(self):
        #test unified lookup with non-existent identifier
        user = db.get_user_by_email_or_phone("nonexistent@example.com")
        self.assertIsNone(user)
    
    ######################################################################

    #loing test; Email and Phone
    
    #auth login function tests
    def test_get_user_by_email(self):
        #test getting user by email
        user = db.get_user("test1@example.com")
        self.assertIsNotNone(user)
        self.assertEqual(user["email"], "test1@example.com")
    
    def test_get_user_by_phone(self):
        #test getting user by phone number
        user = db.get_user_by_phone("+15555551111")
        self.assertIsNotNone(user)
        self.assertEqual(user["email"], "test1@example.com")
    
    def test_get_user_by_phone_not_found(self):
        #test getting user by non-existent phone
        user = db.get_user_by_phone("+19999999999")
        self.assertIsNone(user)
    
    def test_get_user_by_email_or_phone_with_email(self):
        #test unified lookup with email
        user = db.get_user_by_email_or_phone("test2@example.com")
        self.assertIsNotNone(user)
        self.assertEqual(user["email"], "test2@example.com")
    
    def test_get_user_by_email_or_phone_with_phone(self):
        #test unified lookup with phone
        user = db.get_user_by_email_or_phone("+15555552222")
        self.assertIsNotNone(user)
        self.assertEqual(user["email"], "test2@example.com")
    
    def test_get_user_by_email_or_phone_not_found(self):
        #test unified lookup with non-existent identifier
        user = db.get_user_by_email_or_phone("nonexistent@example.com")
        self.assertIsNone(user)
    
    ######################################################################

    #auth login function tests

    def test_login_with_email_success(self):
        #test successful login with email
        success, message, email = auth.login("test1@example.com", "password123")
        self.assertTrue(success)
        self.assertEqual(message, "Login successful")
        self.assertEqual(email, "test1@example.com")
    
    def test_login_with_phone_success(self):
        #test successful login with phone
        success, message, email = auth.login("+15555551111", "password123")
        self.assertTrue(success)
        self.assertEqual(message, "Login successful")
        self.assertEqual(email, "test1@example.com")
    
    def test_login_with_email_wrong_password(self):
        #test login with wrong password via email
        success, message, email = auth.login("test1@example.com", "wrongpass")
        self.assertFalse(success)
        self.assertEqual(message, "Invalid password")
        self.assertIsNone(email)
    
    def test_login_with_phone_wrong_password(self):
        #test login with wrong password via phone
        success, message, email = auth.login("+15555551111", "wrongpass")
        self.assertFalse(success)
        self.assertEqual(message, "Invalid password")
        self.assertIsNone(email)
    
    def test_login_user_not_found(self):
        #test login with non-existent user
        success, message, email = auth.login("fake@example.com", "password123")
        self.assertFalse(success)
        self.assertEqual(message, "User not found")
        self.assertIsNone(email)
    
    def test_login_returns_email_when_using_phone(self):
        #test that login always returns email even when phone is used
        success, message, email = auth.login("+15555552222", "securepass")
        self.assertTrue(success)
        #should return email, not phone
        self.assertEqual(email, "test2@example.com")
        self.assertNotEqual(email, "+15555552222")
    
    def test_login_user_without_phone(self):
        #test that users without phone can still login with email
        success, message, email = auth.login("nophone@example.com", "testpass")
        self.assertTrue(success)
        self.assertEqual(email, "nophone@example.com")
    
    def test_login_case_insensitive_email(self):
        #test login with different email case
        success, message, email = auth.login("TEST1@EXAMPLE.COM", "password123")
        self.assertTrue(success)
        self.assertEqual(email, "test1@example.com")
    
    ######################################################################

    #signup tests
    
    def test_signup_success_minimal(self):
        #test successful signup with only email and password
        success, message = auth.signup("newuser@test.com", "password123")
        self.assertTrue(success)
        self.assertEqual(message, "Signup successful")
        
        #verify user was created
        user = db.get_user("newuser@test.com")
        self.assertIsNotNone(user)
        self.assertEqual(user["email"], "newuser@test.com")
    
    def test_signup_success_with_names(self):
        #test successful signup with first and last names
        success, message = auth.signup(
            "john.doe@test.com",
            "securepass",
            first_name="John",
            last_name="Doe"
        )
        self.assertTrue(success)
        
        #verify user data
        user = db.get_user("john.doe@test.com")
        self.assertIsNotNone(user)
        self.assertEqual(user["first_name"], "John")
        self.assertEqual(user["last_name"], "Doe")
    
    def test_signup_duplicate_email(self):
        #test signup with existing email fails
        #first user with an email
        auth.signup("duplicate@test.com", "pass1")
        
        #second user attempts same email
        success, message = auth.signup("duplicate@test.com", "pass2")
        self.assertFalse(success)
        self.assertEqual(message, "Email already registered")

    def test_signup_duplicate_phone(self):
        #first user with a phone
        ok, msg = auth.signup("dupphone1@test.com", "pass", phone="+19998887777")
        self.assertTrue(ok)
        #second user attempts same phone
        success, message = auth.signup("dupphone2@test.com", "pass", phone="+19998887777")
        self.assertFalse(success)
        self.assertEqual(message, "Phone number already registered")
    
    def test_signup_email_case_insensitive(self):
        #test that signup treats emails as case-insensitive
        auth.signup("CaseSensitive@Test.com", "pass1")
        
        #try with different case
        success, message = auth.signup("casesensitive@test.com", "pass2")
        self.assertFalse(success)
        self.assertEqual(message, "Email already registered")
    
    def test_signup_password_hashed(self):
        #test that password is properly hashed, not stored in plaintext
        success, message = auth.signup("hashed@test.com", "mypassword")
        self.assertTrue(success)
        
        user = db.get_user("hashed@test.com")
        #password hash should not equal plaintext
        self.assertNotEqual(user["password_hash"], "mypassword")
        #hash should be bcrypt format
        self.assertTrue(user["password_hash"].startswith("$2b$"))
    
    def test_signup_long_password(self):
        #test signup with very long password (72 bytes)
        long_pass = "a" * 100
        success, message = auth.signup("longpass@test.com", long_pass)
        self.assertTrue(success)
        
        #verify can login with same long password
        login_success, login_msg, email = auth.login("longpass@test.com", long_pass)
        self.assertTrue(login_success)
    
    ######################################################################

    #reset password/forgot password tests
    
    def test_reset_password_success(self):
        #test successful password reset. create user with initial password
        auth.signup("reset@test.com", "oldpassword")
        
        #reset password
        success, message = auth.reset_password("reset@test.com", "newpassword")
        self.assertTrue(success)
        self.assertEqual(message, "Password updated successfully")
        
        #verify old password no longer works
        login_old = auth.login("reset@test.com", "oldpassword")
        self.assertFalse(login_old[0])
        
        #verify new password works
        login_new = auth.login("reset@test.com", "newpassword")
        self.assertTrue(login_new[0])
    
    def test_reset_password_user_not_found(self):
        #est reset password fails for non-existent user
        success, message = auth.reset_password("nonexistent@test.com", "newpass")
        self.assertFalse(success)
        self.assertEqual(message, "User not found")
    
    def test_reset_password_multiple_times(self):
        #test user can reset password multiple times
        auth.signup("multireset@test.com", "pass1")
        
        #reset to pass 2
        auth.reset_password("multireset@test.com", "pass2")
        self.assertTrue(auth.login("multireset@test.com", "pass2")[0])
        
        #reset to pass 3
        auth.reset_password("multireset@test.com", "pass3")
        self.assertTrue(auth.login("multireset@test.com", "pass3")[0])
        self.assertFalse(auth.login("multireset@test.com", "pass2")[0])
    
    def test_reset_password_hashed_properly(self):
        #test that reset password is hashed, not plaintext
        auth.signup("hashcheck@test.com", "oldpass")
        auth.reset_password("hashcheck@test.com", "mynewpass")
        
        user = db.get_user("hashcheck@test.com")
        self.assertNotEqual(user["password_hash"], "mynewpass")
        self.assertTrue(user["password_hash"].startswith("$2b$"))
    
    ######################################################################
    
    #continue as guest tests
    
    def test_guest_user_concept(self):
        #test guest user logic. guest should not be able to get user data
        guest_user = db.get_user("")
        self.assertIsNone(guest_user)
        
        guest_user2 = db.get_user(" ")
        self.assertIsNone(guest_user2)
    
    def test_guest_cannot_login_with_empty_credentials(self):
        #test that empty credentials don't allow login
        success, message, email = auth.login("", "")
        self.assertFalse(success)
        #should fail to find user
        self.assertIsNone(email)
    
    def test_display_name_for_guest(self): #this function works but it's very fast on the login page when users log back in again
        #test get_user_display_name handles missing users gracefully. for a non-existent user, should return the email/identifier
        display_name = auth.get_user_display_name("nonexist@test.com")
        #current implementation returns the identifier if user not found
        self.assertEqual(display_name, "nonexist@test.com")
    
    def test_display_name_with_first_name(self):
        #test display name uses first_name when available
        auth.signup("displaytest@test.com", "pass", first_name="Alice")
        display_name = auth.get_user_display_name("displaytest@test.com")
        self.assertEqual(display_name, "Alice")
    
    def test_display_name_without_first_name(self):
        #test display name falls back to email username
        auth.signup("nofirstname@test.com", "pass")
        display_name = auth.get_user_display_name("nofirstname@test.com")
        self.assertEqual(display_name, "nofirstname")  # email before @
    
    ######################################################################
    
    #intergration tests; ends to ends flow
    
    def test_full_user_lifecycle(self):
        #test complete user path; signup, login, reset, then login
        #signup
        success, msg = auth.signup("lifecycle@test.com", "pass1", first_name="Test")
        self.assertTrue(success)
        
        #login
        success, msg, email = auth.login("lifecycle@test.com", "pass1")
        self.assertTrue(success)
        self.assertEqual(email, "lifecycle@test.com")
        
        #reset password
        success, msg = auth.reset_password("lifecycle@test.com", "newpass")
        self.assertTrue(success)
        
        #login with new password
        success, msg, email = auth.login("lifecycle@test.com", "newpass")
        self.assertTrue(success)
        
        #old password should fail
        success, msg, email = auth.login("lifecycle@test.com", "pass1")
        self.assertFalse(success)
    
    def test_signup_then_login_with_phone(self):
        #test user can signup with phone and login using it
        success, msg = auth.signup(
            "phoneuser@test.com",
            "pass123",
            phone="+15555550101"
        )
        self.assertTrue(success)

        #login with phone
        success, msg, email = auth.login("+15555550101", "pass123")
        self.assertTrue(success)
        self.assertEqual(email, "phoneuser@test.com")

        #login with email should also work
        success, msg, email = auth.login("phoneuser@test.com", "pass123")
        self.assertTrue(success)


if __name__ == "__main__":
    unittest.main(verbosity=2)

