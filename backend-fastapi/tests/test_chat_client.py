"""
Unit tests for Gemini LLM Chat Client Service (app.services.chat_client)
"""

import pytest
from unittest.mock import MagicMock, patch
from app.services.chat_client import (
    generate_answer,
    GeminiChatError,
    GEMINI_CHAT_MODEL,
)


def test_generate_answer_empty_query():
    """Confirms empty query raises GeminiChatError without calling API."""
    with pytest.raises(GeminiChatError, match="User query cannot be empty."):
        generate_answer(system_prompt="System prompt", user_query="")


@patch("app.services.chat_client.settings")
def test_generate_answer_missing_api_key(mock_settings):
    """Confirms missing GEMINI_API_KEY raises GeminiChatError."""
    mock_settings.GEMINI_API_KEY = ""
    with pytest.raises(GeminiChatError, match="GEMINI_API_KEY is not configured"):
        generate_answer(system_prompt="System prompt", user_query="What is calculus?")


@patch("app.services.chat_client.genai.Client")
@patch("app.services.chat_client.settings")
def test_generate_answer_success(mock_settings, mock_genai_client):
    """Confirms successful answer generation using gemini-3.6-flash."""
    mock_settings.GEMINI_API_KEY = "dummy-api-key"
    mock_client_instance = MagicMock()
    mock_genai_client.return_value = mock_client_instance

    mock_response = MagicMock()
    mock_response.text = "Calculus is the mathematical study of continuous change."
    mock_client_instance.models.generate_content.return_value = mock_response

    system_prompt = "You are a math tutor."
    user_query = "What is calculus?"

    result = generate_answer(system_prompt=system_prompt, user_query=user_query)

    assert result == "Calculus is the mathematical study of continuous change."
    mock_client_instance.models.generate_content.assert_called_once()
    call_kwargs = mock_client_instance.models.generate_content.call_args.kwargs
    assert call_kwargs["model"] == GEMINI_CHAT_MODEL
    assert call_kwargs["contents"] == user_query
    assert call_kwargs["config"].system_instruction == system_prompt


@patch("app.services.chat_client.time.sleep", return_value=None)
@patch("app.services.chat_client.genai.Client")
@patch("app.services.chat_client.settings")
def test_generate_answer_retry_transient_failure(mock_settings, mock_genai_client, mock_sleep):
    """Confirms exponential backoff retry on transient API failure followed by success."""
    mock_settings.GEMINI_API_KEY = "dummy-api-key"
    mock_client_instance = MagicMock()
    mock_genai_client.return_value = mock_client_instance

    mock_response = MagicMock()
    mock_response.text = "Success on attempt 2."

    mock_client_instance.models.generate_content.side_effect = [
        Exception("500 Server Error"),
        mock_response,
    ]

    result = generate_answer(system_prompt="Prompt", user_query="Query")

    assert result == "Success on attempt 2."
    assert mock_client_instance.models.generate_content.call_count == 2
    mock_sleep.assert_called_once_with(1.0)


@patch("app.services.chat_client.time.sleep", return_value=None)
@patch("app.services.chat_client.genai.Client")
@patch("app.services.chat_client.settings")
def test_generate_answer_retries_exhausted(mock_settings, mock_genai_client, mock_sleep):
    """Confirms retries exhausted raises GeminiChatError."""
    mock_settings.GEMINI_API_KEY = "dummy-api-key"
    mock_client_instance = MagicMock()
    mock_genai_client.return_value = mock_client_instance

    mock_client_instance.models.generate_content.side_effect = Exception("Persistent API Error")

    with pytest.raises(GeminiChatError, match="Gemini Chat API failed after 3 attempts"):
        generate_answer(system_prompt="Prompt", user_query="Query")

    assert mock_client_instance.models.generate_content.call_count == 3
