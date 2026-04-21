# Ops Inbox — Unified SRE Worklist

**Goal:** Replace the Incidents page with a single unified inbox that combines monitor findings, proactive tasks, alerts, and assessments into one priority-ranked worklist. Merges the original "Ops Inbox" (proactive task generators) with the "Mission Board" concept (team coordination, claims, shared tasks).

**Key insight:** SREs shouldn't have to check two pages. Reactive incidents ("something broke") and proactive tasks ("something will break") belong in the same priority-sorted list. The inbox is the "start your shift here" surface.

**Architecture:** Two-phase delivery. Phase A: backend (inbox_items table, item generators, REST API, monitor integration) surfaced in the existing incidents page with badges. Phase B: full `/inbox` frontend replacing the incidents page. This validates generator output on a live cluster before building new UI.

**Tech Stack:** Python backend (FastAPI endpoints, monitor integration), React/TypeScript frontend (replaces `/incidents` route), PostgreSQL persistence, WebSocket real-time updates.

---

## 1. Data Model

### `inbox_items` table (migration 021)

```sql
CREATE TABLE IF NOT EXISTS inbox_items (
    id TEXT PRIMARY KEY,
    item_type TEXT NOT NULL,              -- finding | task | alert | assessment
    status TEXT NOT NULL DEFAULT 'new',
    title TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    severity TEXT,                         -- critical | warning | info (nullable for tasks)
    priority_score REAL NOT NULL DEFAULT 0,
    confidence REAL DEFAULT 0,
    noise_score REAL DEFAULT 0,
    namespace TEXT,
    resources JSONB DEFAULT '[]',         -- [{kind, name, namespace}]
    correlation_key TEXT,                  -- groups related items (same type only)
    claimed_by TEXT,
    claimed_at BIGINT,
    created_by TEXT NOT NULL,             -- system:monitor | system:agent | authenticated username
    due_date BIGINT,                      -- for manual tasks (nullable)
    finding_id TEXT,                       -- link to monitor finding (nullable)
    view_id TEXT,                          -- linked investigation view (nullable, created on demand)
    cluster_id TEXT,                       -- for fleet/multi-cluster support
    pinned_by JSONB DEFAULT '[]',         -- list of usernames who pinned this item
    metadata JSONB DEFAULT '{}',          -- extensible: source scanner, auto-fix info, generator name, etc.
    created_at BIGINT NOT NULL,
    updated_at BIGINT NOT NULL,
    resolved_at BIGINT,
    snoozed_until BIGINT                  -- if set and in future, item is hidden
);

CREATE INDEX IF NOT EXISTS idx_inbox_items_status ON inbox_items (status);
CREATE INDEX IF NOT EXISTS idx_inbox_items_type ON inbox_items (item_type);
CREATE INDEX IF NOT EXISTS idx_inbox_items_correlation ON inbox_items (correlation_key);
CREATE INDEX IF NOT EXISTS idx_inbox_items_cluster ON inbox_items (cluster_id);
CREATE INDEX IF NOT EXISTS idx_inbox_items_priority ON inbox_items (priority_score DESC);
```

### Correlation

Items sharing a `correlation_key` collapse into a group in the UI. Grouping is **within the same `item_type` only** — findings group with findings, never with tasks or alerts. The monitor generates correlation keys from `{category}:{resource_owner}:{namespace}` — so 12 crashlooping pods in the same deployment become one group.

### Dedup key

`item_type + correlation_key` (or `item_type + title + namespace` for items without correlation). Each scan cycle upserts — if an item with the same dedup key exists and is open, add new resources to `resources[]` and update `priority_score`. Don't create duplicates.

### Status lifecycles by type

| Type | Lifecycle | Notes |
|------|-----------|-------|
| **finding** | `new -> acknowledged -> investigating -> action_taken -> verifying -> resolved -> archived` | Rich incident stages from existing view system |
| **task** | `new -> in_progress -> resolved -> archived` | Simple for manual items |
| **alert** | `new -> acknowledged -> resolved -> archived` | Prometheus alert lifecycle |
| **assessment** | `new -> acknowledged -> escalated` | Escalated creates a new finding item |

