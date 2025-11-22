from agents.return_agent import return_agent, _get_orderid, _process_return, AgentState
import pytest
from unittest.mock import patch, MagicMock
import sys

# Mock the problematic imports BEFORE importing return_agent
sys.modules['sendgrid'] = MagicMock()
sys.modules['sendgrid.helpers'] = MagicMock()
sys.modules['sendgrid.helpers.mail'] = MagicMock()


class TestReturnAgent:
    """Test cases for return_agent function."""

    def test_return_agent_guest_user(self):
        """Test that guest users are prompted to log in."""
        state: AgentState = {
            "input": "I want to return my order",
            "email": None,
            "intent": None,
            "reasoning": None,
            "tool_calls": [],
            "tool_results": [],
            "output": None,
            "context_summary": None,
            "context_refs": None,
            "preface": None,
            "memory": None
        }
        updated_state = return_agent(state)
        assert "guest session" in updated_state["output"].lower()

    @patch('agents.return_agent._process_return')
    @patch('agents.return_agent._get_orderid')
    def test_return_agent_no_order_id_found(self, mock_get_orderid, mock_process_return):
        """Test when no order ID is found in input."""
        mock_get_orderid.return_value = {}

        state: AgentState = {
            "input": "I want to return my order",
            "email": "user@example.com",
            "intent": None,
            "reasoning": None,
            "tool_calls": [],
            "tool_results": [],
            "output": None,
            "context_summary": None,
            "context_refs": None,
            "preface": None,
            "memory": None
        }
        updated_state = return_agent(state)
        assert "order number" in updated_state["output"].lower()

    @patch('agents.return_agent._process_return')
    @patch('agents.return_agent._get_orderid')
    def test_return_agent_successful_return(self, mock_get_orderid, mock_process_return):
        """Test successful return processing."""
        mock_get_orderid.return_value = "ord_12345"
        mock_process_return.return_value = True

        state: AgentState = {
            "input": "I want to return order 12345",
            "email": "user@example.com",
            "intent": None,
            "reasoning": None,
            "tool_calls": [],
            "tool_results": [],
            "output": None,
            "context_summary": None,
            "context_refs": None,
            "preface": None,
            "memory": None
        }
        updated_state = return_agent(state)
        assert "confirmation email" in updated_state["output"].lower()

    @patch('agents.return_agent._process_return')
    @patch('agents.return_agent._get_orderid')
    def test_return_agent_failed_return(self, mock_get_orderid, mock_process_return):
        """Test failed return processing."""
        mock_get_orderid.return_value = "ord_99999"
        mock_process_return.return_value = False

        state: AgentState = {
            "input": "I want to return order 99999",
            "email": "user@example.com",
            "intent": None,
            "reasoning": None,
            "tool_calls": [],
            "tool_results": [],
            "output": None,
            "context_summary": None,
            "context_refs": None,
            "preface": None,
            "memory": None
        }
        updated_state = return_agent(state)
        assert "something went wrong" in updated_state["output"].lower()


class TestGetOrderId:
    """Test cases for _get_orderid function."""

    def test_get_orderid_with_number(self):
        """Test extracting order ID from text with number."""
        text = "Please return my order 12345"
        order_id = _get_orderid(text)
        assert order_id == "ord_12345"

    def test_get_orderid_no_number(self):
        """Test when no number is found in text."""
        text = "I want to return my order"
        order_id = _get_orderid(text)
        assert order_id == {}

    def test_get_orderid_empty_text(self):
        """Test with empty text."""
        text = ""
        order_id = _get_orderid(text)
        assert order_id == {}

    def test_get_orderid_multiple_numbers(self):
        """Test extracting first number when multiple exist."""
        text = "Return order 12345 not 67890"
        order_id = _get_orderid(text)
        assert order_id == "ord_12345"


class TestProcessReturn:
    """Test cases for _process_return function."""

    # test guest user return attempt.
    def test_return_agent_guest_user(self):
        """Test return agent with guest user."""
        state: AgentState = {
            "input": "I want to return my order",
            "email": None,
        }
        updated_state = return_agent(state)
        assert updated_state["output"] == (
            "You're currently using a guest session. Please log in or sign up to start a return."
        )

    # test process return success.
    @patch('agents.return_agent.msg')
    @patch('agents.return_agent.db')
    def test_process_return_success(self, mock_db, mock_msg):
        """Test successful return processing."""
        mock_db.get_user.return_value = {
            "email": "user@example.com",
            "first_name": "John"
        }
        mock_db.set_order_status.return_value = None
        mock_msg.message_agent.return_value = {"success": True}

        result = _process_return("user@example.com", "ord_test_001")

        assert result is True
        mock_db.get_user.assert_called_once_with("user@example.com")
        mock_db.set_order_status.assert_called_once_with(
            "ord_test_001", "return requested")

    # process return with valid email and order ID.
    @patch('agents.return_agent.msg.message_agent')
    @patch('agents.return_agent.db.set_order_status')
    @patch('agents.return_agent.db.get_user')
    def test_process_return_valid_email_and_order(self, mock_get_user,
                                                  mock_set_status, mock_message_agent):
        """Test successful return processing with valid email and order ID."""
        # Arrange
        email = "user@example.com"
        order_id = "ord_12345"
        mock_user = {
            "email": email,
            "first_name": "John",
            "last_name": "Doe"
        }

        mock_get_user.return_value = mock_user
        mock_message_agent.return_value = {"success": True}
 # test process return with empty order ID.

    @patch('agents.return_agent.msg')
    @patch('agents.return_agent.db')
    def test_process_return_empty_order_id(self, mock_db, mock_msg):
        """Test return processing with empty order ID."""
        mock_db.get_user.return_value = {"email": "user@example.com"}

        result = _process_return("user@example.com", "")

        assert result is False
        mock_db.set_order_status.assert_not_called()
        mock_msg.message_agent.assert_not_called()

    # process with invalid order ID.
    @patch('agents.return_agent.db')
    @patch('agents.return_agent.msg.message_agent')
    def test_process_return_invalid_order_id(self, mock_message_agent, mock_db):
        """Test return processing with invalid order ID."""
        email = "test@example.com"
        order_id = ""

        mock_db.get_user.return_value = {"email": email, "first_name": "Test"}

        result = _process_return(email, order_id)

        assert result is False
        mock_message_agent.assert_not_called()
        mock_message_agent.assert_not_called()

    # process return when user has no first name.
    @patch('agents.return_agent.db')
    @patch('agents.return_agent.msg.message_agent')
    def test_process_return_no_first_name(self, mock_message_agent, mock_db):
        """Test return processing when user has no first name."""
        mock_db.get_user.return_value = {"email": "user@example.com"}
        email = "user@example.com"
        order_id = "ord_12345"
        mock_db.set_order_status.return_value = None
        mock_message_agent.return_value = {"success": True}
        result = _process_return(email, order_id)

        assert result is True
        mock_db.get_user.assert_called_once_with(email)
        mock_db.set_order_status.assert_called_once_with(
            order_id, "return requested")
        mock_message_agent.assert_called_once()
# run the tests


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
