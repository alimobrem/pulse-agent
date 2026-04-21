# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Pulse Agent — AI-powered OpenShift/Kubernetes SRE and Security agent built on Claude. Connects to live clusters via the K8s API and uses Claude Opus for diagnostics, incident triage, and automated remediation. v2.5.0, Protocol v2, 135 tools (99 native + 36 MCP), 7 skills (built-in: sre, security, view_designer, capacity_planner, plan-builder, postmortem, slo-management), 22 scanners (18 reactive + 4 predictive trend scanners), tests, 73 PromQL recipes, 15 eval suites, 170 scenarios, 116 eval prompts. 40 modules (k8s_tools/12, monitor/11, api/18, plus decorators.py, tool_predictor.py) — no file over 910 lines. Python 3.11+, Mypy clean (0 errors), ruff clean. Migration version 017 (slo_definitions). Auto-routing orchestrator with typo auto-correction (~130 K8s misspellings), hard pre-route regex rules, and pre-route handoff in skill classifier. Centralized Pydantic config (no raw os.environ). Generative views: tools return 23 component specs (including action_button, confidence_badge, resolution_tracker, blast_radius) for rich UI rendering, user-scoped custom dashboards with share/clone, action execution endpoint. Multi-datasource live tables with K8s watches + PromQL/log enrichment + sparkline charts. Tool usage tracking: full audit log with chain intelligence. Adaptive tool selection: TF-IDF + LLM fallback + chain expansion. ORCA multi-signal skill selector (6-channel fusion, 5 active by default, parallel multi-skill execution max 2 with Sonnet synthesis), phased plan execution, dependency graph (17 resource types, 10 relationships, 5 topology perspectives with metrics enrichment), auto-postmortems, SLO registry. ALWAYS_INCLUDE trimmed from 12 to 5. Release gate: 99.6% (release suite avg).

**UI Repository:** `/Users/amobrem/ali/OpenshiftPulse` — React/TypeScript frontend (Zustand stores, incident views, admin dashboard).

**IMPORTANT:** Always run `python3 -m pytest tests/ -v` before committing. CI runs on every push — check with `gh run list --limit 1`.

## Design Principles (see [`DESIGN_PRINCIPLES.md`](DESIGN_PRINCIPLES.md))

All features and UI decisions must follow these principles:
1. Conversational-first, visual-second, code-third
2. Intent -> Visibility -> Trust -> Action
3. Zero training curve; interface teaches itself
4. Delight: proactive, plain-English, confidence scores everywhere
5. Human-in-the-loop by default for anything that matters
6. Radical transparency & explainability
7. Proactive intelligence without alert fatigue
8. Minimal cognitive load & single pane of glass
9. Forgiving & resilient by design
10. Personalized & adaptive over time

## Commands

```bash
# Install
pip install -e .

# Run CLI
python -m sre_agent.main              # SRE agent
python -m sre_agent.main security     # Security scanner

# Run API server
pulse-agent-api                       # FastAPI on port 8080

# Tests
python3 -m pytest tests/ -v           # all tests (~tests)
python3 -m pytest tests/test_k8s_tools.py -v  # single file
make verify                                    # lint + type-check + test\nmake test-everything                           # verify + ALL eval suites (deterministic + LLM-judged)\nmake chaos-test                                # chaos engineering (5 scenarios, needs cluster)

# Eval commands
python -m sre_agent.evals.cli --suite release --fail-on-gate   # run release eval gate
python -m sre_agent.evals.cli --suite core --save-baseline     # save eval baseline
python -m sre_agent.evals.cli --suite core --compare-baseline  # compare vs saved baseline
python -m sre_agent.evals.cli --audit-prompt --mode sre        # prompt token cost breakdown
python -m sre_agent.evals.ablation --suite release --mode sre  # (future) ablation test

# Release
make release VERSION=1.6.0            # bump version everywhere, commit, tag
# then: git push && git push --tags   # triggers build-push.yml

# Deploy (OpenShift) — uses umbrella script in UI repo
cd /Users/amobrem/ali/OpenshiftPulse && ./deploy/deploy.sh   # builds UI + Agent, pushes to Quay, Helm upgrade
cd /Users/amobrem/ali/OpenshiftPulse && ./deploy/deploy.sh --dry-run  # preview without applying
cd /Users/amobrem/ali/OpenshiftPulse && ./deploy/deploy.sh --set agent.mcp.enabled=true  # deploy with MCP enabled
cd /Users/amobrem/ali/OpenshiftPulse && ./deploy/deploy.sh --set agent.mcp.enabled=true  # deploy with MCP enabled
```

## Architecture

### Entry Points
- `sre_agent/main.py` — Interactive CLI with Rich UI
- `sre_agent/serve.py` → `sre_agent/api/` — FastAPI WebSocket server

