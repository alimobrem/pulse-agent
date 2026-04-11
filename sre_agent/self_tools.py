"""Self-description tools — let the agent tell users what it can do.

Tools for agent self-awareness: skills, tools, and UI components.
"""

from __future__ import annotations

from anthropic import beta_tool


@beta_tool
def list_my_skills() -> str:
    """List all available agent skills with descriptions. Call when the user asks what you can do or what skills you have."""
    from .skill_loader import list_skills

    skills = list_skills()
    lines = [f"I have {len(skills)} skills:\n"]
    for skill in sorted(skills, key=lambda s: -s.priority):
        status = " (degraded)" if skill.degraded else ""
        lines.append(f"**{skill.name}** v{skill.version}{status} — {skill.description}")
        if skill.categories:
            lines.append(f"  Categories: {', '.join(skill.categories)}")
        if skill.handoff_to:
            targets = ", ".join(skill.handoff_to.keys())
            lines.append(f"  Can hand off to: {targets}")

    return "\n".join(lines)


@beta_tool
def list_my_tools() -> str:
    """List all tools available to the agent grouped by source. Call when the user asks what tools you have."""
    from .mcp_client import list_mcp_tools
    from .tool_registry import TOOL_REGISTRY

    try:
        mcp_names = {t["name"] for t in list_mcp_tools()}
    except Exception:
        mcp_names = set()

    native = []
    mcp = []
    for name in sorted(TOOL_REGISTRY):
        tool = TOOL_REGISTRY[name]
        desc = getattr(tool, "description", "")[:80]
        if name in mcp_names:
            mcp.append(f"- `{name}` — {desc}")
        else:
            native.append(f"- `{name}` — {desc}")

    lines = [f"I have {len(TOOL_REGISTRY)} tools:\n"]
    lines.append(f"**Native ({len(native)}):**")
    lines.extend(native[:30])  # cap to avoid massive output
    if len(native) > 30:
        lines.append(f"  ... and {len(native) - 30} more")
    if mcp:
        lines.append(f"\n**MCP ({len(mcp)}):**")
        lines.extend(mcp)

    return "\n".join(lines)


@beta_tool
def list_ui_components() -> str:
    """List all UI component types the agent can render in dashboards and chat responses.

    Call when the user asks what visualizations, components, or widget types are available.
    """
    from .component_registry import COMPONENT_REGISTRY

    lines = [f"I can render {len(COMPONENT_REGISTRY)} UI component types:\n"]

    by_category: dict[str, list[tuple[str, str]]] = {}
    for name, comp in COMPONENT_REGISTRY.items():
        cat = comp.category
        if cat not in by_category:
            by_category[cat] = []
        mutations = f" (editable: {', '.join(comp.supports_mutations)})" if comp.supports_mutations else ""
        by_category[cat].append((name, f"{comp.description}{mutations}"))

    for cat in sorted(by_category):
        lines.append(f"\n**{cat.title()}:**")
        for name, desc in sorted(by_category[cat]):
            lines.append(f"- `{name}` — {desc}")

    return "\n".join(lines)


@beta_tool
def list_promql_recipes(category: str = "") -> str:
    """List available PromQL query recipes by category.

    Call when the user asks what metrics, queries, or PromQL recipes are available.
    If category is empty, shows all categories with counts. If specified, shows
    recipes in that category with their queries.

    Categories: cpu, memory, network, storage, pods, alerts, cluster_health,
    control_plane, ingress, monitoring, node_use, operators, overcommit,
    scheduler, storage_state, workload_state
    """
    from .promql_recipes import RECIPES

    if not category:
        total = sum(len(v) for v in RECIPES.values())
        lines = [f"I have {total} PromQL recipes across {len(RECIPES)} categories:\n"]
        for cat in sorted(RECIPES):
            lines.append(f"- **{cat}** ({len(RECIPES[cat])} recipes)")
        lines.append("\nAsk for a specific category to see the queries (e.g., 'show me cpu recipes').")
        return "\n".join(lines)

    recipes = RECIPES.get(category, [])
    if not recipes:
        return f"No recipes for category '{category}'. Available: {', '.join(sorted(RECIPES.keys()))}"

    lines = [f"**{category}** — {len(recipes)} recipes:\n"]
    for r in recipes:
        lines.append(f"**{r.name}** ({r.scope})")
        lines.append(f"  `{r.query}`")
        lines.append(f"  {r.description} — renders as {r.chart_type}")
        lines.append("")

    return "\n".join(lines)


@beta_tool
def list_runbooks() -> str:
    """List available SRE runbooks that guide incident diagnosis.

    Call when the user asks what runbooks are available, what incidents
    you can help with, or what diagnostic workflows you know.
    """
    from .runbooks import _RUNBOOK_KEYWORDS

    lines = [f"I have {len(_RUNBOOK_KEYWORDS)} diagnostic runbooks:\n"]
    descriptions = {
        "crashloop": "Pod stuck in CrashLoopBackOff — check logs, exit codes, resource limits",
        "imagepull": "ImagePullBackOff — check registry auth, image tag, network policies",
        "oomkilled": "OOMKilled pods — check memory limits, leak detection, VPA recommendations",
        "node_notready": "Node NotReady — check kubelet, disk pressure, memory pressure, network",
        "pvc_pending": "PVC stuck Pending — check StorageClass, provisioner, capacity",
        "dns": "DNS resolution failures — check CoreDNS pods, configmap, network policies",
        "high_restarts": "High container restart count — check liveness probes, resource limits",
        "deployment_stuck": "Deployment not progressing — check rollout status, pod scheduling, events",
        "operator_degraded": "ClusterOperator degraded — check operator pods, CRDs, dependencies",
        "quota": "Resource quota exceeded — check namespace quotas, limit ranges, usage",
    }

    for name, keywords in sorted(_RUNBOOK_KEYWORDS.items()):
        desc = descriptions.get(name, f"Triggers on: {', '.join(keywords[:3])}")
        lines.append(f"- **{name}** — {desc}")

    return "\n".join(lines)
