# Changelog

All notable changes to Pulse Agent are documented in this file.

## v2.0.0 (2026-04-12)

### Extensible Skill System
- Skill packages: drop-in .md files with routing, tools, evals, hot reload
- 6 skills: SRE, Security, View Designer, Capacity Planner + user-created
- Create/edit/delete/clone skills through chat or Toolbox UI
- Skill name routing (2x weight), keyword scoring, LLM fallback (haiku)
- User-created skills persist on PVC across restarts

### MCP Integration
- OpenShift MCP server (11 toolsets, 36 tools)
- SSE transport, prompt discovery, 3-tier rendering
- Toolset toggle from UI with crashloop detection
- Table parser for kubectl-style output

### Agent Intelligence
- Intent analysis prefix (think-before-acting)
- Dynamic prompt builder (centralized assembly)
- Skill-aware component hints (data-driven from registry)
- Edit-distance typo correction (catches novel misspellings)
- Synonym-based eval scoring
- Lazy skill validation (no false degradation at startup)
- ALWAYS_INCLUDE trimmed 23→12 (self-describe tools conditional)
- Runbook injection capped at 2000 chars

### Transparency & Observability
- Skill attribution footer on every chat response (skill, tools, duration, tokens)
- Prompt logging (hash, sections, tokens, version tracking)
- Hallucination detection (unknown tools, empty results)
- Confidence scoring in routing decisions
- Capability change toast notifications
- Welcome message with dynamic tool/skill counts

### Toolbox UI (/toolbox)
- Consolidated /tools + /extensions into 6-tab page
- Source badges (native/mcp) throughout
- Follow-up suggestion pills (context-aware)
- Prompt Audit section in Analytics
- Skill detail drawer with editor, versions, diff viewer
- MCP toolset toggles with checkboxes
- Clone + Delete buttons for skills
- Arrow key tab navigation, proper ARIA

### Self-Description Tools (12)
- list_my_skills, list_my_tools, list_ui_components
- list_promql_recipes, list_runbooks
- explain_resource, list_api_resources, list_deprecated_apis
- create_skill, edit_skill, delete_skill, create_skill_from_template

### Testing
- 1454 backend tests, 1934 frontend tests
- 9 multi-turn replay fixtures
- 15 security eval scenarios (3x increase)
- Prompt quality test suite
- 0.981 deterministic eval score, 19/21 judge pass

## v1.16.0 (2026-04-09)

### Added
- **Eval comparison infrastructure** — A/B baseline diffing with `--save-baseline`, `--compare-baseline`, `--fail-on-regression` CLI flags.
- **Prompt token audit** — `--audit-prompt` shows token cost per prompt section.
- **Section ablation framework** — test impact of removing prompt sections on eval scores.
- **View designer eval suite** — 6 scenarios + 4 new replay fixtures (17 total).
- **Eval history DB** — `eval_runs` table (migration 006) with trends API (`GET /eval/history`, `GET /eval/trend`).
- **CI automation** — live judge runs on releases, daily cron, prompt change triggers.
- **GitHub secrets** for Vertex AI (`VERTEX_PROJECT_ID`, `VERTEX_REGION`, `GCP_SA_KEY`).
- **UI Evals tab** on Agent Settings — quality gate, suite scores, dimension bars, prompt audit viz, sparkline trends.
- **ToolsView accessibility fixes** — aria-labels, keyboard nav, ToolCard extraction.
- **View designer prompt improvement** — specific commands, cautious writes.
- **bump-version.sh** auto-updates umbrella chart subchart.
- **Replay harness** — thinking parameter support, config singleton fix, model defaults to `claude-sonnet-4-6`.

## v1.15.0 (2026-04-09)

### Added
- **Modular package architecture** — Split 3 largest files into focused packages: `k8s_tools/` (11 modules, was 4419 lines), `monitor/` (10 modules, was 2486 lines), `api/` (12 modules, was 2415 lines). No file exceeds 910 lines. All backward-compatible imports preserved.
- **Typo auto-correction** — `fix_typos()` corrects ~130 common K8s/SRE misspellings (deployment, namespace, prometheus, vulnerability, etc.) with automatic plural/suffix handling. Applied before intent classification and tool selection.
- **Route safety tests** — 22 tests guard against broken GVR routes (leading tilde, wrong namespace wildcard, double slashes in API paths).
- **Centralized configuration** — All ~30 raw `os.environ.get()` calls migrated to `get_settings()`. Added 6 missing config fields: `db_pool_min/max`, `noise_threshold`, `max_trust_level`, `investigations_max_per_scan`, `investigation_cooldown`, `dev_user`.

### Removed
- **`layout_templates.py`** — deleted deprecated module (replaced by `layout_engine.py`), along with 4 backward-compat tests.
- **Dead code** — removed unused `DEFAULT_DB_PATH` constant, identity typo mapping, unused `os` imports from 4 files.

### Fixed
- **Nodes page 404** — `TopologyMap.tsx` used `/r/~v1~nodes/*` which decoded to empty API group (`/apis//v1/nodes`). Fixed to `/r/v1~nodes/_`.
- **CRDs route bug** — `CRDsView.tsx` produced leading tilde for CRDs with empty `spec.group`.
- **`MAX_RESULTS` duplication** — was defined identically in 8 k8s_tools submodules; centralized to `validators.py`.

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
