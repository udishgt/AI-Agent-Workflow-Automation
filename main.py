"""Command-line entry point for displaying discovered workflows."""

import json
import re

from app.agent import Agent
from app.llm_client import LLMClientError, OpenAICompatibleClient
from app.models import Workflow
from app.tool_registry import ToolRegistry
from app.tools import register_default_tools
from app.workflow_loader import WorkflowLoaderError, load_workflows


class DemoLLM:
    """Deterministic local selector used only when no LLM configuration exists."""

    def __init__(self, workflows: list[Workflow]) -> None:
        self._workflows = workflows

    def complete(self, prompt: str) -> str:
        request = prompt.split("User request:\n", 1)[-1].split(
            "\n\nWorkflow catalog:", 1
        )[0].lower()
        catalog = [
            workflow
            for workflow in self._workflows
            if isinstance(workflow.id, str) and isinstance(workflow.name, str)
        ]
        request_words = set(re.findall(r"[a-z0-9]+", request))
        scored = []
        for workflow in catalog:
            score = 0
            for field, weight in (("Workflow_Name", 4), ("Trigger", 3), ("Inputs", 2), ("Steps", 1)):
                metadata_words = set(re.findall(r"[a-z0-9]+", str(workflow.fields.get(field, "")).lower()))
                score += weight * len(request_words & metadata_words)
            scored.append((score, workflow))
        score, selected = max(scored, key=lambda item: item[0], default=(0, None))
        if selected is None or score == 0:
            return json.dumps({
                "workflow_id": "__no_demo_match__",
                "reason": "Demo mode found no matching workflow in the Excel catalog.",
                "confidence": 0.95,
            })
        return json.dumps({
            "workflow_id": selected.id,
            "reason": "DEMO/MOCK mode selected the best metadata match from the Excel catalog.",
            "confidence": 0.95,
        })


def _display_result(result) -> None:
    print(f"Selected Workflow: {result.workflow_id} - {result.workflow_name}")
    print(f"Selection Reason: {result.selection_reason}")
    print(f"Confidence: {result.confidence}")
    if result.execution:
        print("Execution Steps:")
        for step in result.execution.steps_executed:
            print(f"- {step.name}: {step.status}")
        print(f"Tools Used: {', '.join(result.execution.tools_used) or 'None'}")
        print(f"Decisions: {result.execution.decisions or 'None'}")
        print(f"Final Result: {result.execution.final_output}")
        if result.execution.errors:
            print(f"Errors: {result.execution.errors}")
    elif result.errors:
        print(f"Errors: {result.errors}")
    print(f"Status: {result.status.upper()}")


def main() -> int:
    try:
        workflows = load_workflows()
    except WorkflowLoaderError as exc:
        print(f"Error: {exc}")
        return 1

    try:
        client = OpenAICompatibleClient.from_environment()
    except LLMClientError as exc:
        client = DemoLLM(workflows)
        print(f"LLM unavailable ({exc}); using DEMO/MOCK mode.")

    agent = Agent(
        workflows,
        client,
        register_default_tools(ToolRegistry(), llm_client=client),
    )
    while True:
        try:
            user_request = input("\nEnter your workflow request (or 'exit' to quit): ").strip()
        except EOFError:
            print()
            return 0
        if user_request.lower() in {"exit", "quit"}:
            print("Goodbye.")
            return 0
        if not user_request:
            print("Please enter a request.")
            continue

        print(f"\nUser Request: {user_request}")
        _display_result(agent.run(user_request))


if __name__ == "__main__":
    raise SystemExit(main())