### Agent Loop
- `agent.py` — shared `run_agent_streaming()` loop used by both SRE and Security agents
- Circuit breaker: `CircuitBreaker` class with CLOSED→OPEN→HALF_OPEN states
- Tool execution: parallel for reads, sequential with confirmation gate for writes
- Confirmation: `confirm_request` → `confirm_response` with JIT nonce for replay prevention

### WebSocket API (Protocol v2)
- `/ws/agent` — Auto-routing orchestrated agent (ORCA classifies intent per message, routes to appropriate skill)
- `/ws/monitor` — Autonomous cluster monitoring (push-based findings, investigations, actions)
- Auth: `PULSE_AGENT_WS_TOKEN` via query param, constant-time comparison

### Monitor System (`monitor/` package — 11 modules)
- `MonitorSession` (session.py) — periodic cluster scanning (default 60s interval)
- 22 scanners: 18 reactive scanners (crashlooping pods, pending pods, failed deployments, node pressure, expiring certs, firing alerts, OOM-killed pods, image pull errors, degraded operators, DaemonSet gaps, HPA saturation, security posture + 5 audit scanners: config changes, RBAC, deployments, warning events, auth) + 4 predictive trend scanners (memory pressure forecast, disk pressure forecast, HPA exhaustion trend, error rate acceleration) using Prometheus `predict_linear()`
- Auto-fix at trust level 3+: deletes crashlooping pods, restarts failed deployments
- Confidence scores on all findings, investigations, and action proposals
- `resolution` events emitted when findings resolve (auto-fix or self-healed)
- Reasoning chains: investigation prompt requests evidence + alternatives_considered
- Noise learning: tracks transient findings, assigns `noiseScore` to suppress flaky alerts
- `findings_snapshot` event for stale finding cleanup
- Morning briefing: `GET /briefing` endpoint aggregates recent activity with time-aware greeting, live scanner data, and trend findings with priority items
- Simulation preview: `POST /simulate` predicts impact, risk, duration, reversibility
- WebSocket `feedback` message type for UI-driven memory learning (thumbs up/down)
- Approved confirmations recorded as implicit positive feedback for memory
- Fix history persisted to the database (`PULSE_AGENT_DATABASE_URL`)
- `_sanitize_for_prompt()` on all cluster data in investigation prompts with `--- BEGIN/END CLUSTER DATA ---` delimiters

### Orchestrator (`orchestrator.py`)
- `classify_intent()` — keyword-based SRE/Security/Both classification
- `fix_typos()` — corrects ~130 common K8s/SRE misspellings before classification
- `build_orchestrated_config()` — returns system_prompt, tool_defs, tool_map, write_tools for the classified mode
- Used by `/ws/agent` endpoint for auto-routing

### Tools
- `k8s_tools/` — 12-module package with 42 K8s tools (`@beta_tool` decorated). Write tools in `WRITE_TOOLS` set require confirmation. Submodules: validators, pods, nodes, deployments, workloads, monitoring, diagnostics, generic, advanced, audit, live_table.
- `security_tools.py` — 9 security scanning tools (read-only)
- `fleet_tools.py` — 5 multi-cluster tools
- `gitops_tools.py` — 6 ArgoCD tools
- `predict_tools.py` — 3 predictive analytics tools
- `timeline_tools.py` — 1 incident correlation tool
- `git_tools.py` — 1 Git PR proposal tool
- `handoff_tools.py` — 2 agent-to-agent handoff tools (`request_security_scan`, `request_sre_investigation`)
- `tool_registry.py` — central registry; all tool modules call `register_tool()` at import time

### Tool Pattern
```python
@beta_tool
def tool_name(param: str, namespace: str = "") -> str:
    """One-line description used by Claude to decide when to call it."""
    err = _validate_k8s_namespace(namespace)
    if err:
        return err
    result = safe(lambda: get_core_client().list_namespaced_pod(namespace))
    if isinstance(result, str):
        return result  # Error from safe()
    # Format and return
```

Rules: validate inputs with `_validate_k8s_name()`/`_validate_k8s_namespace()`, wrap K8s calls in `safe()`, write tools must be in `WRITE_TOOLS` set, never return secret values.

### Configuration (`config.py`)
- `PulseAgentSettings(BaseSettings)` — Pydantic v2 Settings with `PULSE_AGENT_` env prefix
- `.env` file support, type validation at startup
- All config accessed via settings instance, not raw `os.environ`

### Harness (`harness.py`)
- Prompt caching: `cache_control: ephemeral` on system prompt
- Cluster context injection: pre-fetches node count, namespaces, OCP version
- Component hints for selected tools (tool selection moved to skill_loader)

