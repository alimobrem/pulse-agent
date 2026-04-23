# User OAuth Token Forwarding

**Date:** 2026-04-22
**Status:** Draft
**Author:** Ali + Claude

## Problem

Pulse Agent executes all K8s API calls using its ServiceAccount token. Users see resources they shouldn't have access to, and write operations execute under the agent's identity rather than the user's. This bypasses RBAC enforcement and breaks audit trail attribution.

## Goal

When a user is connected via WebSocket, all K8s API calls (reads and writes) execute using the user's OAuth token. The K8s API server enforces RBAC — the agent never does authorization itself. Monitor background scans continue using the ServiceAccount token.

## Architecture Decision

**Direct token forwarding** — the same pattern used by OpenShift Console and Kubernetes Dashboard. The user's OAuth token is forwarded to the K8s API server as `Authorization: Bearer <token>`. The API server validates the token and enforces RBAC. No impersonation, no SubjectAccessReviews.

Why not impersonation: impersonation requires explicit group forwarding. OpenShift RBAC is heavily group-based (`dedicated-admins`, project groups). Missing a group silently drops permissions. The user's real token carries all identity (user, groups, scopes) natively.

## Token Source

The oauth-proxy sidecar handles the OpenShift OAuth flow and passes the user's access token to the backend via `X-Forwarded-Access-Token` HTTP header on every request, including the WebSocket upgrade. The frontend never touches the token directly — it lives in an HTTP-only cookie managed by the proxy.

The token is available at WebSocket handshake time. `ws_endpoints.py` already reads this header (lines 99-100) for `_get_current_user()`.

## Design

### 1. Token Flow

The token is an explicit named parameter at every layer:

```
Browser
  → oauth-proxy (cookie → X-Forwarded-Access-Token header)
  → nginx (forwards header)
  → ws_endpoints.py: extract from websocket.headers at connect time
  → session_state["user_token"]
  → _run_agent_ws(user_token=token)
  → SkillExecutor.__init__(user_token=token)
  → run_agent_streaming(user_token=token)
  → _execute_tool(user_token=token)       # threaded pool
  → _execute_tool_with_timeout(user_token=token)
```

At the `tool.call()` boundary, `_execute_tool` sets a `ContextVar` before invoking the tool and resets it in a `finally` block. This is the only point where implicit state is used — the `@beta_tool` function signature is fixed by Claude's tool schema and cannot accept extra parameters.

```python
# agent.py — _execute_tool
def _execute_tool(name, input_data, tool_map, user_token=None):
    from .k8s_client import _user_token_var

    reset_token = _user_token_var.set(user_token)
    try:
        result = tool.call(input_data)
    finally:
        _user_token_var.reset(reset_token)
```

### 2. k8s_client.py Changes

Add a `ContextVar` and a helper to build per-request clients:

```python
from contextvars import ContextVar

_user_token_var: ContextVar[str | None] = ContextVar("_user_token", default=None)

def _build_api_client(token: str) -> client.ApiClient:
    _load_k8s()
    cfg = client.Configuration.get_default_copy()
    cfg.api_key = {"authorization": f"Bearer {token}"}
    cfg.api_key_prefix = {}
    return client.ApiClient(configuration=cfg)
```

Each `get_*_client()` function checks the contextvar:

```python
def get_core_client() -> client.CoreV1Api:
    token = _user_token_var.get()
    if token:
        return client.CoreV1Api(api_client=_build_api_client(token))
    _load_k8s()
    if "core" not in _clients:
        _clients["core"] = client.CoreV1Api()
    return _clients["core"]
```

When `_user_token_var` is `None` (default), the SA singleton is returned — identical to current behavior. When set, a new `ApiClient` is created with the user's bearer token. The SA singleton is never mutated.

All 8 `get_*_client()` functions follow this pattern: `get_core_client`, `get_apps_client`, `get_custom_client`, `get_version_client`, `get_rbac_client`, `get_networking_client`, `get_batch_client`, `get_autoscaling_client`.

### 3. agent.py Changes

New `user_token` parameter on:

- `run_agent_streaming()` — passed from `SkillExecutor`
- `_execute_tool()` — sets/resets contextvar around `tool.call()`
- `_execute_tool_with_timeout()` — passes through to `_execute_tool`

In the tool execution loop, the token is passed to pool submissions:

```python
# Read tools (parallel)
futures = {
    _tool_pool.submit(_execute_tool, b.name, b.input, tool_map, user_token): b
    for b in read_blocks
}

# Write tools (sequential, after confirmation)
text, component, exec_meta = _execute_tool_with_timeout(
    block.name, block.input, tool_map, user_token=user_token
)
```

### 4. WebSocket Layer Changes

**ws_endpoints.py**: Extract token at connect time, store on session state, pass to `_run_agent_ws`:

```python
user_token = websocket.headers.get("x-forwarded-access-token")
# ... later
await _run_agent_ws(websocket, ..., user_token=user_token)
```

**agent_ws.py**: `_run_agent_ws` passes token to `SkillExecutor`, which passes it to `run_agent_streaming`:

```python
class SkillExecutor:
    def __init__(self, ..., user_token: str | None = None):
        self._user_token = user_token

    def run(self):
        run_agent_streaming(..., user_token=self._user_token)
```

### 5. MCP Token Forwarding

MCP tools execute via `call_mcp_tool()` → `_mcp_post()`. The contextvar is already set by `_execute_tool` before the MCP tool wrapper runs.

