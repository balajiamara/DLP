"""
Gemini LLM Chat Client Service

Model Decision Rationale:
`gemini-3.6-flash` is selected as Google's official recommended flagship Flash model
for general text generation, instruction following, and RAG grounding.
"""

import asyncio
import time
import logging
from typing import AsyncGenerator
from google import genai
from google.genai import types
from app.core.config import settings

logger = logging.getLogger(__name__)

GEMINI_CHAT_MODEL = "gemini-3.6-flash"
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 1.0  # seconds


class GeminiChatError(Exception):
    """Raised when Gemini LLM generation fails after retries or is misconfigured."""
    pass


def generate_answer(system_prompt: str, user_query: str) -> str:
    """
    Generates a grounded text answer using Google Gemini 3.6 Flash.

    Args:
        system_prompt: Grounding instructions and context provided to the model.
        user_query: The user's question string.

    Returns:
        Generated text string response from the model.

    Raises:
        GeminiChatError: If API key is missing or calls fail after retries.
    """
    if not user_query:
        raise GeminiChatError("User query cannot be empty.")

    api_key = settings.GEMINI_API_KEY
    if not api_key:
        raise GeminiChatError("GEMINI_API_KEY is not configured in settings.")

    client = genai.Client(api_key=api_key)
    delay = INITIAL_RETRY_DELAY

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.2,  # Low temperature for strict grounded factual precision
            )
            response = client.models.generate_content(
                model=GEMINI_CHAT_MODEL,
                contents=user_query,
                config=config,
            )

            if not response or not response.text:
                raise GeminiChatError("Gemini Chat API returned an empty text response.")

            return response.text.strip()

        except GeminiChatError:
            raise
        except Exception as e:
            logger.warning(
                f"Gemini Chat API call failed (attempt {attempt}/{MAX_RETRIES}): {e}"
            )
            if attempt == MAX_RETRIES:
                raise GeminiChatError(
                    f"Gemini Chat API failed after {MAX_RETRIES} attempts: {e}"
                ) from e
            time.sleep(delay)
            delay *= 2.0

    raise GeminiChatError("Failed to generate answer: retries exhausted.")


async def generate_answer_stream(system_prompt: str, user_query: str) -> AsyncGenerator[str, None]:
    """
    Generates a streaming grounded text answer using Google Gemini 3.6 Flash via async client.

    Args:
        system_prompt: Grounding instructions and context provided to the model.
        user_query: The user's question string.

    Yields:
        Non-empty string chunks (deltas) as they arrive from Gemini.

    Raises:
        GeminiChatError: If API key is missing or stream connection fails.
    """
    if not user_query:
        raise GeminiChatError("User query cannot be empty.")

    api_key = settings.GEMINI_API_KEY
    if not api_key:
        raise GeminiChatError("GEMINI_API_KEY is not configured in settings.")

    client = genai.Client(api_key=api_key)
    delay = INITIAL_RETRY_DELAY

    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=0.2,  # Low temperature for strict grounded factual precision
    )

    response_stream = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response_stream = await client.aio.models.generate_content_stream(
                model=GEMINI_CHAT_MODEL,
                contents=user_query,
                config=config,
            )
            break
        except Exception as e:
            logger.warning(
                f"Gemini Chat API stream initialization failed (attempt {attempt}/{MAX_RETRIES}): {e}"
            )
            if attempt == MAX_RETRIES:
                raise GeminiChatError(
                    f"Gemini Chat API stream failed after {MAX_RETRIES} attempts: {e}"
                ) from e
            await asyncio.sleep(delay)
            delay *= 2.0

    if response_stream is None:
        raise GeminiChatError("Failed to initialize Gemini stream: retries exhausted.")

    try:
        async for chunk in response_stream:
            text = chunk.text
            # Filter out empty terminal chunks or empty deltas
            if text:
                yield text
    except Exception as e:
        logger.error(f"Error reading Gemini content stream: {e}")
        raise GeminiChatError(f"Gemini content stream interrupted: {e}") from e

