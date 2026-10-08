import json

import pytest

from app.models import Workflow
from app.workflow_selector import (
    LLMConfigurationError,
    WorkflowSelectionError,
    OpenAICompatibleClient,
    select_workflow,
)


WORKFLOWS = [
    Workflow("wf-1", "First workflow", {"Workflow_ID": "wf-1", "Workflow_Name": "First workflow"}),
    Workflow("wf-2", "Second workflow", {"Workflow_ID": "wf-2", "Workflow_Name": "Second workflow"}),
]


class MockLLM:
    def __init__(self, response: str):
        self.response = response
        self.prompt = ""

    def complete(self, prompt: str) -> str:
        self.prompt = prompt
        return self.response


def test_selects_and_validates_llm_response() -> None:
    llm = MockLLM(json.dumps({
        "workflow_id": "wf-2",
        "reason": "It matches the request.",
        "confidence": 0.91,
    }))

    selection = select_workflow("Do the second task", WORKFLOWS, llm)

    assert selection.workflow_id == "wf-2"
    assert selection.confidence == 0.91
    assert "Do the second task" in llm.prompt
    assert "First workflow" in llm.prompt


@pytest.mark.parametrize(
    ("response", "message"),
    [
        ("not json", "invalid JSON"),
        ('{"workflow_id": "unknown", "reason": "x", "confidence": 0.9}', "unknown workflow_id"),
        ('{"workflow_id": "wf-1", "reason": "x", "confidence": 0.2}', "below the minimum"),
    ],
)
def test_rejects_invalid_llm_selections(response: str, message: str) -> None:
    with pytest.raises(WorkflowSelectionError, match=message):
        select_workflow("Request", WORKFLOWS, MockLLM(response))


def test_rejects_missing_response_fields() -> None:
    with pytest.raises(WorkflowSelectionError, match="missing fields"):
        select_workflow("Request", WORKFLOWS, MockLLM('{"workflow_id": "wf-1"}'))


def test_requires_llm_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    with pytest.raises(LLMConfigurationError, match="LLM_API_KEY"):
        OpenAICompatibleClient.from_environment()
