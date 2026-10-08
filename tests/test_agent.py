import json

from app.agent import Agent
from app.models import Workflow
from app.tool_registry import ToolRegistry
from app.tools import register_default_tools


class FakeLLM:
    def __init__(self, workflow_id: str):
        self.workflow_id = workflow_id

    def complete(self, prompt: str) -> str:
        return json.dumps({
            "workflow_id": self.workflow_id,
            "reason": "The request matches the supplied workflow metadata.",
            "confidence": 0.95,
        })


def test_agent_runs_inventory_request_with_local_data() -> None:
    workflows = [Workflow(
        "future-id", "Inventory analysis",
        {
            "Workflow_ID": "future-id", "Workflow_Name": "Inventory analysis",
            "Inputs": "Product inventory CSV; minimum stock threshold",
            "Steps": "Load inventory → compare current stock with minimum threshold → generate restock list",
            "Tools_Required": "CSV reader; calculator",
        },
    )]
    result = Agent(
        workflows, FakeLLM("future-id"),
        register_default_tools(ToolRegistry()),
    ).run("Check today's inventory")

    assert result.status == "success"
    assert result.workflow_id == "future-id"
    assert result.execution is not None
    assert len(result.execution.steps_executed) == 3
    assert result.execution.tools_used
    assert result.execution.final_output is not None


def test_agent_returns_selection_failure_for_unknown_request() -> None:
    class UnknownLLM:
        def complete(self, prompt: str) -> str:
            return '{"workflow_id": "missing", "reason": "no match", "confidence": 0.9}'

    result = Agent([], UnknownLLM(), ToolRegistry()).run("unsupported request")
    assert result.status == "failed"
    assert result.errors


def test_agent_surfaces_tool_failure_in_execution_result() -> None:
    workflow = Workflow(
        "generic", "Generic",
        {"Steps": "Load inventory", "Inputs": "Product inventory CSV", "Tools_Required": "CSV reader"},
    )
    registry = ToolRegistry()
    registry.register("tabular_file_reader", lambda args: (_ for _ in ()).throw(RuntimeError("broken tool")))
    result = Agent([workflow], FakeLLM("generic"), registry).run("request")
    assert result.status == "failed"
    assert result.execution is not None
    assert result.execution.steps_executed[0].status == "failed"
    assert "broken tool" in result.execution.errors[0]


def test_agent_runs_product_price_validation_from_metadata() -> None:
    workflow = Workflow(
        "price-workflow", "Price validation",
        {
            "Inputs": "Product CSV; vendor price list",
            "Steps": "Load product prices → load vendor price list → match products by SKU → calculate percentage difference",
            "Tools_Required": "CSV reader; calculator",
        },
    )
    result = Agent(
        [workflow], FakeLLM("price-workflow"),
        register_default_tools(ToolRegistry()),
    ).run("Validate product prices")

    assert result.status == "success"
    assert result.execution is not None
    assert "record_matcher" in result.execution.tools_used
    assert len(result.execution.steps_executed) == 4


def test_agent_returns_structured_missing_input() -> None:
    workflow = Workflow(
        "order-workflow", "Order status",
        {
            "Inputs": "Order ID or customer email",
            "Steps": "Validate identifier → search order data",
            "Tools_Required": "Order database/API",
        },
    )
    result = Agent([workflow], FakeLLM("order-workflow"), register_default_tools(ToolRegistry())).run(
        "Where is my order?"
    )

    assert result.status == "failed"
    assert result.execution is not None
    assert "Missing required input" in result.execution.errors[0]
