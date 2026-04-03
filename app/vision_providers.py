"""
Vision provider abstraction.

Defines a single interface — VisionProvider.analyze(image_bytes, prompt) -> str —
that any LLM with vision support can implement. The visual analyzer calls this
without knowing which provider is underneath, making it trivial to swap models.

This is the same pattern as BaseAnalyzer: define the contract once, implement
as many times as needed. Adding a new provider means adding one class here and
updating load_provider() — nothing else changes.

Current implementations:
  AnthropicVisionProvider  — Claude (default: claude-sonnet-4-6)
  OpenAIVisionProvider     — GPT-4o (stub, not yet implemented)
"""
import base64
import logging
from abc import ABC, abstractmethod

from app.config import ANTHROPIC_API_KEY, OPENAI_API_KEY

logger = logging.getLogger("isitai")


class VisionProvider(ABC):
    """
    Interface for vision model providers.

    Implement analyze() to add a new provider — everything else is handled
    by the visual analyzer. The method is synchronous so it runs cleanly
    inside asyncio.to_thread alongside the other sync analyzers.
    """

    @abstractmethod
    def analyze(self, image_bytes: bytes, prompt: str) -> str:
        """
        Send an image and a prompt to the vision model.
        Returns the raw text response — the caller handles parsing.
        """
        ...


class AnthropicVisionProvider(VisionProvider):
    """
    Claude vision via the Anthropic Python SDK.

    Uses the sync client (anthropic.Anthropic) so it fits naturally into
    the thread-pool pattern the rest of the analyzers use.

    Default model: claude-sonnet-4-6 — good balance of vision
    quality and cost. Override via the model param.
    """

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        from anthropic import Anthropic
        self._client = Anthropic(api_key=api_key)
        self._model = model

    def analyze(self, image_bytes: bytes, prompt: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=500,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": base64.b64encode(image_bytes).decode(),
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        return response.content[0].text


class OpenAIVisionProvider(VisionProvider):
    """
    GPT-4o vision via the OpenAI Python SDK.

    Stub — implement analyze() using the openai package when needed.
    The interface is identical to AnthropicVisionProvider so swapping
    is a one-line change in load_provider().
    """

    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self._api_key = api_key
        self._model = model

    def analyze(self, image_bytes: bytes, prompt: str) -> str:
        # TODO: implement with the openai package
        # import openai
        # client = openai.OpenAI(api_key=self._api_key)
        # response = client.chat.completions.create(...)
        raise NotImplementedError(
            "OpenAI vision provider is not yet implemented. "
            "Set ANTHROPIC_API_KEY to use Claude vision instead."
        )


def load_provider() -> "VisionProvider | None":
    """
    Load a vision provider from environment variables.

    Priority: Anthropic → OpenAI → None.
    Returns None if no key is set — the visual analyzer silently skips.
    """
    if ANTHROPIC_API_KEY:
        logger.info("Vision: Anthropic (claude-sonnet-4-6)")
        return AnthropicVisionProvider(api_key=ANTHROPIC_API_KEY)

    if OPENAI_API_KEY:
        logger.info("Vision: OpenAI (gpt-4o) — not yet implemented")
        return OpenAIVisionProvider(api_key=OPENAI_API_KEY)

    logger.info("Vision: no API key set — visual analyzer disabled")
    return None
