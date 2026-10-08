"""Generic registry for dynamically resolved workflow tools."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any


Tool = Callable[[dict[str, Any]], Any]


@dataclass(frozen=True)
class ToolExecutionResult:
    """Structured outcome of a tool lookup or invocation."""

    tool_name: str
    success: bool
    result: Any = None
    error: str | None = None


class ToolRegistry:
    """Register and invoke tools by name without workflow-specific knowledge."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, name: str, tool: Tool) -> None:
        """Register a callable under a non-empty tool name."""
        normalized_name = self._validate_name(name)
        if not callable(tool):
            raise TypeError(f"Tool '{normalized_name}' must be callable")
        if normalized_name in self._tools:
            raise ValueError(f"Tool already registered: {normalized_name}")
        self._tools[normalized_name] = tool

    def get(self, name: str) -> Tool | None:
        """Return a registered tool, or None when it is not registered."""
        return self._tools.get(self._validate_name(name))

    def list_tools(self) -> list[str]:
        """Return registered tool names in registration order."""
        return list(self._tools)

    def execute(
        self,
        name: str,
        arguments: Mapping[str, Any] | None = None,
    ) -> ToolExecutionResult:
        """Execute a registered tool and capture lookup or invocation failures."""
        try:
            normalized_name = self._validate_name(name)
        except (TypeError, ValueError) as exc:
            return ToolExecutionResult(str(name), False, error=str(exc))

        tool = self._tools.get(normalized_name)
        if tool is None:
            return ToolExecutionResult(
                normalized_name,
                False,
                error=f"Unknown tool: {normalized_name}",
            )

        tool_arguments = dict(arguments or {})
        try:
            return ToolExecutionResult(
                normalized_name,
                True,
                result=tool(tool_arguments),
            )
        except Exception as exc:
            return ToolExecutionResult(
                normalized_name,
                False,
                error=f"Tool '{normalized_name}' failed: {exc}",
            )

    @staticmethod
    def _validate_name(name: str) -> str:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Tool name must be a non-empty string")
        return name.strip()
