"""Command-line entry point for displaying discovered workflows."""

import json
import re
from typing import Any

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


def _json_safe(value: Any, active_ids: set[int] | None = None):
    """Create a display-only JSON-compatible copy without mutating the result."""
    active_ids = set() if active_ids is None else active_ids
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    value_id = id(value)
    if value_id in active_ids:
        return "[repeated nested value omitted]"
    active_ids.add(value_id)
    try:
        if isinstance(value, dict):
            return {
                str(key): _json_safe(item, active_ids)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple, set)):
            return [_json_safe(item, active_ids) for item in value]
        return str(value)
    finally:
        active_ids.remove(value_id)


def _nested_dicts(value: Any, active_ids: set[int] | None = None) -> list[dict[str, Any]]:
    """Collect nested dictionaries without recursing forever through cycles."""
    active_ids = set() if active_ids is None else active_ids
    if not isinstance(value, (dict, list, tuple, set)):
        return []
    value_id = id(value)
    if value_id in active_ids:
        return []
    active_ids.add(value_id)
    try:
        if isinstance(value, dict):
            found = [value]
            children = value.values()
        else:
            found = []
            children = value
        for child in children:
            found.extend(_nested_dicts(child, active_ids))
        return found
    finally:
        active_ids.remove(value_id)


def _as_number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _unique_records(records: list[dict[str, Any]], key_fields: tuple[str, ...]) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for record in records:
        key = tuple(record.get(field) for field in key_fields)
        if any(value is not None for value in key) and key not in seen:
            seen.add(key)
            unique.append(record)
    return unique


def _format_final_result(execution) -> str:
    """Create a generic business-readable view of execution output."""
    sources = [execution.final_output]
    sources.extend(step.result for step in execution.steps_executed if step.result is not None)
    records = _nested_dicts(sources)

    inventory = _unique_records(
        [
            record for record in records
            if {"sku", "product_name", "current_stock", "minimum_stock"} <= record.keys()
        ],
        ("sku",),
    )
    low_stock = [
        record for record in inventory
        if (_as_number(record["current_stock"]) is not None
            and _as_number(record["minimum_stock"]) is not None
            and _as_number(record["current_stock"]) < _as_number(record["minimum_stock"]))
    ]
    if low_stock:
        lines = [f"Restock required for {len(low_stock)} products:"]
        for record in low_stock:
            reorder = record.get("reorder_quantity")
            if reorder is None:
                current = _as_number(record["current_stock"])
                minimum = _as_number(record["minimum_stock"])
                reorder = minimum - current if current is not None and minimum is not None else "unknown"
            lines.append(
                f"- {record['product_name']} ({record['sku']}): "
                f"current stock {record['current_stock']}, minimum {record['minimum_stock']}, "
                f"reorder {reorder:g}" if isinstance(reorder, float) else
                f"- {record['product_name']} ({record['sku']}): "
                f"current stock {record['current_stock']}, minimum {record['minimum_stock']}, "
                f"reorder {reorder}"
            )
        return "\n".join(lines)

    flagged_price_records = [
        item
        for record in records
        if record.get("flagged") is True and isinstance(record.get("records"), list)
        for item in record["records"]
        if isinstance(item, dict)
    ]
    prices = _unique_records(
        [
            record for record in records
            if {"sku", "percentage_difference"} <= record.keys()
            and ("vendor_price" in record or "internal_price" in record)
        ],
        ("sku",),
    )
    flagged_prices = _unique_records(
        [
            record for record in flagged_price_records
            if {"sku", "percentage_difference"} <= record.keys()
        ],
        ("sku",),
    )
    if flagged_prices:
        prices = flagged_prices
    if prices:
        lines = [f"Price validation found {len(prices)} exception(s):"]
        for record in prices:
            percentage = _as_number(record.get("percentage_difference"))
            percentage_text = f"{percentage:.2f}" if percentage is not None else str(
                record.get("percentage_difference")
            )
            lines.append(
                f"- {record.get('product_name', record['sku'])} ({record['sku']}): "
                f"{percentage_text}% difference "
                f"(internal {record.get('internal_price')}, vendor {record.get('vendor_price')})"
            )
        return "\n".join(lines)

    orders = _unique_records(
        [
            record for record in records
            if "order_id" in record and ("status" in record or "shipment_status" in record)
        ],
        ("order_id", "status", "shipment_status", "tracking_number"),
    )
    if orders:
        lines = ["Order status:"]
        for record in orders:
            details = [f"status {record['status']}"] if "status" in record else []
            if "shipment_status" in record:
                details.append(f"shipment {record['shipment_status']}")
            if "tracking_number" in record:
                details.append(f"tracking {record['tracking_number']}")
            lines.append(f"- {record['order_id']}: {', '.join(details)}")
        return "\n".join(lines)

    display_value = _json_safe(execution.final_output)
    return json.dumps(display_value, indent=2, ensure_ascii=False)


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
        print("Final Result:")
        print(_format_final_result(result.execution))
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
