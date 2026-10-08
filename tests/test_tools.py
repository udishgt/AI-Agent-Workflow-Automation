import json
from pathlib import Path

from app.tool_registry import ToolRegistry
from app.tools import register_default_tools


EXPECTED_TOOLS = {
    "tabular_file_reader", "file_exporter", "schema_normalizer",
    "record_validator", "record_lookup", "shipment_lookup", "record_matcher",
    "text_normalizer", "similarity_scorer", "numeric_calculator",
    "threshold_checker", "priority_scorer", "capacity_checker",
    "candidate_ranker", "text_classifier", "text_validator", "text_generator",
    "text_summarizer", "error_analyzer", "recommendation_generator",
    "report_builder",
}


class FakeLLM:
    def complete(self, prompt: str) -> str:
        return json.dumps({"output": "grounded result"})


def test_register_default_tools_registers_complete_generic_set() -> None:
    registry = register_default_tools(ToolRegistry(), llm_client=FakeLLM())

    assert set(registry.list_tools()) == EXPECTED_TOOLS


def test_file_reader_and_exporter_use_local_data(tmp_path: Path) -> None:
    registry = register_default_tools(ToolRegistry())
    source = Path("data/sample_data/inventory.csv")

    read_result = registry.execute("tabular_file_reader", {"path": str(source)})
    assert read_result.success is True
    assert len(read_result.result["rows"]) == 3

    output = tmp_path / "inventory.json"
    export_result = registry.execute(
        "file_exporter",
        {"path": str(output), "rows": read_result.result["rows"]},
    )
    assert export_result.success is True
    assert json.loads(output.read_text(encoding="utf-8"))[0]["sku"] == "P100"


def test_validation_matching_and_deterministic_calculations() -> None:
    registry = register_default_tools(ToolRegistry())
    validation = registry.execute(
        "record_validator",
        {"records": [{"sku": "A"}, {"name": "missing sku"}], "required_fields": ["sku", "name"]},
    )
    assert validation.result["valid_count"] == 0
    assert validation.result["invalid_count"] == 2

    calculation = registry.execute(
        "numeric_calculator",
        {"operation": "percentage_difference", "values": [100, 110]},
    )
    threshold = registry.execute(
        "threshold_checker",
        {"value": calculation.result["result"], "threshold": 10, "operator": ">"},
    )
    assert calculation.result["result"] == 10
    assert threshold.result["flagged"] is False


def test_lookup_shipment_normalization_and_ranking() -> None:
    registry = register_default_tools(ToolRegistry())
    lookup = registry.execute(
        "record_lookup",
        {"records": [{"id": "1", "status": "open"}], "criteria": {"id": "1"}},
    )
    shipment = registry.execute(
        "shipment_lookup",
        {"records": [{"order_id": "O1", "tracking_number": "T1"}], "order_id": "O1"},
    )
    ranked = registry.execute(
        "candidate_ranker",
        {"candidates": [{"name": "a", "score": 1}, {"name": "b", "score": 3}]},
    )
    assert lookup.result["found"] is True
    assert shipment.result["matches"][0]["tracking_number"] == "T1"
    assert ranked.result["ranked"][0]["name"] == "b"


def test_llm_tools_use_injected_client_and_do_not_need_real_credentials() -> None:
    registry = register_default_tools(ToolRegistry(), llm_client=FakeLLM())

    result = registry.execute(
        "text_generator",
        {"facts": {"product_name": "Mug"}, "constraints": ["Do not invent attributes"]},
    )

    assert result.success is True
    assert result.result == {"output": "grounded result"}


def test_llm_tools_return_structured_error_without_client() -> None:
    result = register_default_tools(ToolRegistry()).execute(
        "text_summarizer",
        {"facts": {"status": "shipped"}},
    )

    assert result.success is False
    assert "LLM client is required" in result.error


def test_reporting_tools_return_structured_results() -> None:
    registry = register_default_tools(ToolRegistry())
    errors = registry.execute(
        "error_analyzer",
        {"records": [{"error": "bad"}, {"error": "bad"}, {"error": ""}]},
    )
    report = registry.execute(
        "report_builder",
        {"title": "Summary", "sections": {"errors": errors.result}},
    )
    assert errors.result["error_counts"] == {"bad": 2}
    assert report.result["title"] == "Summary"