### Security
- Non-root container (UID 1001) on UBI9
- RBAC: read-only by default, write ops opt-in via `rbac.allowWriteOperations`
- Confirmation gate enforced in code (not just prompt)
- Prompt injection defense in system prompt
- Input validation: replicas 0-100, log lines 1-1000, grace period 1-300s

### MCP Server (`chart/templates/mcp-server.yaml`)
- OpenShift MCP server (github.com/openshift/openshift-mcp-server) deployed as sidecar pod
- Image: `quay.io/amobrem/pulse-agent:mcp-server` (built from openshift fork)
- SSE transport, auto-discovery, 3-tier rendering
- 11 toolsets: core, config, helm, observability, openshift, ossm, netedge, tekton, kiali, kubevirt, kcp
- 36 MCP tools registered alongside native tools
- Health probes (readiness + liveness on `/healthz`)
- Toggle toolsets from the Toolbox UI
- CI (`build-push.yml`) builds MCP image on release tags

### Helm Chart (`chart/`)
- `values.yaml` — requires `vertexAI.projectId` or `anthropicApiKey.existingSecret`
- WS token and PG password auto-generated with `lookup()` to preserve existing values on upgrade
- RollingUpdate strategy with maxUnavailable=1/maxSurge=0 (old pod dies first to free RWO PVC)
- `chart/templates/deployment.yaml` — validates credentials at install time via `_helpers.tpl`
- `chart/templates/postgresql.yaml` — PostgreSQL **StatefulSet** (RHEL 9, runAsNonRoot, NetworkPolicy, headless Service)

### Frontend CSS Gotchas
- **Scrollbar styling**: Uses ONLY `::-webkit-scrollbar` pseudo-elements (in `index.css`). Do NOT add `scrollbar-color` or `scrollbar-width` — Chrome 121+ ignores `::-webkit-scrollbar` when standard scrollbar properties are set (even via inheritance).
- **`.openshiftpulse` class**: Must be on the Shell root div (`Shell.tsx`). All global CSS rules are scoped to this class.

### Key Files
- `config.py` — Pydantic v2 Settings (`PulseAgentSettings` with `PULSE_AGENT_` prefix)
- `errors.py` — `ToolError` classification (7 categories + suggestions)
- `error_tracker.py` — thread-safe ring buffer for error aggregation
- `runbooks.py` — 10 built-in SRE runbooks injected into system prompt
- `memory/` — self-improving agent (PostgreSQL, pattern detection, learned runbooks)
- `view_tools.py` — `namespace_summary` + `create_dashboard` + `get_topology_graph` tools for generative views. Topology supports 5 perspectives (Physical, Logical, Network, Multi-Tenant, Helm) via `kinds`, `relationships`, `layout_hint`, `include_metrics`, `group_by` params
- `view_mutations.py` — view mutation tools extracted from view_tools.py (`update_dashboard`, `delete_dashboard`, `clone_view`, `share_view`)
- `dependency_graph.py` — live K8s resource dependency graph (17 types, 10 relationships), `_fetch_metrics()` with 30s TTL cache for metrics-server enrichment
- `quality_engine.py` — unified dashboard validation + quality scoring (includes `critique_view` moved from view_critic.py)
- `db.py` — Database abstraction (PostgreSQL production, SQLite tests) + view CRUD functions
- `k8s_client.py` — lazy-initialized K8s client with `safe()` wrapper
- `context_bus.py` — shared context bus for cross-agent communication
- `orchestrator.py` — intent classification + typo correction + agent routing for `/ws/agent`
- `tool_usage.py` — tool invocation audit log (PostgreSQL, fire-and-forget recording, query/stats)
- `tool_predictor.py` — adaptive tool selection engine (TF-IDF prediction, LLM fallback, co-occurrence expansion, real-time learning)
- `decorators.py` — typed `beta_tool` wrapper (centralizes SDK type mismatch for tools returning `tuple[str, dict]`)
- `tool_chains.py` — tool chain discovery and next-tool hints (bigram analysis, system prompt injection)
- `promql_recipes.py` — 73 production-tested PromQL recipes + learned queries DB (sources: OpenShift console, cluster-monitoring-operator, kube-state-metrics, node_exporter, ACM)
- `layout_engine.py` — semantic auto-layout engine (role-based row packing, replaces fixed templates)
- `intelligence.py` — analytics feedback loop (query reliability, dashboard patterns, error hotspots → system prompt); supports `PULSE_PROMPT_EXCLUDE_SECTIONS` env var for ablation testing
- `evals/compare.py` — A/B comparison of eval suite results (baseline vs current, regression detection)
- `evals/ablation.py` — prompt section ablation framework (tests impact of removing prompt sections on scores)
- `evals/history.py` — eval history DB (eval_runs table, trend queries, migration 006)
- `skill_loader.py` — skill package loader, tool selection, MCP inclusion (consolidates harness tool selection); ALWAYS_INCLUDE trimmed to 5 (adaptive), self-describe tools conditional
- `skill_router.py` — query routing and pre-route handoff logic extracted from skill_loader.py
- `tool_categories.py` — tool category definitions extracted from skill_loader.py
- `mcp_client.py` — MCP server connections (SSE transport), tool/prompt discovery, registration
- `self_tools.py` — 12 self-description + 4 skill management + 3 K8s API introspection tools
- `prompt_log.py` — prompt logging (hash, sections, tokens, version tracking) for observability and debugging
- `component_registry.py` — 23 component kinds registered (metrics, data, visualization, status, detail, layout, action); data-driven prompt hints
- `slo_registry.py` — SLO definition CRUD, live Prometheus burn-rate queries, persistence to `slo_definitions` table
- `change_risk.py` — deploy risk scoring for findings (correlates recent changes with incidents)
- `plan_runtime.py` — phased investigation plan execution engine (plan templates, phase lifecycle, progress events)
- `skill_scaffolder.py` — AI-generated skill packages from conversation patterns and usage data
- `eval_scaffolder.py` — auto-generates eval scenarios when skills are scaffolded (`scaffold_eval_from_plan()` for full scenario + replay fixture, `scaffold_eval_from_investigation()` for scenario only); writes to non-gating `scaffolded` eval suite
- `selector_learning.py` — ORCA selector weight learning from feedback signals (routing decisions, overrides, outcomes)
- `synthesis.py` — parallel skill output merging with Sonnet-powered conflict detection and fallback concatenation
- `trend_scanners.py` — 4 predictive scanners (memory pressure, disk pressure, HPA exhaustion, error rate acceleration) using Prometheus predict_linear()
- `api/views.py` — view CRUD, sharing, version history, `POST /views/{view_id}/actions` for action_button tool execution
- `api/scanner_rest.py` — scanner REST endpoints extracted from monitor_rest.py
- `api/fix_rest.py` — fix history REST endpoints extracted from monitor_rest.py
- `api/topology_rest.py` — topology REST endpoints extracted from monitor_rest.py

