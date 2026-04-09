"""PromQL and component sanitization helpers."""

from __future__ import annotations

import re

_DOUBLE_BRACE_RE = re.compile(r"\}(\s*)\{")


def _fix_promql(query: str) -> str:
    """Fix common PromQL syntax errors.

    Merges double label blocks: metric{a="1"}{b="2"} -> metric{a="1",b="2"}
    """
    if not query or "{" not in query:
        return query
    return _DOUBLE_BRACE_RE.sub(r",", query)


def _sanitize_components(components: list[dict]) -> list[dict]:
    """Sanitize component specs before saving to views.

    Fixes invalid PromQL in metric_card queries.
    """
    for comp in components:
        if comp.get("kind") == "metric_card" and comp.get("query"):
            comp["query"] = _fix_promql(comp["query"])
        # Handle grids/tabs/sections that contain nested components
        for container_key in ("items", "components"):
            nested = comp.get(container_key)
            if isinstance(nested, list):
                _sanitize_components(nested)
        # Handle tabs with nested components
        tabs = comp.get("tabs")
        if isinstance(tabs, list):
            for tab in tabs:
                tab_comps = tab.get("components")
                if isinstance(tab_comps, list):
                    _sanitize_components(tab_comps)
    return components
