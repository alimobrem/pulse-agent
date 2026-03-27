# Pulse API Contract

**Protocol Version: 2**

Defines the WebSocket protocol between the Pulse UI and Pulse Agent. Both repos must implement the same protocol version for compatibility.

> Source of truth for message schemas. When adding or changing a message type, update this file first, then implement in both repos.

---

## Endpoints

### REST

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/healthz` | Agent health check. Returns `{"status": "ok"}` |
| `GET` | `/version` | Protocol version + capabilities. UI checks this on connect. |

#### `/version` Response

```json
{
  "protocol": "2",
  "agent": "1.4.0",
  "tools": 68,
  "features": ["component_specs", "ws_token_auth", "rate_limiting", "monitor", "fix_history", "predictions"]
}
```

### WebSocket

| Path | Description |
|------|-------------|
| `ws://.../ws/sre` | SRE agent mode |
| `ws://.../ws/security` | Security agent mode |
| `ws://.../ws/monitor` | Autonomous cluster monitoring (Protocol v2) |

---

## Client-to-Server Messages

Messages sent by the UI to the agent over WebSocket.

### `message` — Send a chat message

```json
{
  "type": "message",
  "content": "Why are pods crash-looping in production?",
  "context": {
    "kind": "Deployment",
    "name": "api-server",
    "namespace": "production",
    "gvr": "apps~v1~deployments"
  },
  "fleet": false
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | `"message"` | yes | |
| `content` | `string` | yes | User's message text |
| `context` | `ResourceContext` | no | Resource the user is viewing |
| `fleet` | `boolean` | no | Enable fleet/multi-cluster mode |

#### `ResourceContext`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `kind` | `string` | yes | K8s resource kind (e.g., `"Deployment"`) |
| `name` | `string` | yes | Resource name |
| `namespace` | `string` | no | Resource namespace (omit for cluster-scoped) |
| `gvr` | `string` | no | GVR key (`group~version~plural`) |

### `confirm_response` — Respond to a confirmation request

```json
{
  "type": "confirm_response",
  "approved": true
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | `"confirm_response"` | yes | |
| `approved` | `boolean` | yes | Whether the user approved the action |

### `clear` — Clear conversation history

```json
{
  "type": "clear"
}
```

### `/ws/monitor` Client-to-Server Messages

#### `subscribe_monitor` — Subscribe to cluster monitoring

Sent as the first message after connecting to `/ws/monitor`. Configures the monitoring session.

```json
{
  "type": "subscribe_monitor",
  "trustLevel": 1,
  "autoFixCategories": ["crash_loop", "resource_pressure"]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | `"subscribe_monitor"` | yes | |
| `trustLevel` | `integer` | no | Autonomous action trust level (0–3). Clamped to server-configured max. Default: `1` |
| `autoFixCategories` | `string[]` | no | Categories the agent may auto-fix without prompting |

#### `trigger_scan` — Trigger an immediate cluster scan

```json
{
  "type": "trigger_scan"
}
```

Triggers an immediate cluster scan. Results are pushed as `finding` and `monitor_status` events.

#### `action_response` — Respond to an autonomous action proposal

```json
{
  "type": "action_response",
  "actionId": "abc123",
  "approved": true
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | `"action_response"` | yes | |
| `actionId` | `string` | yes | ID of the proposed action |
| `approved` | `boolean` | yes | Whether the user approved the action |

#### `get_fix_history` — Request fix history

```json
{
  "type": "get_fix_history",
  "page": 1,
  "filters": {"status": "applied", "category": "crash_loop"}
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | `"get_fix_history"` | yes | |
| `page` | `integer` | no | Page number (default: `1`) |
| `filters` | `object` | no | Optional filters (`status`, `category`, `since`, `search`) |

---

## Server-to-Client Events

Events streamed from the agent to the UI over WebSocket.

### `text_delta` — Streaming text chunk

```json
{
  "type": "text_delta",
  "text": "The pods are crash-looping because"
}
```

### `thinking_delta` — Streaming thinking/reasoning chunk

```json
{
  "type": "thinking_delta",
  "thinking": "Let me check the pod logs first..."
}
```

### `tool_use` — Tool execution started

```json
{
  "type": "tool_use",
  "tool": "get_pod_logs"
}
```

### `component` — Structured UI component from tool result

```json
{
  "type": "component",
  "tool": "list_pods",
  "spec": {
    "kind": "data_table",
    "title": "Pods in production",
    "columns": [
      {"id": "name", "header": "Name"},
      {"id": "status", "header": "Status"}
    ],
    "rows": [
      {"name": "api-server-abc", "status": "Running"}
    ]
  }
}
```

See [Component Specs](#component-specs) for all `spec.kind` values.

### `confirm_request` — Request user confirmation for a dangerous action

```json
{
  "type": "confirm_request",
  "tool": "delete_resource",
  "input": {"kind": "Pod", "name": "my-pod", "namespace": "default"},
  "nonce": "abc123..."
}
```

| Field | Type | Description |
|-------|------|-------------|
| `tool` | `string` | Tool name requiring confirmation |
| `input` | `object` | Tool input parameters (shown to user) |
| `nonce` | `string` | JIT nonce for replay prevention |

### `done` — Agent turn complete

```json
{
  "type": "done",
  "full_response": "The pods are crash-looping because..."
}
```

### `error` — Error message

```json
{
  "type": "error",
  "message": "Rate limited. Max 10 messages per minute."
}
```

### `cleared` — Conversation history cleared

```json
{
  "type": "cleared"
}
```

### `/ws/monitor` Server-to-Client Events

#### `finding` — Cluster issue detected

```json
{
  "type": "finding",
  "id": "f-abc123",
  "severity": "warning",
  "category": "crash_loop",
  "resource": {"kind": "Pod", "name": "api-server-xyz", "namespace": "production"},
  "summary": "Pod crash-looping: CrashLoopBackOff (5 restarts in 10m)",
  "details": "...",
  "timestamp": 1711540800
}
```

#### `prediction` — Predicted future issue

```json
{
  "type": "prediction",
  "id": "p-abc123",
  "category": "resource_pressure",
  "resource": {"kind": "Node", "name": "worker-03"},
  "summary": "Node memory predicted to exceed 90% within 2 hours",
  "confidence": 0.87,
  "horizon": "2h",
  "timestamp": 1711540800
}
```

#### `action_report` — Result of an autonomous or approved action

```json
{
  "type": "action_report",
  "actionId": "a-abc123",
  "findingId": "f-abc123",
  "action": "restart_pod",
  "status": "applied",
  "summary": "Restarted pod api-server-xyz",
  "before": {},
  "after": {},
  "timestamp": 1711540800
}
```

#### `monitor_status` — Scan cycle status update

```json
{
  "type": "monitor_status",
  "scanning": false,
  "lastScan": 1711540800,
  "findingsCount": 3,
  "predictionsCount": 1
}
```

#### `findings_snapshot` — Active findings reconciliation

Sent after each scan cycle. Contains the IDs of all currently active findings. The UI removes any locally-held findings whose IDs are not in `activeIds`, preventing stale entries from accumulating after issues are resolved.

```json
{
  "type": "findings_snapshot",
  "activeIds": ["f-abc123", "f-def456"],
  "timestamp": 1711540800
}
```

| Field | Type | Description |
|-------|------|-------------|
| `activeIds` | `string[]` | IDs of all findings that are still active |
| `timestamp` | `number` | Unix timestamp of the snapshot |

#### `fix_history` — Response to `get_fix_history`

```json
{
  "type": "fix_history",
  "items": [],
  "total": 0,
  "page": 1,
  "pageSize": 20
}
```

---

## Component Specs

Structured UI components returned by agent tools via the `component` event. The UI renders these inline in the chat.

| `kind` | Description | Key Fields |
|--------|-------------|------------|
| `data_table` | Sortable table | `columns[]`, `rows[]` |
| `info_card_grid` | Metric cards | `cards[]{label, value, sub?}` |
| `badge_list` | Colored badges | `badges[]{text, variant}` |
| `status_list` | Health status items | `items[]{name, status, detail?}` |
| `key_value` | Key-value pairs | `pairs[]{key, value}` |
| `chart` | Time-series chart | `series[]{label, data[][], color?}` |
| `tabs` | Tabbed content | `tabs[]{label, content: ComponentSpec}` |
| `grid` | Grid layout | `columns`, `items: ComponentSpec[]` |
| `section` | Titled section | `title`, `content: ComponentSpec` |

### Badge Variants

`success` | `warning` | `error` | `info` | `default`

### Status Values

`healthy` | `warning` | `error` | `pending` | `unknown`

---

## Constraints

| Constraint | Value | Enforced By |
|------------|-------|-------------|
| Max message size | 1 MB | Agent |
| Rate limit | 10 messages/minute per connection | Agent |
| Confirmation timeout | 120 seconds | Agent |
| Context field validation | `^[a-zA-Z0-9\-._/: ]{0,253}$` | Agent |
| Reconnect attempts | 5 max, exponential backoff + jitter | UI |

---

## Version Compatibility

The UI sends a `GET /version` request before connecting. If the agent's `protocol` field doesn't match the UI's `EXPECTED_PROTOCOL`, the UI shows a warning but still connects (graceful degradation).

### Protocol Version History

| Version | Changes | UI Version | Agent Version |
|---------|---------|------------|---------------|
| `2` | `/ws/monitor` endpoint for autonomous cluster scanning, `trigger_scan` / `subscribe_monitor` / `action_response` / `get_fix_history` client messages, `finding` / `prediction` / `action_report` / `monitor_status` server events, fix history REST endpoints, predictions REST endpoint | v5.12.0+ | v1.4.0+ |
| `1` | Initial protocol: text/thinking streaming, tool use, components, confirmations | v5.0.0+ | v1.0.0+ |

### Release Compatibility Matrix

| UI Version | Agent Version | Protocol | Status |
|------------|--------------|----------|--------|
| v5.12.0 | v1.4.0 | 2 | Current |
| v5.11.0 | v1.3.0 | 1 | Compatible |
| v5.10.0 | v1.3.0 | 1 | Compatible |
| v5.8.0 | v1.2.0 | 1 | Compatible |
| v5.0.0–v5.7.0 | v1.0.0–v1.1.0 | 1 | Compatible |

> Both repos should tag releases together when protocol changes occur. Minor UI/Agent releases within the same protocol version are always compatible.
