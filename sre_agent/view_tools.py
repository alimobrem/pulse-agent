"""Tools for creating custom dashboard views from conversation context."""

from __future__ import annotations

import uuid

from anthropic import beta_tool

from .tool_registry import register_tool


@beta_tool
def create_dashboard(title: str, description: str = "") -> str:
    """Create a custom dashboard view that the user can save and access from the sidebar. Use this when the user asks to create a dashboard, custom view, or persistent display of data. The dashboard will contain the component specs from the current conversation.

    Args:
        title: Name for the dashboard (e.g. "SRE Overview", "Node Health").
        description: Brief description of what the dashboard shows.
    """
    view_id = f"cv-{uuid.uuid4().hex[:12]}"
    # Return a marker that the API layer will intercept and convert to a view_spec event
    return f"__VIEW_SPEC__{view_id}|{title}|{description}"


register_tool(create_dashboard)
