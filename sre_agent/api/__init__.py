"""Pulse Agent API package.

Re-exports key symbols for backward compatibility:
    from sre_agent.api import app
    from sre_agent.api import _get_current_user, _user_cache, _USER_CACHE_MAX, _cache_user
    from sre_agent.api import _fix_promql, _sanitize_components
    from sre_agent.api import _build_tool_result_handler
"""

from .agent_ws import _build_tool_result_handler
from .app import app
from .auth import _USER_CACHE_MAX, _cache_user, _get_current_user, _user_cache
from .sanitize import _fix_promql, _sanitize_components

__all__ = [
    "_USER_CACHE_MAX",
    "_build_tool_result_handler",
    "_cache_user",
    "_fix_promql",
    "_get_current_user",
    "_sanitize_components",
    "_user_cache",
    "app",
]