### Priority score

Computed, not manually assigned:

```
priority_score = severity_weight * confidence * (1 - noise_score) + age_bonus + due_date_bonus
```

- `severity_weight`: critical=4, warning=2, info=1
- `age_bonus`: +0.1 per hour stale (caps at 2.0)
- `due_date_bonus`: +2.0 if due within 24h, +1.0 if due within 72h (tasks only)
- Recomputed each scan cycle

Pinned items always sort first regardless of score.

### Snooze

Items with `snoozed_until` set are excluded from query results. When `snoozed_until < NOW()`, the item flips back to its pre-snooze status (stored in `metadata.pre_snooze_status`) and reappears. Snooze options: 4h, 24h, 3 days, 1 week. The snooze endpoint saves the current status to metadata before setting `snoozed_until`.

### Cleanup

Resolved/archived items older than 30 days are pruned each scan cycle.

---

## 2. Item Generators

### How items enter the inbox

Four sources:

1. **Monitor findings** — `MonitorSession` creates inbox items during scan cycle. Dedup by correlation key.
2. **Proactive generators** — 13 generators run at end of each scan cycle, predict future issues.
3. **Agent** — creates items via `create_inbox_task` tool during investigation or when user asks.
4. **Manual** — admins create tasks via UI "New Task" button or chat ("add task: rotate TLS certs by Friday").

### 13 Proactive Generators

Each is a pure function returning `list[dict]` with inbox item fields. Registered in a `TASK_GENERATORS` list (same pattern as `SCANNER_REGISTRY`).

#### Infrastructure (7)

| Generator | Source | Urgency Calculation |
|-----------|--------|---------------------|
| `cert_expiry` | TLS secrets (type=kubernetes.io/tls) | hours until expiry |
| `trend_prediction` | 4 trend scanners (predict_linear) | predicted hours to breach |
| `degraded_operator` | ClusterOperator conditions | 0 if degraded >1h |
| `upgrade_available` | ClusterVersion.status.availableUpdates | 168h default (1 week) |
| `slo_burn` | SLO registry burn rates via Prometheus | hours until error budget exhausted |
| `capacity_projection` | metrics-server node allocatable vs requests | hours until node >90% |
| `stale_finding` | findings with no action >72h | 0 minus hours stale (negative = overdue) |

#### Security (3)

| Generator | Source | Urgency |
|-----------|--------|---------|
| `privileged_workloads` | Pods with privileged SCC or runAsRoot | 24h |
| `rbac_drift` | ClusterRoleBindings with cluster-admin not in last audit | 12h |
| `network_policy_gaps` | Namespaces with no NetworkPolicy | 48h |

#### Networking (2)

| Generator | Source | Urgency |
|-----------|--------|---------|
| `route_cert_expiry` | Route TLS certs (separate from service certs) | hours until expiry |
| `service_endpoint_gaps` | Services with 0 ready endpoints | 1h |

#### Production Readiness (1)

| Generator | Source | Urgency |
|-----------|--------|---------|
| `readiness_regressions` | Readiness gate API — workloads that newly failed a gate after a redeploy | 24h |

Generator output maps to inbox items as: `item_type='assessment'`, `severity` from urgency threshold, `metadata.generator` stores the generator name, `metadata.urgency_hours` stores the computed urgency.

### Scan integration

Generators run at the end of each scan cycle in `MonitorSession._run_scan_locked()`:

1. Call each generator, collect all items
2. Compute dedup key per item
3. Upsert into `inbox_items`:
   - New key -> INSERT with `status='new'`
   - Existing key with `new|acknowledged` -> UPDATE `priority_score`, `resources`
   - Existing key with `snoozed` -> skip (respect snooze)
