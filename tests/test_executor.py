import pytest

from app.executor import WorkflowExecutor
from app.models import ExecutionContext, StepHandlerResult, Workflow


def workflow(steps: str) -> Workflow:
    return Workflow(
        workflow_id="future-workflow",
        workflow_name="Generic workflow",
        fields={"Workflow_ID": "future-workflow", "Workflow_Name": "Generic workflow", "Steps": steps},
    )


def test_successful_multi_step_execution_preserves_context() -> None:
    def handler(step, context):
        context.state[step.name] = len(context.state)
        context.state["final_output"] = f"completed {step.name}"
        return StepHandlerResult(result=context.state[step.name], tool_used="fake-tool")

    context = ExecutionContext("do the generic task", {"initial": "value"})
    result = WorkflowExecutor(handler).execute(
        workflow("Collect input → Transform input → Produce output"),
        context.request,
        context,
    )

    assert result.status == "success"
    assert [step.name for step in result.steps_executed] == [
        "Collect input", "Transform input", "Produce output",
    ]
    assert all(step.status == "success" for step in result.steps_executed)
    assert result.tools_used == ["fake-tool"]
    assert result.final_output == "completed Produce output"
    assert context.state["Collect input"] == 1
    assert context.state["Transform input"] > context.state["Collect input"]


def test_failed_step_is_structured_and_later_steps_are_skipped() -> None:
    def handler(step, context):
        if step.name == "Break here":
            raise RuntimeError("mock failure")
        return "ok"

    result = WorkflowExecutor(handler).execute(
        workflow("Start → Break here → Never run"),
        "request",
        ExecutionContext("request", {}),
    )

    assert result.status == "failed"
    assert [step.status for step in result.steps_executed] == ["success", "failed", "skipped"]
    assert "mock failure" in result.errors[0]
    assert result.steps_executed[-1].error is None


def test_can_continue_after_failure_when_configured() -> None:
    def handler(step, context):
        if step.name == "Fail":
            raise ValueError("bad input")
        return "done"

    result = WorkflowExecutor(handler, stop_on_failure=False).execute(
        workflow("Fail → Continue"),
        "request",
        ExecutionContext("request", {}),
    )

    assert result.status == "failed"
    assert [step.status for step in result.steps_executed] == ["failed", "success"]


def test_records_decisions_and_generic_workflow_identity() -> None:
    def handler(step, context):
        return StepHandlerResult(
            result={"step": step.name},
            decisions=[f"decision for {step.name}"],
        )

    result = WorkflowExecutor(handler).execute(
        workflow("A → B"),
        "request",
        ExecutionContext("request", {}),
    )

    assert result.workflow_id == "future-workflow"
    assert result.workflow_name == "Generic workflow"
    assert result.decisions == ["decision for A", "decision for B"]


def test_invalid_steps_return_failure_without_crashing() -> None:
    malformed = Workflow("id", "name", {"Steps": 123})

    result = WorkflowExecutor(lambda step, context: None).execute(
        malformed,
        "request",
        ExecutionContext("request", {}),
    )

    assert result.status == "failed"
    assert result.steps_executed == []
    assert "Workflow Steps must be text" in result.errors[0]
