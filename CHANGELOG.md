# Changelog

All notable changes to Pulse Agent are documented in this file.

## v1.14.0 (2026-04-03)

### Added
- **Tool eval prompts** -- 84 real-world user queries mapped to expected tool calls, covering all 82 registered tools. CI enforces eval prompt coverage for new tools.
- **`delete_dashboard` and `clone_dashboard` tools** -- manage saved views from the agent conversation.
- **Token usage tracking** -- records input/output/cache tokens per turn from the Claude API for cost visibility.
- **Semantic layout engine** -- role-based auto-layout replaces 5 fixed dashboard templates. Widgets arranged by role (KPI, chart, table, status) and content relationships.
- **Intelligence loop** -- `intelligence.py` feeds tool analytics (query reliability, dashboard patterns, error hotspots) back into the system prompt.
- **Plan validation** -- `plan_dashboard` now validates plans before execution, catching missing components early.
- **Tool analytics** -- full audit log with chain intelligence (bigram discovery, next-tool hints), usage stats API, chains endpoint.
- **View versioning** -- version history with undo support for saved views.

### Changed
- **Prompt optimization** -- SRE system prompt reduced from 28KB to 8KB (71% reduction) via selective component schema and runbook injection.
- **View designer prompt** rewritten -- 50% smaller, workflow-first approach.
- `verify_query` made optional for recipe-based PromQL queries to reduce Prometheus round-trips.
- `time_range` defaults to 1h for chart components.

### Fixed
- NaN values in chart data causing JSON parse failures and 500 errors on view endpoints.
- Connection leak, context validation, and ApiClient reuse issues.
- View designer bugs: generic `cluster_metrics` forced on every dashboard, missing title exemptions for grid/tabs/section.
- SQL interval syntax, category tracking, and Prometheus client issues.
- Invalid PromQL, dead code, session leak, and KPI sizing issues from code review.

### Docs
- Updated tool count from 105 to 82 across all documentation.
- Updated test count to 1078.
- Added EVAL_PROMPTS.md, DESIGN_PRINCIPLES.md, and CHANGELOG.md.
- Added Tool Analytics section to README.
- Updated API_CONTRACT.md with view REST endpoints and tool chain endpoint.

## v1.13.1 (2026-03-28)

### Added
- 88 unit tests for all 11 monitor scanner functions.
- Startup probes for agent (60s) and PostgreSQL (30s).
- PodDisruptionBudget for zero-downtime rollouts.

### Changed
- Deployment strategy changed to RollingUpdate with maxUnavailable=1/maxSurge=0.
- Removed standalone WS token generator; umbrella chart owns the token.

### Fixed
- Share endpoint JSONResponse bug.
- Memory timing bug, async pattern detection, version history diffs.

## v1.13.0 (2026-03-25)

### Added
- Generic `list_resources` and `describe_resource` tools for any K8s resource type via the Table API.
- 14 smart column renderers for resource tables.
- Resource relationship tracer (`get_resource_relationships`).
- View auto-save: `create_dashboard` saves directly to PostgreSQL.
- View versioning with undo and share/clone support.
- Structured JSON logging.
- Connection pooling with `ThreadedConnectionPool`.
- Schema migration system (`db_migrations.py`).
- Warning-severity investigation in monitor (not just critical).
- Default namespace scanning (removed from skip list).
- Showcase eval scenarios for all 10 component types.

### Changed
- PostgreSQL-only database layer (SQLite removed for production).
- Removed 9 redundant tools, consolidated into generic resource tools.
- Context helper extraction, tool parallelization.

### Fixed
- 401 on views API.
- Prometheus table labels.
- NaN in chart data causing JSON parse failures.

## v1.12.0 (2026-03-18)

### Added
- Auto-routing orchestrator (`/ws/agent` endpoint).
- Agent-to-agent handoff tools (`request_security_scan`, `request_sre_investigation`).
- Shared context bus for cross-agent communication.
- Noise learning for monitor findings.
- Morning briefing endpoint (`GET /briefing`).
- Simulation preview endpoint (`POST /simulate`).

## v1.9.0 (2026-03-01)

### Added
- Self-improving agent with incident memory, learned runbooks, and pattern detection.
- 73 production-tested PromQL recipes across 16 categories.
- `discover_metrics` and `verify_query` tools.
- Pydantic v2 configuration (`PulseAgentSettings`).

## v1.4.0 (2026-02-01)

### Added
- Protocol v2: `/ws/monitor` for autonomous scanning.
- 16 scanners (11 cluster + 5 audit).
- Auto-fix at trust levels 3 and 4.
- Fix history with rollback support.
- Confidence scores on all findings.

## v1.0.0 (2026-01-15)

- Initial release: SRE agent, security scanner, 9 security tools, CLI and WebSocket API.
