from app.models import Workflow
from app.step_resolver import StepResolver
from app.tool_registry import ToolRegistry
from app.tools import register_default_tools


def test_resolver_uses_metadata_and_does_not_need_workflow_ids() -> None:
    workflow = Workflow(
        "arbitrary-id",
        "Arbitrary",
        {
            "Steps": "Load inventory → compare current stock with minimum threshold",
            "Inputs": "Product inventory CSV; minimum stock threshold",
            "Tools_Required": "CSV reader; calculator",
        },
    )
    plans = StepResolver(register_default_tools(ToolRegistry())).resolve(workflow, "request")

    assert [plan.tool_name for plan in plans] == ["tabular_file_reader", "threshold_checker"]
    assert plans[0].error is None


def test_unresolved_step_is_structured() -> None:
    workflow = Workflow("id", "name", {"Steps": "Perform an unspecified operation", "Tools_Required": "unknown"})
    plans = StepResolver(register_default_tools(ToolRegistry())).resolve(workflow, "request")
    assert plans[0].tool_name is None
    assert "Cannot resolve" in plans[0].error
