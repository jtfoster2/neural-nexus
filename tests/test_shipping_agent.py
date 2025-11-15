from agents.shipping_agent import ShippingAgent, shipping_agent, STATUS_NORMALIZATION

def test_extract_email_and_run_with_no_email():
    agent = ShippingAgent()
    result = agent.run({"input": "Check my order status"})
    assert "Please provide" in result["output"]

def test_extract_email_from_input():
    agent = ShippingAgent()
    s = {"input": "my email is test@example.com"}
    agent._extract_email(s)
    assert s["email"] == "test@example.com"

def test_format_user_message_known_status():
    agent = ShippingAgent()
    msg = agent._format_user_message({"status": "Shipped", "order_id": "ORD123", "created_at": "2025-11-12"})
    assert "ORD123" in msg and "Shipped" in msg and "2025-11-12" in msg

def test_format_user_message_unknown_status():
    agent = ShippingAgent()
    assert "I couldn’t find any recent orders associated with your email." in agent._format_user_message({"status": "Unknown"})

def test_status_normalization_map():
    assert STATUS_NORMALIZATION["in transit"] == "In Transit"
    assert STATUS_NORMALIZATION["processing"] == "Processing"

def test_shipping_agent_error_handler(monkeypatch):
    monkeypatch.setattr("agents.shipping_agent.ShippingAgent.run", lambda self, s: 1/0)
    out = shipping_agent({"input": "foo"})
    assert "Sorry—something went wrong while checking your shipping status." in out["output"]
    assert out["confidence"] == 0.2