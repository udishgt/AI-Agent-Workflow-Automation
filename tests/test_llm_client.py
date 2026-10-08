from types import SimpleNamespace

import pytest

from app.llm_client import LLMClientError, LLMConfigurationError, OpenAICompatibleClient


def test_reads_configuration_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://llm.example/v1")
    monkeypatch.setenv("LLM_MODEL", "test-model")

    client = OpenAICompatibleClient.from_environment()

    assert client.base_url == "https://llm.example/v1"
    assert client.model == "test-model"


def test_requires_all_configuration_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.setenv("LLM_MODEL", "test-model")

    with pytest.raises(LLMConfigurationError, match="LLM_BASE_URL"):
        OpenAICompatibleClient.from_environment()


def test_complete_uses_openai_compatible_interface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class FakeCompletions:
        def create(self, **kwargs: object) -> SimpleNamespace:
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content='{"workflow_id": "wf-1"}')
                    )
                ]
            )

    class FakeOpenAI:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr("app.llm_client.OpenAI", FakeOpenAI)
    client = OpenAICompatibleClient("secret-key", "https://llm.example/v1", "test-model")

    assert client.complete("select a workflow") == '{"workflow_id": "wf-1"}'
    assert captured["api_key"] == "secret-key"
    assert captured["base_url"] == "https://llm.example/v1"
    assert captured["model"] == "test-model"
    assert captured["messages"] == [{"role": "user", "content": "select a workflow"}]


def test_rejects_empty_prompt() -> None:
    client = OpenAICompatibleClient("secret-key", "https://llm.example/v1", "test-model")

    with pytest.raises(LLMClientError, match="prompt"):
        client.complete(" ")
