import json

def test_parse_conversation_text_json_valid():
    from app import _parse_conversation_text

    raw = json.dumps([
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello"},
    ])
    out = _parse_conversation_text(raw)
    assert out == [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello"},
    ]

def test_parse_conversation_text_plain_text_lines():
    from app import _parse_conversation_text

    raw = "User: Hi\nAssistant: Hello!\n…and more"
    out = _parse_conversation_text(raw)

    assert out[0]["role"] == "user" and out[0]["content"] == "Hi"
    assert out[1]["role"] == "assistant"
    assert "Hello!" in out[1]["content"]
    assert "more" in out[1]["content"]