`_mcp_post()` reads the contextvar and adds the `Authorization` header:

```python
def _mcp_post(base_url, payload, session_id=""):
    from .k8s_client import _user_token_var

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    token = _user_token_var.get()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    # ... rest unchanged
```

**MCP server fork change required** (separate PR): The openshift-mcp-server must check for an incoming `Authorization` header and use that token for K8s API calls instead of its SA. When no header is present, fall back to SA (backward compatible).

### 6. Monitor Isolation

`MonitorSession` never receives a `user_token` parameter. The contextvar default is `None`. All monitor paths — scanners, `auto_fix()`, `execute_targeted_fix()` in `fix_planner.py` — call `get_*_client()` which returns the SA singleton.

No code changes to `monitor/session.py`, `monitor/scanners.py`, `fix_planner.py`, or `trend_scanners.py`.

### 7. 401 Handling (Token Expiry)

OpenShift OAuth tokens default to 24h. The oauth-proxy refreshes cookies hourly (`--cookie-refresh=1h`), but the WebSocket upgrade headers are fixed at connect time. The token may expire mid-session.

When a K8s API call returns 401 (Unauthorized):

1. `safe()` in `k8s_client.py` catches the `ApiException`
2. `classify_api_error()` in `errors.py` identifies it as a 401
3. The tool returns an error string containing "Unauthorized" to the agent
4. `_execute_tool` detects the 401 in `exec_meta` and sets a flag
5. The WS handler checks the flag and emits a `session_expired` WebSocket event
6. The frontend (Shell.tsx) shows a countdown modal and redirects to re-auth

Note: 403 (Forbidden) is NOT a session expiry — it means the user lacks RBAC permissions for that specific resource. These are returned to the agent as normal tool errors so it can explain the permission gap to the user.

The user reconnects with a fresh WebSocket handshake carrying a refreshed token.

### 8. Security

**Token never logged:** Add `"user_token"` to `_REDACTED_FIELDS` in `agent.py`. The `_redact_input` function already strips sensitive fields from audit logs.

**Token never stored:** The token exists only as a function parameter and a scoped contextvar. It is not persisted to the database, not written to disk, not stored in any long-lived data structure.

**Token never sent to Claude:** The token is used exclusively in K8s API calls and MCP HTTP requests. It is not included in tool results, system prompts, or conversation messages.

**Token never in error messages:** `_execute_tool` catches exceptions and returns only `type(e).__name__` to the LLM. Internal error details are logged (without the token) but not exposed.

**Contextvar scoping:** The `finally` block in `_execute_tool` guarantees the contextvar is reset after every tool call, even on exceptions. Thread pool worker reuse is safe — `ContextVar.reset()` restores the previous value (`None`).

**No cross-session contamination:** Each WebSocket connection has its own `user_token` parameter. The contextvar is set and reset within a single `_execute_tool` invocation. Two concurrent users cannot see each other's tokens.

## What This Does NOT Cover

- Scanner transparency (exposing scanner metadata and results to users) — separate spec
- New scanners (resource quota exhaustion, endpoint health) — separate spec
- MCP server fork changes (accepting and using forwarded tokens) — separate PR
- Frontend changes — none needed (token already forwarded by oauth-proxy)

## Files Changed

| File | Change |
|------|--------|
| `sre_agent/k8s_client.py` | Add `_user_token_var` contextvar, `_build_api_client()`, update 8 `get_*_client()` functions |
| `sre_agent/agent.py` | Add `user_token` param to `run_agent_streaming`, `_execute_tool`, `_execute_tool_with_timeout`; set/reset contextvar in `_execute_tool`; add `"user_token"` to `_REDACTED_FIELDS` |
| `sre_agent/mcp_client.py` | Read contextvar in `_mcp_post()`, add `Authorization` header |
| `sre_agent/api/agent_ws.py` | Add `user_token` param to `SkillExecutor.__init__`, `_run_agent_ws`; pass through to `run_agent_streaming` |
| `sre_agent/api/ws_endpoints.py` | Extract `X-Forwarded-Access-Token` at connect time, pass to `_run_agent_ws` |

**Files NOT changed:**
- `sre_agent/monitor/session.py` — no changes
- `sre_agent/monitor/scanners.py` — no changes
- `sre_agent/monitor/fix_planner.py` — no changes
- `sre_agent/trend_scanners.py` — no changes
- `sre_agent/k8s_tools/*` — no changes (0 of 60 call sites modified)
- Frontend (OpenshiftPulse) — no changes

## Testing

**k8s_client.py unit tests:**
- `get_core_client()` returns SA singleton when contextvar unset
- `get_core_client()` returns user-token client when contextvar set
- `_build_api_client()` configures bearer token correctly
- After `reset()`, SA singleton is returned (thread reuse safety)

**agent.py unit tests:**
- Contextvar is set before `tool.call()` and reset after
- Contextvar is reset even when `tool.call()` raises
- `user_token=None` results in SA client (monitor path)

**MCP unit tests:**
- `_mcp_post()` includes `Authorization` header when contextvar set
- `_mcp_post()` omits `Authorization` header when contextvar unset

**Integration tests:**
- Mock K8s API: user-token path sends `Authorization: Bearer <user_token>`
- Mock K8s API: SA path sends SA token
- 401 response triggers `session_expired` event on WebSocket

**RBAC filtering test:**
- Two mock tokens with different RBAC — verify tool results differ
