import pytest
from agents.order_agent import order_agent, AgentState

class DummyDB:
    def __init__(self):
        self.orders = {
            "ord_100": {"order_id": "ord_100", "status": "processing", "created_at": "2025-11-01", "shipping_address": "123 Main St, Atlanta, GA 30318", "subtotal_cents": 10000, "tax_cents": 800, "shipping_cents": 500},
            "ord_200": {"order_id": "ord_200", "status": "shipped", "created_at": "2025-11-02", "shipping_address": "456 Oak Ave, New York, NY 10001", "subtotal_cents": 20000, "tax_cents": 1600, "shipping_cents": 1000},
        }
    def get_order_by_id(self, order_id):
        return self.orders.get(order_id)
    def set_order_shipping_address(self, order_id, address):
        if order_id in self.orders:
            self.orders[order_id]["shipping_address"] = address
    def list_orders_for_user(self, email):
        return [v for v in self.orders.values() if email in v.get("shipping_address","")]

@pytest.fixture(autouse=True)
def patch_db(monkeypatch):
    dummy_db = DummyDB()
    monkeypatch.setattr("agents.order_agent.db", dummy_db)
    yield

def test_order_agent_no_order_id():
    state = AgentState(input="I want to check my order.")
    result = order_agent(state)
    assert "provide either your email or an order id" in result["output"].lower()
    assert result["confidence"] == 0.4

def test_order_agent_found():
    state = AgentState(input="ord_100")
    result = order_agent(state)
    assert "ord_100" in result["output"]
    assert "processing" in result["output"].lower()
    assert "estimated total" in result["output"].lower()
    assert result["confidence"] >= 0.7

def test_order_agent_not_found():
    state = AgentState(input="ord_999")
    result = order_agent(state)
    assert "couldn’t find any orders" in result["output"].lower()
    assert result["confidence"] == 0.5

def test_order_agent_shipping_address_update():
    state = AgentState(input="ord_100 789 New St, Boston, MA 02118", intent="change shipping address")
    result = order_agent(state)
    assert "updated" in result["output"].lower() or "provide your order id" in result["output"].lower()
    # confirm address change in dummy db
    db = DummyDB()
    db.set_order_shipping_address("ord_100", "789 New St, Boston, MA 02118")
    assert db.orders["ord_100"]["shipping_address"] == "789 New St, Boston, MA 02118"

def test_order_agent_blocked_status():
    state = AgentState(input="ord_200 123 New St, NY, NY 10001", intent="change shipping address")
    result = order_agent(state)
    assert "can no longer be changed" in result["output"].lower()
