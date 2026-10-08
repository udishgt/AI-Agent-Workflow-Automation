"""Application orchestrator connecting selection, resolution, tools, and execution."""

from __future__ import annotations

import re
from typing import Any, Sequence

from app.executor import WorkflowExecutor
from app.llm_client import LLMClient
from app.models import AgentResult, ExecutionContext, StepHandlerResult, Workflow
from app.step_resolver import StepResolutionError, StepResolver
from app.tool_registry import ToolRegistry
from app.workflow_selector import WorkflowSelectionError, select_workflow


class Agent:
    """Reusable workflow agent; business behavior remains in metadata and tools."""

    def __init__(
        self,
        workflows: Sequence[Workflow],
        llm_client: LLMClient,
        registry: ToolRegistry,
        *,
        sample_data_dir: str = "data/sample_data",
    ) -> None:
        self._workflows = workflows
        self._llm_client = llm_client
        self._registry = registry
        self._resolver = StepResolver(registry, sample_data_dir)

    def run(self, user_request: str) -> AgentResult:
        try:
            selection = select_workflow(user_request, self._workflows, self._llm_client)
            workflow = next(item for item in self._workflows if item.id == selection.workflow_id)
            plans = self._resolver.resolve(workflow, user_request)
            context = ExecutionContext(user_request, {"plans": plans, "decision_logic": workflow.fields.get("Decision_Logic")})

            def handler(step, execution_context):
                plan = next(item for item in plans if item.step == step)
                if plan.error:
                    raise ValueError(plan.error)
                arguments = dict(plan.arguments)
                datasets = execution_context.state.setdefault("datasets", [])
                if plan.tool_name == "record_matcher" and plan.arguments.get("right_path"):
                    loaded = self._registry.execute(
                        "tabular_file_reader", {"path": plan.arguments["right_path"]}
                    )
                    if not loaded.success:
                        raise RuntimeError(loaded.error)
                    arguments["right"] = loaded.result["rows"]
                    arguments["left"] = execution_context.state.get("rows", [])
                    arguments["key"] = plan.arguments.get("key", "sku")
                if plan.tool_name == "record_matcher" and len(datasets) >= 2:
                    arguments.update({"left": datasets[-2], "right": datasets[-1], "key": "sku"})
                if plan.tool_name == "numeric_calculator" and arguments.get("operation") == "percentage_difference":
                    arguments["records"] = execution_context.state.get("matched", [])
                if plan.tool_name in {"record_validator", "threshold_checker"}:
                    arguments["records"] = execution_context.state.get("rows", [])
                if plan.tool_name == "numeric_calculator" and arguments.get("operation") == "reorder_quantity":
                    arguments["records"] = execution_context.state.get("rows", [])
                if (
                    plan.tool_name == "numeric_calculator"
                    and "records" in arguments
                    and arguments.get("operation") != "percentage_difference"
                ):
                    arguments["records"] = execution_context.state.get("rows", [])
                if plan.tool_name == "error_analyzer":
                    arguments["records"] = execution_context.state.get("rows", [])
                if plan.tool_name == "report_builder":
                    arguments["sections"] = {
                        "step_results": execution_context.state.get("step_results", [])
                    }
                if plan.tool_name in {"record_lookup", "shipment_lookup"} and plan.arguments.get("path"):
                    loaded = self._registry.execute(
                        "tabular_file_reader", {"path": plan.arguments["path"]}
                    )
                    if not loaded.success:
                        raise RuntimeError(loaded.error)
                    arguments["records"] = loaded.result["rows"]
                    if plan.tool_name == "record_lookup":
                        match = re.search(r"\b(?:ord|order)[-_ ]?\d+\b", user_request, re.I)
                        if match:
                            arguments["criteria"] = {"order_id": match.group(0).upper().replace("ORDER", "").replace(" ", "").replace("-", "")}
                    if plan.tool_name == "shipment_lookup":
                        match = re.search(r"\b(?:ord|order)[-_ ]?\d+\b", user_request, re.I)
                        if match:
                            arguments["order_id"] = match.group(0).upper().replace("ORDER", "").replace(" ", "").replace("-", "")
                result = self._registry.execute(plan.tool_name, arguments)
                if not result.success:
                    raise RuntimeError(result.error)
                decision_logic = str(execution_context.state.get("decision_logic", "")).lower()
                if (
                    isinstance(result.result, dict)
                    and result.result.get("found") is False
                    and "no order" in decision_logic
                ):
                    raise ValueError(
                        "Decision requires another identifier: no order was found"
                    )
                if isinstance(result.result, dict) and "rows" in result.result:
                    execution_context.state["rows"] = result.result["rows"]
                    datasets.append(result.result["rows"])
                if isinstance(result.result, dict) and "matched" in result.result:
                    execution_context.state["matched"] = result.result["matched"]
                if isinstance(result.result, dict) and "result" in result.result:
                    execution_context.state["rows"] = (
                        result.result["result"]
                        if isinstance(result.result["result"], list)
                        else execution_context.state.get("rows", [])
                    )
                execution_context.state["final_output"] = result.result
                execution_context.state.setdefault("step_results", []).append(
                    {"step": step.name, "tool": plan.tool_name, "result": result.result}
                )
                decisions = []
                if not execution_context.state.get("decision_recorded"):
                    decisions.append(execution_context.state.get("decision_logic"))
                    execution_context.state["decision_recorded"] = True
                return StepHandlerResult(result.result, plan.tool_name, decisions)

            execution = WorkflowExecutor(handler).execute(workflow, user_request, context)
            return AgentResult(
                user_request, workflow.id, workflow.name, selection.reason,
                selection.confidence, execution, execution.status, execution.errors,
            )
        except (WorkflowSelectionError, StepResolutionError, ValueError, StopIteration) as exc:
            return AgentResult(user_request, status="failed", errors=[str(exc)])
