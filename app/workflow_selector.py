"""Select a loaded workflow using a replaceable LLM provider."""

from __future__ import annotations

import json
from typing import Sequence

from app.llm_client import LLMClient, LLMConfigurationError, OpenAICompatibleClient
from app.models import Workflow, WorkflowSelection


class WorkflowSelectionError(ValueError):
    """Raised when a workflow cannot be selected."""


def _build_prompt(request: str, workflows: Sequence[Workflow]) -> str:
    workflow_data = [
        {"workflow_id": workflow.id, "workflow_name": workflow.name, **workflow.fields}
        for workflow in workflows
    ]
    return (
        "Select the single most appropriate workflow for the user's request. "
        "Return only valid JSON with exactly these fields: workflow_id, reason, confidence. "
        "confidence must be a number from 0 to 1. Choose workflow_id only from the supplied "
        "workflow catalog.\n\n"
        f"User request:\n{request}\n\n"
        f"Workflow catalog:\n{json.dumps(workflow_data, default=str)}"
    )


def select_workflow(
    request: str,
    workflows: Sequence[Workflow],
    llm_client: LLMClient,
    *,
    minimum_confidence: float = 0.5,
) -> WorkflowSelection:
    """Use an LLM to select and validate a workflow."""
    if not request.strip():
        raise WorkflowSelectionError("User request must not be empty")
    if not workflows:
        raise WorkflowSelectionError("No workflows are available for selection")
    if not 0 <= minimum_confidence <= 1:
        raise WorkflowSelectionError("minimum_confidence must be between 0 and 1")

    raw_response = llm_client.complete(_build_prompt(request, workflows))
    try:
        result = json.loads(raw_response)
    except (TypeError, json.JSONDecodeError) as exc:
        raise WorkflowSelectionError("LLM returned invalid JSON") from exc
    if not isinstance(result, dict):
        raise WorkflowSelectionError("LLM response must be a JSON object")

    required = ("workflow_id", "reason", "confidence")
    missing = [field for field in required if field not in result]
    if missing:
        raise WorkflowSelectionError(f"LLM response is missing fields: {', '.join(missing)}")

    workflow_id = result["workflow_id"]
    reason = result["reason"]
    confidence = result["confidence"]
    if not isinstance(reason, str) or not reason.strip():
        raise WorkflowSelectionError("LLM response reason must be a non-empty string")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise WorkflowSelectionError("LLM response confidence must be a number")
    if not 0 <= confidence <= 1:
        raise WorkflowSelectionError("LLM response confidence must be between 0 and 1")
    if confidence < minimum_confidence:
        raise WorkflowSelectionError(
            f"LLM confidence {confidence:.2f} is below the minimum {minimum_confidence:.2f}"
        )

    known_ids = {workflow.id for workflow in workflows}
    if workflow_id not in known_ids:
        raise WorkflowSelectionError(f"LLM selected unknown workflow_id: {workflow_id}")
    return WorkflowSelection(workflow_id, reason.strip(), float(confidence))


# Compatibility exports for callers that previously imported the provider here.
__all__ = [
    "LLMClient",
    "LLMConfigurationError",
    "OpenAICompatibleClient",
    "WorkflowSelectionError",
    "select_workflow",
]
