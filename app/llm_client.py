"""Configurable OpenAI-compatible LLM client."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

from dotenv import load_dotenv
from openai import OpenAI
from openai import OpenAIError


class LLMClientError(RuntimeError):
    """Raised when the LLM client cannot be configured or complete a request."""


class LLMConfigurationError(LLMClientError):
    """Raised when required LLM configuration is missing."""


class LLMClient(Protocol):
    """Small interface implemented by LLM providers and test fakes."""

    def complete(self, prompt: str) -> str:
        """Send a prompt and return the response text."""


@dataclass(frozen=True)
class OpenAICompatibleClient:
    """Client for providers exposing the OpenAI chat-completions interface."""

    api_key: str
    base_url: str
    model: str
    timeout: float = 30

    def __post_init__(self) -> None:
        if not self.api_key.strip():
            raise LLMConfigurationError("LLM_API_KEY is not configured")
        if not self.base_url.strip():
            raise LLMConfigurationError("LLM_BASE_URL is not configured")
        if not self.model.strip():
            raise LLMConfigurationError("LLM_MODEL is not configured")

    def complete(self, prompt: str) -> str:
        """Send a prompt and return the model's text response."""
        if not prompt.strip():
            raise LLMClientError("LLM prompt must not be empty")

        client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout,
        )
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                response_format={"type": "json_object"},
            )
        except OpenAIError as exc:
            raise LLMClientError(f"LLM request failed: {exc}") from exc

        content = response.choices[0].message.content if response.choices else None
        if not content:
            raise LLMClientError("LLM response did not contain message content")
        return content

    @classmethod
    def from_environment(cls) -> OpenAICompatibleClient:
        """Create a client from environment variables or a local .env file."""
        load_dotenv()
        api_key = os.getenv("LLM_API_KEY", "")
        base_url = os.getenv("LLM_BASE_URL", "")
        model = os.getenv("LLM_MODEL", "")
        missing = [
            name for name, value in (
                ("LLM_API_KEY", api_key),
                ("LLM_BASE_URL", base_url),
                ("LLM_MODEL", model),
            )
            if not value.strip()
        ]
        if missing:
            raise LLMConfigurationError(
                f"Missing LLM configuration: {', '.join(missing)}"
            )
        return cls(api_key=api_key, base_url=base_url, model=model)
