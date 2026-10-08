"""Generic, step-driven workflow execution foundation."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from app.models import (
    ExecutionContext,
    ExecutionResult,
    StepDefinition,
    StepHandlerResult,
    StepResult,
    Workflow,
)


StepHandler = Callable[[StepDefinition, ExecutionContext], StepHandlerResult | Any]


def parse_steps(steps: Any) -> list[StepDefinition]:
    """Parse the Excel Steps field into ordered, provider-neutral descriptions."""
    if steps is None:
        return []
    if not isinstance(steps, str):
        raise ValueError("Workflow Steps must be text")
    return [
        StepDefinition(name=part.strip())
        for part in re.split(r"\s*(?:→|->|\r?\n)\s*", steps)
        if part.strip()
    ]


class WorkflowExecutor:
    """Execute workflow step descriptions through an injected generic handler."""

    def __init__(self, step_handler: StepHandler, *, stop_on_failure: bool = True):
        self._step_handler = step_handler
        self._stop_on_failure = stop_on_failure

    def execute(
        self,
        workflow: Workflow,
        request: str,
        context: ExecutionContext,
    ) -> ExecutionResult:
        """Execute all parsed steps and return a complete trace instead of raising."""
        if context.request != request:
            context.request = request

        try:
            steps = parse_steps(workflow.fields.get("Steps"))
        except Exception as exc:
            message = f"Unable to parse workflow steps: {exc}"
            return ExecutionResult(
                workflow.id,
                workflow.name,
                "failed",
                [],
                [],
                [],
                None,
                [message],
            )

        trace: list[StepResult] = []
        tools_used: list[str] = []
        decisions: list[Any] = []
        errors: list[str] = []

        for index, step in enumerate(steps):
            try:
                outcome = self._step_handler(step, context)
                if not isinstance(outcome, StepHandlerResult):
                    outcome = StepHandlerResult(result=outcome)
                if outcome.tool_used and outcome.tool_used not in tools_used:
                    tools_used.append(outcome.tool_used)
                decisions.extend(outcome.decisions)
                trace.append(
                    StepResult(
                        name=step.name,
                        status="success",
                        tool_used=outcome.tool_used,
                        result=outcome.result,
                    )
                )
            except Exception as exc:
                message = f"Step '{step.name}' failed: {exc}"
                errors.append(message)
                trace.append(StepResult(name=step.name, status="failed", error=str(exc)))
                if self._stop_on_failure:
                    for skipped_step in steps[index + 1:]:
                        trace.append(StepResult(name=skipped_step.name, status="skipped"))
                    break

        failed = bool(errors)
        final_output = context.state.get("final_output")
        if final_output is None and trace:
            completed = [step.result for step in trace if step.status == "success"]
            final_output = completed[-1] if completed else None
        return ExecutionResult(
            workflow_id=workflow.id,
            workflow_name=workflow.name,
            status="failed" if failed else "success",
            steps_executed=trace,
            tools_used=tools_used,
            decisions=decisions,
            final_output=final_output,
            errors=errors,
        )
