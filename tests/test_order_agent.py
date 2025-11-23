from agents.order_agent import route_event, order_agent, order_event, check_order_event, _extract_order_data
import db
import pytest
import sys
import os
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")))

sys.modules["message_agent"] = MagicMock()
sys.modules["agents.message_agent"] = MagicMock()
sys.modules["sendgrid_tool"] = MagicMock()
sys.modules["sendgrid"] = MagicMock()
sys.modules["sendgrid.helpers"] = MagicMock()
sys.modules["sendgrid.helpers.mail"] = MagicMock()


@pytest.fixture(autouse=True)
def setup_db():
    db.init_db()
    yield


def test_route_order_event():
    state = {"input": "place order widget", "event_type": "ORDER_EVENT"}
    assert route_event(state) == "order_event"


def test_route_check_order():
    state = {"input": "check my orders", "event_type": "CHECK_ORDER_EVENT"}
    assert route_event(state) == "check_order_event"


def test_extract_json():
    raw = '{"items": [{"sku": "SKU1", "name": "Widget", "qty": 2, "unit_price_cents": 500}], "subtotal_cents": 1000}'
    data = _extract_order_data(raw)
    assert data["items"][0]["name"] == "Widget"


def test_extract_simple_format():
    raw = "Widget x 2 @ $5.00"
    data = _extract_order_data(raw)
    assert len(data["items"]) == 1
    assert data["items"][0]["qty"] == 2


def test_order_event_no_user():
    state = {"email": "nonexist@test.com", "input": "Widget x 1 @ $10",
             "tool_calls": [], "tool_results": []}
    result = order_event(state)
    assert "not found" in result["output"].lower()


def test_order_event_creates_order():
    db.add_user("test@order.com", "Test User", "1234567890")
    state = {"email": "test@order.com", "input": "Widget x 1 @ $10",
             "tool_calls": [], "tool_results": []}
    result = order_event(state)
    assert "ORDER PLACED" in result["output"]


def test_check_order_no_user():
    state = {"email": "ghost@test.com", "input": "check orders",
             "tool_calls": [], "tool_results": []}
    result = check_order_event(state)
    assert "not found" in result["output"].lower()


def test_check_order_no_orders():
    db.add_user("empty@test.com", "Empty User", "1234567890")
    state = {"email": "empty@test.com", "input": "my orders",
             "tool_calls": [], "tool_results": []}
    result = check_order_event(state)
    assert "no orders" in result["output"].lower()


def test_check_specific_order():
    db.add_user("buyer@test.com", "Buyer", "1234567890")
    db.add_order("ord_999", "buyer@test.com", 1000, 80, 500)
    db.add_order_item("ord_999", "SKU1", "Test Product", 1, 1000)
    state = {"email": "buyer@test.com", "input": "check order ord_999",
             "tool_calls": [], "tool_results": []}
    result = check_order_event(state)
    assert "ord_999" in result["output"]


def test_order_agent_no_email():
    state = {"input": "orders", "email": None,
             "tool_calls": [], "tool_results": []}
    result = order_agent(state)
    assert "email" in result["output"].lower()


def test_order_agent_with_orders():
    db.add_user("shopper@test.com", "Shopper", "1234567890")
    db.add_order("ord_100", "shopper@test.com", 2000, 160, 500)
    db.add_order_item("ord_100", "SKU2", "Gadget", 2, 1000)
    state = {"input": "", "email": "shopper@test.com",
             "tool_calls": [], "tool_results": []}
    result = order_agent(state)
    assert "ord_100" in result["output"]


# run test
if __name__ == "__main__":
    pytest.main([__file__])
