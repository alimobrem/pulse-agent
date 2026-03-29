"""Central tool registry — all @beta_tool functions register here."""

from typing import Any

TOOL_REGISTRY: dict[str, Any] = {}
WRITE_TOOL_NAMES: set[str] = set()


def register_tool(tool: Any, is_write: bool = False) -> Any:
    """Register a tool in the central registry."""
    TOOL_REGISTRY[tool.name] = tool
    if is_write:
        WRITE_TOOL_NAMES.add(tool.name)
    return tool


def get_all_tools() -> list:
    return list(TOOL_REGISTRY.values())


def get_tool_map() -> dict:
    return dict(TOOL_REGISTRY)


def get_write_tools() -> set[str]:
    return set(WRITE_TOOL_NAMES)
