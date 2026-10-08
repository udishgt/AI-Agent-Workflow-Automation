import pytest

from app.tool_registry import ToolRegistry


def test_register_and_retrieve_tool() -> None:
    registry = ToolRegistry()

    def fake_tool(arguments: dict[str, object]) -> str:
        return str(arguments["value"])

    registry.register("fake_tool", fake_tool)

    assert registry.get("fake_tool") is fake_tool


def test_execute_registered_tool_with_arguments() -> None:
    registry = ToolRegistry()
    registry.register("adder", lambda arguments: arguments["left"] + arguments["right"])

    result = registry.execute("adder", {"left": 2, "right": 3})

    assert result.success is True
    assert result.tool_name == "adder"
    assert result.result == 5
    assert result.error is None


def test_unknown_tool_returns_structured_error() -> None:
    result = ToolRegistry().execute("missing_tool", {"value": 1})

    assert result.success is False
    assert result.result is None
    assert result.error == "Unknown tool: missing_tool"


def test_tool_failure_returns_structured_error() -> None:
    def failing_tool(arguments: dict[str, object]) -> None:
        raise RuntimeError("input was invalid")

    registry = ToolRegistry()
    registry.register("failing_tool", failing_tool)

    result = registry.execute("failing_tool")

    assert result.success is False
    assert result.error == "Tool 'failing_tool' failed: input was invalid"


def test_lists_registered_tools() -> None:
    registry = ToolRegistry()
    registry.register("first", lambda arguments: None)
    registry.register("second", lambda arguments: None)

    assert registry.list_tools() == ["first", "second"]


def test_rejects_invalid_and_duplicate_registration() -> None:
    registry = ToolRegistry()
    with pytest.raises(ValueError, match="non-empty"):
        registry.register(" ", lambda arguments: None)
    registry.register("tool", lambda arguments: None)
    with pytest.raises(ValueError, match="already registered"):
        registry.register("tool", lambda arguments: None)
