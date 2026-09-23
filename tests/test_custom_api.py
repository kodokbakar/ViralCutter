import pytest
from unittest.mock import patch, MagicMock
from scripts.create_viral_segments import (
    call_custom_api,
    verify_ai_connection,
)

def test_call_custom_api_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {"message": {"content": "Hello world from custom LLM!"}}
        ]
    }

    with patch("requests.post", return_value=mock_resp) as mock_post:
        result = call_custom_api(
            prompt="Hi",
            base_url="http://localhost:11434/v1",
            api_key="sk-test-123",
            model_name="llama3.2"
        )
        assert result == "Hello world from custom LLM!"
        mock_post.assert_called_once()
        call_url = mock_post.call_args[0][0]
        assert call_url == "http://localhost:11434/v1/chat/completions"
        headers = mock_post.call_args[1].get("headers", {})
        assert headers.get("Authorization") == "Bearer sk-test-123"

def test_call_custom_api_no_api_key():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {"message": {"content": "Local model output"}}
        ]
    }

    with patch("requests.post", return_value=mock_resp) as mock_post:
        result = call_custom_api(
            prompt="Hi",
            base_url="http://localhost:11434/v1/",
            api_key="",
            model_name="mistral"
        )
        assert result == "Local model output"
        headers = mock_post.call_args[1].get("headers", {})
        assert "Authorization" not in headers

def test_verify_ai_connection_custom_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "ok"}}]
    }

    with patch("requests.post", return_value=mock_resp):
        ok, msg = verify_ai_connection(
            backend="custom",
            base_url="http://localhost:11434/v1",
            api_key="",
            model_name="llama3.2"
        )
        assert ok is True
        assert "Connected" in msg
        assert "llama3.2" in msg

def test_verify_ai_connection_custom_failure():
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = "Invalid API key"

    with patch("requests.post", return_value=mock_resp):
        ok, msg = verify_ai_connection(
            backend="custom",
            base_url="https://api.openai.com/v1",
            api_key="bad-key",
            model_name="gpt-4o"
        )
        assert ok is False
        assert "401" in msg or "Invalid" in msg