4. For generator-created items in DB not generated this cycle and status `new|acknowledged`:
   - Set `status='resolved'`, `resolved_at=NOW()` (condition cleared)
5. Prune resolved items older than 30 days

### Monitor finding integration

When `MonitorSession` emits a finding:
1. Check if an inbox item exists with matching `finding_id`
2. If not, create one: `item_type='finding'`, map severity/confidence/noise_score from the finding
3. If yes, update `priority_score` and `resources`
4. When finding resolves (self-heal or auto-fix), transition inbox item to `resolved`

When auto-fix runs:
1. Linked inbox item transitions to `verifying`
2. If verification passes (5 clean scan cycles) -> `resolved`
3. If verification fails -> back to `investigating`

---

## 3. REST API

New endpoints in `api/inbox.py`:

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/inbox` | List items. Query: `type`, `status`, `namespace`, `claimed_by`, `severity`, `group_by`, `pinned`. Sorted by pinned first, then `priority_score DESC` |
| `GET` | `/inbox/:id` | Single item with linked view + pending approval details |
| `GET` | `/inbox/stats` | Counts by status, type, severity for badge/header |
| `POST` | `/inbox` | Create manual task (title, summary, due_date, namespace) |
| `PATCH` | `/inbox/:id` | Update status |
| `POST` | `/inbox/:id/claim` | Claim item. Auto-transitions `new -> in_progress` (task) or `new -> investigating` (finding) |
| `DELETE` | `/inbox/:id/claim` | Unclaim item |
| `POST` | `/inbox/:id/acknowledge` | Transition to acknowledged |
| `POST` | `/inbox/:id/snooze` | Snooze. Body: `{hours: 4|24|72|168}` |
| `POST` | `/inbox/:id/dismiss` | Dismiss permanently. Requires ConfirmDialog for critical severity |
| `POST` | `/inbox/:id/investigate` | Creates linked view, opens investigation |
| `POST` | `/inbox/:id/resolve` | Transition to resolved |
| `POST` | `/inbox/:id/pin` | Toggle pin for authenticated user |

All endpoints use authenticated session user for `created_by`, `claimed_by`, `acked_by` fields — not impersonation flags.

### Response format

`GET /inbox`:
```json
{
  "items": [...],
  "groups": [
    {
      "correlation_key": "crashloop:payment-api:production",
      "items": [...],
      "count": 12,
      "top_severity": "critical"
    }
  ],
  "stats": {"new": 3, "acknowledged": 2, "investigating": 1, "in_progress": 5},
  "total": 11
}
```

The backend separates correlated and uncorrelated items. Items with a `correlation_key` that matches 2+ items appear in `groups[]`. Items with no correlation key or unique correlation keys appear in `items[]`. The frontend renders `InboxGroup` for grouped items, `InboxItem` for ungrouped. Both arrays are sorted by `priority_score DESC` (pinned first).

---

## 4. WebSocket Integration

New event types on existing monitor WS channel:

| Event | Payload | When |
|-------|---------|------|
| `inbox_item_created` | `{id, item_type, title, severity, priority_score}` | New item from generator/monitor/agent |
| `inbox_item_updated` | `{id, status, claimed_by, priority_score}` | Status change, claim, priority recalc |
| `inbox_item_claimed` | `{id, claimed_by, claimed_at}` | Someone claims an item |
| `inbox_item_resolved` | `{id, resolved_at}` | Item resolved (auto or manual) |

### Toast notifications

Critical-severity `inbox_item_created` events trigger a toast notification on all connected clients regardless of current page. Toast includes item title + "View in Inbox" link. Non-critical items update the badge count silently.

---

## 5. Agent Tool

New `create_inbox_task` tool in `sre_agent/inbox.py`:

```python
@beta_tool
def create_inbox_task(
    title: str,
    detail: str = "",
    urgency: str = "this_week",
    namespace: str = "",
    resource_name: str = "",
    resource_kind: str = "",
):
    """Add a task to the ops inbox.

    Use when the user asks to track, remind, or follow up on something.
    Examples: "remind me to rotate certs", "add task: review HPA config",
    "track the CoreDNS upgrade".

    Args:
        title: Short description
        detail: Actionable guidance on what to do
        urgency: today (8h), this_week (168h), this_month (720h)
        namespace: Optional K8s namespace
        resource_name: Optional resource name
        resource_kind: Optional resource kind
    """