**Frontend:** `/toolbox` consolidates tools, skills, MCP, components, usage, analytics into single page.

**Testing:** See [`TESTING.md`](TESTING.md) for full testing strategy, eval prompts, CI pipeline, and release process.

### Claude Code Agents (`.claude/agents/`)
8 specialized agents with hooks in `.claude/settings.json`:
- `tool-writer` — writes new `@beta_tool` functions
- `runbook-writer` — writes diagnostic runbooks
- `protocol-checker` — validates WebSocket protocol vs API_CONTRACT.md
- `tool-auditor` — audits tools for input validation, security
- `memory-auditor` — audits memory system integrity
- `security-hardener` — reviews security across code, containers, Helm
- `test-writer` — writes pytest tests following conftest patterns
- `deploy-validator` — validates deploy config before rollout

### Environment Variables
| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_VERTEX_PROJECT_ID` | GCP project for Vertex AI | required* |
| `CLOUD_ML_REGION` | GCP region | required* |
| `ANTHROPIC_API_KEY` | Direct Anthropic API key | required* |
| `PULSE_AGENT_MODEL` | Claude model | `claude-opus-4-6` |
| `PULSE_AGENT_WS_TOKEN` | WebSocket auth token | auto-generated |
| `PULSE_AGENT_SCAN_INTERVAL` | Monitor scan interval (seconds) | `60` |
| `PULSE_AGENT_HARNESS` | Enable harness optimizations | `1` |
| `PULSE_AGENT_MEMORY` | Enable self-improving memory | `1` (enabled) |
| `PULSE_AGENT_DATABASE_URL` | Database URL (PostgreSQL) | required |
| `PULSE_AGENT_AUTOFIX_ENABLED` | Enable monitor auto-fix | `true` |
| `PULSE_AGENT_MAX_TRUST_LEVEL` | Server-side max trust level (0-4) | `3` |
| `PULSE_AGENT_CB_THRESHOLD` | Circuit breaker failure threshold | `3` |
| `PULSE_AGENT_CB_TIMEOUT` | Circuit breaker recovery (seconds) | `60` |
| `PULSE_AGENT_NOISE_THRESHOLD` | Noise score threshold for suppressing findings | `0.7` |
| `PULSE_AGENT_MULTI_SKILL` | Enable parallel multi-skill routing | `true` |
| `PULSE_AGENT_MULTI_SKILL_THRESHOLD` | ORCA score gap for multi-skill activation | `0.15` |
| `PULSE_AGENT_MULTI_SKILL_MAX` | Max concurrent skills | `2` |
| `PULSE_AGENT_TEMPORAL_CACHE_TTL` | Temporal signal cache TTL (seconds) | `60` |

*One of Vertex AI or Anthropic API key is required.
