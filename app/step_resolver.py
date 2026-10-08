"""Metadata-driven resolution of workflow steps to reusable tools."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.models import PlannedStep, StepDefinition, Workflow
from app.tool_registry import ToolRegistry
from app.executor import parse_steps


_TOOL_ALIASES = {
    "csv reader": "tabular_file_reader",
    "excel/csv parser": "tabular_file_reader",
    "csv/database reader": "tabular_file_reader",
    "product data reader": "tabular_file_reader",
    "calculator": "numeric_calculator",
    "data validation": "record_validator",
    "text similarity": "similarity_scorer",
    "shipment lookup": "shipment_lookup",
    "order database/api": "record_lookup",
    "employee/task database": "record_lookup",
    "ranking logic": "candidate_ranker",
    "llm/classifier": "text_classifier",
    "llm": "text_generator",
    "reporting": "report_builder",
}

_STEP_HINTS = (
    (("success/failure rate", "average execution time"), "numeric_calculator"),
    (("threshold", "flag", "low-stock", "failure rate", "above", "below"), "threshold_checker"),
    (("match", "sku"), "record_matcher"),
    (("compare", "percentage", "calculate", "rate", "average", "quantity"), "numeric_calculator"),
    (("validate", "invalid", "required"), "record_validator"),
    (("load", "read", "file", "products", "inventory", "logs", "keywords"), "tabular_file_reader"),
    (("normalize",), "text_normalizer"),
    (("duplicate", "similarity"), "similarity_scorer"),
    (("classify", "intent"), "text_classifier"),
    (("search", "retrieve", "find"), "record_lookup"),
    (("shipment", "tracking"), "shipment_lookup"),
    (("detect columns",), "schema_normalizer"),
    (("remove duplicates",), "text_normalizer"),
    (("group likely duplicates", "assign confidence"), "similarity_scorer"),
    (("compare identifiers", "compare product attributes"), "similarity_scorer"),
    (("identify campaign objective", "campaign checklist"), "text_generator"),
    (("check current workload",), "capacity_checker"),
    (("understand task requirements",), "text_classifier"),
    (("frequent errors",), "error_analyzer"),
    (("slow steps",), "numeric_calculator"),
    (("rank", "candidate", "select employee"), "candidate_ranker"),
    (("report", "list", "produce", "export", "recommendations"), "report_builder"),
    (("description", "messaging", "title", "generate", "summary"), "text_generator"),
    (("summarize",), "text_summarizer"),
)


class StepResolutionError(ValueError):
    """Raised when workflow metadata cannot safely resolve a step."""


class StepResolver:
    """Resolve steps using tool metadata and an explicit local data directory."""

    def __init__(self, registry: ToolRegistry, sample_data_dir: str | Path = "data/sample_data"):
        self._registry = registry
        self._sample_data_dir = Path(sample_data_dir)

    def resolve(self, workflow: Workflow, request: str) -> list[PlannedStep]:
        steps = parse_steps(workflow.fields.get("Steps"))
        required_text = str(workflow.fields.get("Tools_Required", "")).lower()
        inputs_text = str(workflow.fields.get("Inputs", "")).lower()
        available = self._available_tools(required_text)
        available |= set(self._registry.list_tools())
        plans: list[PlannedStep] = []
        missing_input = self._missing_input(inputs_text, request)
        for step in steps:
            if missing_input:
                plans.append(PlannedStep(step, None, {}, missing_input))
                continue
            tool_name = self._choose_tool(step.name.lower(), available)
            if tool_name is None:
                plans.append(PlannedStep(step, None, {}, f"Cannot resolve step: {step.name}"))
                continue
            arguments = self._arguments(tool_name, step.name.lower(), inputs_text, request)
            if "path" not in arguments and tool_name == "tabular_file_reader":
                plans.append(PlannedStep(step, tool_name, arguments, "Missing local data file for step"))
            else:
                plans.append(PlannedStep(step, tool_name, arguments))
        return plans

    def _available_tools(self, required_text: str) -> set[str]:
        available = {
            tool for alias, tool in _TOOL_ALIASES.items()
            if alias in required_text
        }
        available.add("report_builder")
        available &= set(self._registry.list_tools())
        for alias, tool in _TOOL_ALIASES.items():
            if alias in required_text and tool not in self._registry.list_tools():
                raise StepResolutionError(f"Required tool is not registered: {tool}")
        return available

    def _choose_tool(self, step: str, available: set[str]) -> str | None:
        for hints, tool in _STEP_HINTS:
            if tool in available and any(
                re.search(rf"(?<![a-z0-9]){re.escape(hint)}(?![a-z0-9])", step)
                for hint in hints
            ):
                return tool
        return None

    def _arguments(self, tool: str, step: str, inputs: str, request: str) -> dict[str, Any]:
        if tool == "tabular_file_reader":
            candidates = (
                ("inventory.csv", ("inventory",)),
                ("product_prices.csv", ("product price", "product csv")),
                ("vendor_prices.csv", ("vendor price",)),
                ("vendor_products.csv", ("vendor file", "vendor product")),
                ("product_catalog.csv", ("product catalog", "catalog")),
                ("campaign_products.csv", ("product list", "campaign")),
                ("keywords.csv", ("keyword",)),
                ("employees.json", ("employee",)),
                ("tasks.json", ("task",)),
                ("execution_logs.json", ("execution log", "workflow execution")),
            )
            step_match = next(
                (
                    (candidate, phrases)
                    for candidate, phrases in candidates
                    if any(phrase in step for phrase in phrases)
                ),
                None,
            )
            if step_match:
                return {"path": str(self._sample_data_dir / step_match[0])}
            for candidate, phrases in candidates:
                if any(phrase in inputs for phrase in phrases):
                    return {"path": str(self._sample_data_dir / candidate)}
            if "vendor" in step and "price" in step:
                return {"path": str(self._sample_data_dir / "vendor_prices.csv")}
            if "inventory" in step or "inventory" in inputs:
                return {"path": str(self._sample_data_dir / "inventory.csv")}
            return {}
        if tool == "text_classifier":
            return {"text": request, "constraints": [inputs]}
        if tool == "record_matcher" and "vendor price" in inputs:
            return {
                "right_path": str(self._sample_data_dir / "vendor_prices.csv"),
                "key": "sku",
            }
        if tool == "record_lookup" and "order" in inputs:
            return {"path": str(self._sample_data_dir / "orders.json")}
        if tool == "shipment_lookup" and "shipment" in inputs:
            return {"path": str(self._sample_data_dir / "shipments.json")}
        if tool == "record_validator":
            if "required fields" in step or "invalid rows" in step:
                return {"required_fields": ["sku", "product_name"], "records": []}
            return {"records": []}
        if tool == "schema_normalizer":
            return {"columns": ["SKU", "Product Name", "Category", "Price"]}
        if tool in {"text_classifier", "text_generator"}:
            return {"facts": {"request": request, "inputs": inputs}, "constraints": ["Use supplied facts only"]}
        if tool == "capacity_checker":
            return {"workload": 0, "capacity": 1}
        if tool == "error_analyzer":
            return {"records": []}
        if tool == "similarity_scorer":
            return {"left": "", "right": ""}
        if tool == "numeric_calculator":
            if "success/failure rate" in step:
                return {"operation": "success_failure_rate", "records": []}
            if "average execution time" in step:
                return {"operation": "average_field", "field": "duration_seconds", "records": []}
            if "percentage" in step:
                return {"operation": "percentage_difference", "records": []}
            if "quantity" in step or "reorder" in step:
                return {"operation": "reorder_quantity", "records": []}
            return {"operation": "sum", "values": []}
        if tool == "threshold_checker" and ("stock" in step or "minimum" in step):
            return {
                "value_field": "current_stock",
                "threshold_field": "minimum_stock",
                "operator": "<",
                "records": [],
            }
        if tool == "threshold_checker" and ("price" in step or "exception" in step):
            return {
                "value_field": "percentage_difference",
                "threshold": 10,
                "operator": ">",
                "records": [],
            }
        if tool in {"text_generator", "text_summarizer"}:
            return {"facts": {"request": request, "inputs": inputs}, "constraints": ["Use supplied facts only"]}
        return {"request": request}

    @staticmethod
    def _missing_input(inputs: str, request: str) -> str | None:
        if "order id" in inputs and not re.search(r"\b(?:ord|order)[-_ ]?\d+\b", request, re.I):
            if "customer email" not in inputs or not re.search(r"[^@\s]+@[^@\s]+", request):
                return "Missing required input: order ID or customer email"
        return None