```

Creates an inbox item with `item_type='task'`, `created_by='system:agent'` or username, `metadata.urgency_hours` from urgency mapping.

---

## 6. Frontend

### Phase A: Badge integration (existing Incidents page)

Before building the full inbox page, surface generator output in the existing UI:
- Add "Proactive" badge filter to the Active tab on the Incidents page
- Assessment-type inbox items appear as cards with an "Upcoming" indicator
- Validates generator output is useful on a live cluster before committing to UI

### Phase B: Full Inbox page

#### Route and navigation

- New route: `/inbox` replaces `/incidents`
- Nav item: "Inbox" with badge count of `new` items (replaces "Incidents")
- Old `/incidents` URL redirects to `/inbox`

#### Page structure

```
InboxPage.tsx
|-- InboxHeader.tsx
|   |-- Badge count (open items)
|   |-- Quick presets: "Active Incidents" | "Needs Approval" | "My Items" | "Unclaimed"
|   |-- "New Task" button
|   |-- Scanner controls popover (moved from incidents page header)
|
|-- Two top-level tabs: "Inbox" | "Activity"
|
|-- Inbox tab (default)
|   |-- InboxFilterBar.tsx
|   |   |-- Type filter (Finding | Task | Alert | Assessment)
|   |   |-- Status filter (type-aware, shows valid statuses for selected type)
|   |   |-- Namespace filter
|   |   |-- Severity filter
|   |   |-- Group by toggle (None | Namespace | Category | Assignee)
|   |
|   |-- InboxList.tsx
|   |   |-- InboxGroup.tsx (collapsible, when grouped)
|   |   |   |-- Group header: title, count, top severity
|   |   |   +-- InboxItem.tsx (repeated)
|   |   +-- InboxItem.tsx (flat when ungrouped)
|   |
|   +-- InboxItem.tsx
|       |-- Severity indicator (left color bar)
|       |-- Title + namespace tag
|       |-- InvestigationPhases badge (findings only, reused)
|       |-- Approval indicator (orange dot when pending actions)
|       |-- Claimed-by username label
|       |-- Age label (reuse existing formatRelativeTime)
|       |-- Pin button
|       +-- Quick actions: Acknowledge, Claim, Snooze, Dismiss
|
|-- Activity tab
|   +-- Existing ActivityTab (moved as-is: by-date/by-resource views,
|       investigations, postmortems, agent learning, time range + category filters)
|
|-- [Item click] -> detail drawer (right side, state lifted to page level)
|   |-- Finding -> IncidentLifecycleDrawer (7 stages, existing)
|   |-- Task -> TaskDetailDrawer (description, due date, action buttons)
|   +-- Alert -> AlertDetailDrawer (alert detail + silence management)
|
+-- NewTaskDialog.tsx (modal)
    |-- Title (required)
    |-- Description (optional textarea)
    |-- Due date (optional date picker)
    +-- Namespace picker (optional, existing namespace select component)
