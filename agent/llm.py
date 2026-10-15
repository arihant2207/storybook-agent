"""Provider-agnostic text generation for the Storybook Agent.

All agent modules should call generate_text() rather than importing the SDK
directly so that the LLM backend can be swapped without touching business logic.

Currently backed by the Google Gemini SDK (google-genai).  To switch providers,
add another branch inside generate_text() or replace the _gemini_generate()
helper with a different implementation.
"""

import logging
from typing import Optional

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from agent import config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Gemini backend
# ---------------------------------------------------------------------------

def _gemini_generate(
    prompt: str,
    *,
    system_instruction: Optional[str] = None,
    response_mime_type: str = "text/plain",
    response_schema=None,
) -> str:
    """Call the Gemini text model and return the raw response text."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.GEMINI_API_KEY)

    gen_cfg_kwargs: dict = {
        "response_mime_type": response_mime_type,
    }
    if system_instruction:
        gen_cfg_kwargs["system_instruction"] = system_instruction
    if response_schema is not None:
        gen_cfg_kwargs["response_schema"] = response_schema

    gen_cfg = types.GenerateContentConfig(**gen_cfg_kwargs)

    response = client.models.generate_content(
        model=config.TEXT_MODEL,
        contents=prompt,
        config=gen_cfg,
    )
    return response.text or ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
    retry=retry_if_exception_type(Exception),
)
def generate_text(
    prompt: str,
    *,
    system_instruction: Optional[str] = None,
    response_mime_type: str = "text/plain",
    response_schema=None,
) -> str:
    """Generate text using the configured LLM backend.

    Args:
        prompt: The user / task prompt to send to the model.
        system_instruction: Optional system / persona instruction.
        response_mime_type: MIME type hint for structured output
            (e.g. ``"application/json"``).
        response_schema: Optional pydantic model or JSON schema that the
            model should conform to (provider-specific; passed through only
            when the backend supports it).

    Returns:
        Raw text from the model (already stripped of leading/trailing whitespace).

    Raises:
        RuntimeError: If the backend returns an empty response after retries.
    """
    logger.debug("generate_text called with model=%s", config.TEXT_MODEL)
    text = _gemini_generate(
        prompt,
        system_instruction=system_instruction,
        response_mime_type=response_mime_type,
        response_schema=response_schema,
    )
    if not text:
        raise RuntimeError("LLM returned an empty response.")
    return text.strip()
