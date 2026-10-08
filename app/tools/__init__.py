"""Reusable, workflow-agnostic tools."""

from app.tool_registry import ToolRegistry
from app.tools.core import build_default_tools


def register_default_tools(
    registry: ToolRegistry,
    *,
    llm_client=None,
) -> ToolRegistry:
    """Register all reusable tools with a registry."""
    for name, tool in build_default_tools(llm_client=llm_client).items():
        registry.register(name, tool)
    return registry


__all__ = ["register_default_tools"]