```

#### Filter preset behavior

Selecting a preset **replaces all active filters** (not additive). Manually changing any filter clears the active preset indicator. Presets:

| Preset | Filters applied |
|--------|----------------|
| Active Incidents | type=finding, status=investigating/action_taken/verifying |
| Needs Approval | metadata.has_pending_approval=true |
| My Items | claimed_by=current_user |
| Unclaimed | claimed_by=null, status!=resolved/archived |

#### State management

New `useInboxStore.ts` (Zustand):
- `items[]`, `groups[]`, `stats{}`
- `filters{}`, `activePreset`, `groupBy`
- `selectedItemId` (drives detail drawer)
- WebSocket subscription for real-time updates
- Replaces incident-related stores

#### Keyboard shortcuts

Same as current incidents page — carried over:
- `j/k` — navigate items
- `a` — acknowledge
- `d` — dismiss (triggers ConfirmDialog for critical severity)
- `i` — investigate (opens/creates linked view)
- `c` — claim/unclaim toggle
- `s` — snooze (opens snooze dropdown)
- `p` — pin/unpin

Conflicts with existing global shortcuts must be checked at implementation time.

#### Loading, error, and empty states

- **Loading:** Skeleton cards (same pattern as existing incident cards)
- **Error:** Error banner with retry button, existing error boundary pattern
- **Empty (no items):** "All clear" message with prompt pills: "Scan for security gaps", "Check capacity projections", "Review cert expiry"
- **Empty (filtered):** "No items match your filters" with "Clear filters" button

#### Virtual scrolling

Use virtual scrolling (react-window or similar) for the inbox list. Under normal conditions the list is small (<100 items), but during incidents correlated groups could expand to hundreds of resources.

---

## 7. Assessment Escalation UI

When an assessment's predicted condition materializes:
1. Backend calls `escalate_assessment_to_incident()` (existing)
2. Assessment inbox item transitions to `escalated`
3. New finding inbox item is created with `metadata.escalated_from` pointing to the assessment ID
4. Frontend shows a brief toast: "Assessment escalated: {title} is now an active finding"
5. The new finding item appears in the inbox with its own lifecycle

The escalated assessment remains visible (dimmed, status=escalated) until the next scan cycle archives it.

---

## 8. Phased Delivery

### Phase A: Backend + existing UI integration
1. Migration 021 (inbox_items table)
2. Item generators (13 proactive + monitor finding bridge)
3. REST API endpoints
4. WebSocket events
5. Agent tool (create_inbox_task)
6. Badge on existing incidents page Active tab ("Proactive" filter)
7. Validate on live cluster

### Phase B: Full Inbox frontend
1. InboxPage + InboxList + InboxItem components
2. InboxFilterBar with presets
3. InboxGroup for correlated items
4. Detail drawer routing (finding/task/alert)
5. NewTaskDialog
6. Activity tab migration
7. useInboxStore (Zustand)
8. Nav change: Incidents -> Inbox with redirect
9. Keyboard shortcuts
10. Toast notifications for critical items

### Phase C: Cleanup
1. Remove old incidents page components (after redirect period)
2. Remove old incident-related Zustand stores
3. Update all docs (README, CLAUDE.md, API_CONTRACT, SECURITY)

---

## 9. Acceptance Criteria

- [ ] 13 proactive generators run each scan cycle and populate inbox_items table
- [ ] Monitor findings create/update inbox items with dedup
- [ ] Items auto-resolve when conditions clear
- [ ] Snooze respects duration and re-surfaces items
- [ ] Correlation groups collapse related same-type items
- [ ] Priority score computed and items sorted correctly
- [ ] Claims work with real usernames, not impersonation flags
- [ ] Dismiss uses ConfirmDialog for critical severity items
- [ ] Filter presets replace all filters (not additive)
- [ ] Badge on nav shows new item count
- [ ] Agent can create tasks via create_inbox_task tool
- [ ] Users can create tasks via "New Task" button and chat
- [ ] WebSocket broadcasts for item creation, update, claim, resolve
- [ ] Toast notifications for critical items on any page
- [ ] Keyboard shortcuts work without conflicts
- [ ] Loading, error, and empty states all render correctly
- [ ] Assessment escalation creates finding item with link back
- [ ] Virtual scrolling handles large lists
- [ ] cluster_id present for fleet support
- [ ] Old /incidents URL redirects to /inbox
- [ ] Manual browser verification of full page
