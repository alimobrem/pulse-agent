"""Intelligence Loop — feeds analytics data back into the agent system prompt.

Computes query reliability, dashboard patterns, and error hotspots from the
last 7 days of tool_usage and promql_queries data. Injected into the system
prompt via harness.py get_cluster_context().
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger("pulse_agent.intelligence")

_intelligence_cache: dict[str, tuple[str, float]] = {}
_CACHE_TTL = 600  # 10 minutes


def get_intelligence_context(mode: str = "sre", max_age_days: int = 7) -> str:
    """Compute intelligence summary from analytics data."""
    now = time.time()
    cached = _intelligence_cache.get(mode)
    if cached and now - cached[1] < _CACHE_TTL:
        return cached[0]

    try:
        sections: list[str] = []
        qr = _compute_query_reliability(max_age_days)
        if qr:
            sections.append(qr)
        dp = _compute_dashboard_patterns(max_age_days)
        if dp:
            sections.append(dp)
        eh = _compute_error_hotspots(max_age_days)
        if eh:
            sections.append(eh)
        te = _compute_token_efficiency(max_age_days)
        if te:
            sections.append(te)
        he = _compute_harness_effectiveness(max_age_days)
        if he:
            sections.append(he)
        ra = _compute_routing_accuracy(max_age_days)
        if ra:
            sections.append(ra)
        fa = _compute_feedback_analysis(max_age_days)
        if fa:
            sections.append(fa)
        tt = _compute_token_trending(max_age_days)
        if tt:
            sections.append(tt)

        if not sections:
            result = ""
        else:
            result = f"## Agent Intelligence (last {max_age_days} days)\n\n" + "\n\n".join(sections)

        _intelligence_cache[mode] = (result, now)
        return result
    except Exception:
        logger.debug("Failed to compute intelligence context", exc_info=True)
        return ""


def _compute_query_reliability(days: int) -> str:
    """Compute PromQL query reliability from promql_queries table."""
    try:
        from .db import get_database

        db = get_database()
        rows = db.fetchall(
            f"SELECT query_template, success_count, failure_count "
            f"FROM promql_queries "
            f"WHERE (last_success > NOW() - INTERVAL '{days} days' "
            f"   OR last_failure > NOW() - INTERVAL '{days} days') "
            f"AND success_count + failure_count >= 3 "
            f"ORDER BY success_count + failure_count DESC "
            f"LIMIT 20",
        )
        if not rows:
            return ""

        preferred: list[str] = []
        avoid: list[str] = []

        for row in rows:
            template = row["query_template"]
            success = row["success_count"]
            failure = row["failure_count"]
            total = success + failure
            rate = success / total if total > 0 else 0

            truncated = template[:80] + "..." if len(template) > 80 else template

            if rate > 0.8 and len(preferred) < 10:
                preferred.append(f"- `{truncated}`: {success}/{total} success → USE THIS")
            elif rate < 0.3 and len(avoid) < 5:
                avoid.append(f"- `{truncated}`: {success}/{total} success → AVOID")

        if not preferred and not avoid:
            return ""

        lines = ["### Query Reliability"]
        if preferred:
            lines.append("**Preferred queries:**")
            lines.extend(preferred)
        if avoid:
            lines.append("**Unreliable queries (avoid):**")
            lines.extend(avoid)
        return "\n".join(lines)
    except Exception:
        logger.debug("Failed to compute query reliability", exc_info=True)
        return ""


def _compute_dashboard_patterns(days: int) -> str:
    """Compute dashboard/view designer usage patterns from tool_usage."""
    try:
        from .db import get_database

        db = get_database()

        tool_rows = db.fetchall(
            f"SELECT tool_name, COUNT(*) as call_count "
            f"FROM tool_usage "
            f"WHERE agent_mode = 'view_designer' "
            f"  AND timestamp > NOW() - INTERVAL '{days} days' "
            f"  AND status = 'success' "
            f"GROUP BY tool_name "
            f"ORDER BY call_count DESC "
            f"LIMIT 10",
        )

        avg_row = db.fetchone(
            f"SELECT AVG(tool_count)::int as avg_tools FROM ("
            f"    SELECT session_id, COUNT(*) as tool_count "
            f"    FROM tool_usage "
            f"    WHERE agent_mode = 'view_designer' "
            f"      AND timestamp > NOW() - INTERVAL '{days} days' "
            f"    GROUP BY session_id"
            f") sub",
        )

        if not tool_rows:
            return ""

        lines = ["### Dashboard Patterns"]
        if avg_row and avg_row.get("avg_tools"):
            lines.append(f"Average tools per dashboard session: {avg_row['avg_tools']}")
        lines.append("**Most used tools in view building:**")
        for row in tool_rows:
            lines.append(f"- {row['tool_name']}: {row['call_count']} calls")
        return "\n".join(lines)
    except Exception:
        logger.debug("Failed to compute dashboard patterns", exc_info=True)
        return ""


def _compute_error_hotspots(days: int) -> str:
    """Compute tools with high error rates from tool_usage."""
    try:
        from .db import get_database

        db = get_database()

        hotspot_rows = db.fetchall(
            f"SELECT tool_name, "
            f"       COUNT(*) FILTER (WHERE status = 'error') as error_count, "
            f"       COUNT(*) as total_count "
            f"FROM tool_usage "
            f"WHERE timestamp > NOW() - INTERVAL '{days} days' "
            f"GROUP BY tool_name "
            f"HAVING COUNT(*) > 5 "
            f"   AND COUNT(*) FILTER (WHERE status = 'error')::float / COUNT(*) > 0.05 "
            f"ORDER BY COUNT(*) FILTER (WHERE status = 'error')::float / COUNT(*) DESC "
            f"LIMIT 5",
        )

        if not hotspot_rows:
            return ""

        lines = ["### Error Hotspots"]
        for row in hotspot_rows:
            tool = row["tool_name"]
            errors = row["error_count"]
            total = row["total_count"]
            error_rate = round(errors / total * 100, 1) if total > 0 else 0

            # Get most common error message for this tool
            err_msg = ""
            try:
                err_row = db.fetchone(
                    f"SELECT error_message, COUNT(*) as cnt "
                    f"FROM tool_usage "
                    f"WHERE tool_name = ? AND status = 'error' "
                    f"  AND timestamp > NOW() - INTERVAL '{days} days' "
                    f"  AND error_message IS NOT NULL "
                    f"GROUP BY error_message "
                    f"ORDER BY cnt DESC "
                    f"LIMIT 1",
                    (tool,),
                )
                if err_row and err_row.get("error_message"):
                    err_msg = err_row["error_message"][:80]
            except Exception:
                pass

            line = f"- {tool}: {error_rate}% error rate ({errors}/{total})"
            if err_msg:
                line += f' — common: "{err_msg}"'
            lines.append(line)

        return "\n".join(lines)
    except Exception:
        logger.debug("Failed to compute error hotspots", exc_info=True)
        return ""


def _compute_token_efficiency(days: int) -> str:
    """Compute token usage efficiency metrics from tool_turns."""
    try:
        from .db import get_database

        db = get_database()
        row = db.fetchone(
            f"SELECT COALESCE(ROUND(AVG(input_tokens)), 0) AS avg_input, "
            f"COALESCE(ROUND(AVG(output_tokens)), 0) AS avg_output, "
            f"COALESCE(ROUND(AVG(cache_read_tokens)), 0) AS avg_cache, "
            f"COUNT(*) AS total_turns "
            f"FROM tool_turns "
            f"WHERE input_tokens IS NOT NULL "
            f"AND timestamp > NOW() - INTERVAL '{days} days'",
        )
        if not row or not row.get("total_turns"):
            return ""

        lines = ["### Token Efficiency"]
        lines.append(f"Average input tokens per turn: {int(row['avg_input'])}")
        lines.append(f"Average output tokens per turn: {int(row['avg_output'])}")
        avg_cache = int(row["avg_cache"])
        if avg_cache:
            total_input = int(row["avg_input"]) or 1
            cache_pct = round((avg_cache / total_input) * 100)
            lines.append(f"Cache hit rate: {cache_pct}%")
        lines.append(f"Total turns analyzed: {row['total_turns']}")
        return "\n".join(lines)
    except Exception:
        logger.debug("Failed to compute token efficiency", exc_info=True)
        return ""


def _compute_harness_effectiveness(days: int) -> str:
    """Compute tool selection accuracy and wasted tools from tool_turns."""
    try:
        from .db import get_database

        db = get_database()

        # Selection accuracy: avg ratio of tools_called / tools_offered
        acc_row = db.fetchone(
            f"SELECT AVG(array_length(tools_called, 1)::float "
            f"/ NULLIF(array_length(tools_offered, 1), 0)) as accuracy, "
            f"COALESCE(ROUND(AVG(array_length(tools_called, 1))), 0) as avg_called, "
            f"COALESCE(ROUND(AVG(array_length(tools_offered, 1))), 0) as avg_offered "
            f"FROM tool_turns "
            f"WHERE tools_offered IS NOT NULL AND tools_called IS NOT NULL "
            f"AND timestamp > NOW() - INTERVAL '{days} days'",
        )

        if not acc_row or acc_row.get("accuracy") is None:
            return ""

        accuracy_pct = round(acc_row["accuracy"] * 100)
        avg_called = int(acc_row["avg_called"])
        avg_offered = int(acc_row["avg_offered"])

        lines = ["### Harness Effectiveness"]
        lines.append(
            f"Tool selection accuracy: {accuracy_pct}% (avg {avg_called} of {avg_offered} offered tools used per turn)"
        )

        # Wasted tools: offered 20+ times but called <5% of the time
        wasted_rows = db.fetchall(
            f"WITH offered AS ("
            f"    SELECT unnest(tools_offered) as tool_name, COUNT(*) as offered_count "
            f"    FROM tool_turns "
            f"    WHERE timestamp > NOW() - INTERVAL '{days} days' AND tools_offered IS NOT NULL "
            f"    GROUP BY 1"
            f"), "
            f"called AS ("
            f"    SELECT unnest(tools_called) as tool_name, COUNT(*) as called_count "
            f"    FROM tool_turns "
            f"    WHERE timestamp > NOW() - INTERVAL '{days} days' AND tools_called IS NOT NULL "
            f"    GROUP BY 1"
            f") "
            f"SELECT o.tool_name, o.offered_count, COALESCE(c.called_count, 0) as called_count "
            f"FROM offered o "
            f"LEFT JOIN called c ON o.tool_name = c.tool_name "
            f"WHERE o.offered_count >= 20 "
            f"AND COALESCE(c.called_count, 0)::float / o.offered_count < 0.05 "
            f"ORDER BY o.offered_count DESC "
            f"LIMIT 10",
        )

        if wasted_rows:
            lines.append("Wasted tools (offered but rarely used):")
            for row in wasted_rows:
                offered = row["offered_count"]
                called = row["called_count"]
                pct = round(called / offered * 100) if offered else 0
                lines.append(f"- {row['tool_name']}: offered {offered}x, used {called}x ({pct}%)")

        return "\n".join(lines)
    except Exception:
        logger.debug("Failed to compute harness effectiveness", exc_info=True)
        return ""


def _compute_routing_accuracy(days: int) -> str:
    """Compute mode routing accuracy from mode switches within sessions."""
    try:
        from .db import get_database

        db = get_database()

        row = db.fetchone(
            f"SELECT "
            f"    COUNT(*) FILTER (WHERE agent_mode != prev_mode) as switches, "
            f"    COUNT(*) as total "
            f"FROM ("
            f"    SELECT agent_mode, "
            f"           LAG(agent_mode) OVER (PARTITION BY session_id ORDER BY turn_number) as prev_mode "
            f"    FROM tool_turns "
            f"    WHERE timestamp > NOW() - INTERVAL '{days} days'"
            f") sub "
            f"WHERE prev_mode IS NOT NULL",
        )

        if not row or not row.get("total"):
            return ""

        switches = row["switches"]
        total = row["total"]
        switch_pct = round(switches / total * 100) if total else 0
        accuracy = 100 - switch_pct

        return (
            f"### Routing Accuracy\n"
            f"Mode routing accuracy: {accuracy}% "
            f"({switch_pct}% of multi-turn sessions had mode switches)"
        )
    except Exception:
        logger.debug("Failed to compute routing accuracy", exc_info=True)
        return ""


def _compute_feedback_analysis(days: int) -> str:
    """Correlate feedback with tools to find tools with negative feedback."""
    try:
        from .db import get_database

        db = get_database()

        rows = db.fetchall(
            f"SELECT u.tool_name, "
            f"       COUNT(*) FILTER (WHERE t.feedback = 'negative') as negative, "
            f"       COUNT(*) as total "
            f"FROM tool_turns t "
            f"JOIN tool_usage u ON t.session_id = u.session_id AND t.turn_number = u.turn_number "
            f"WHERE t.feedback IS NOT NULL "
            f"AND t.timestamp > NOW() - INTERVAL '{days} days' "
            f"GROUP BY u.tool_name "
            f"HAVING COUNT(*) FILTER (WHERE t.feedback = 'negative') > 0 "
            f"ORDER BY COUNT(*) FILTER (WHERE t.feedback = 'negative')::float / COUNT(*) DESC "
            f"LIMIT 5",
        )

        if not rows:
            return ""

        lines = ["### Feedback Analysis", "Tools with negative feedback:"]
        for row in rows:
            lines.append(f"- {row['tool_name']}: {row['negative']}/{row['total']} negative")

        return "\n".join(lines)
    except Exception:
        logger.debug("Failed to compute feedback analysis", exc_info=True)
        return ""


def _compute_token_trending(days: int) -> str:
    """Compute week-over-week token usage trending."""
    try:
        from .db import get_database

        db = get_database()

        row = db.fetchone(
            f"SELECT "
            f"    AVG(input_tokens) FILTER (WHERE timestamp > NOW() - INTERVAL '{days} days') as current_avg, "
            f"    AVG(input_tokens) FILTER (WHERE timestamp BETWEEN "
            f"NOW() - INTERVAL '{days * 2} days' AND NOW() - INTERVAL '{days} days') as prev_avg, "
            f"    AVG(output_tokens) FILTER (WHERE timestamp > NOW() - INTERVAL '{days} days') as current_output "
            f"FROM tool_turns "
            f"WHERE input_tokens IS NOT NULL",
        )

        if not row or row.get("current_avg") is None:
            return ""

        current_avg = int(row["current_avg"])
        current_output = int(row["current_output"]) if row.get("current_output") else 0

        lines = ["### Token Trending"]

        prev_avg = row.get("prev_avg")
        if prev_avg and prev_avg > 0:
            change_pct = round((current_avg - prev_avg) / prev_avg * 100)
            arrow = "\u2193" if change_pct < 0 else "\u2191"
            lines.append(f"Avg input: {current_avg:,} tokens ({arrow}{abs(change_pct)}% from last week)")
        else:
            lines.append(f"Avg input: {current_avg:,} tokens")

        lines.append(f"Avg output: {current_output:,} tokens")

        return "\n".join(lines)
    except Exception:
        logger.debug("Failed to compute token trending", exc_info=True)
        return ""


def get_wasted_tools(days: int = 7) -> list[str]:
    """Return tool names that are offered frequently but rarely used.

    Used by harness.py to auto-deprioritize unused tools.
    """
    try:
        from .db import get_database

        db = get_database()

        rows = db.fetchall(
            f"WITH offered AS ("
            f"    SELECT unnest(tools_offered) as tool_name, COUNT(*) as offered_count "
            f"    FROM tool_turns "
            f"    WHERE timestamp > NOW() - INTERVAL '{days} days' AND tools_offered IS NOT NULL "
            f"    GROUP BY 1"
            f"), "
            f"called AS ("
            f"    SELECT unnest(tools_called) as tool_name, COUNT(*) as called_count "
            f"    FROM tool_turns "
            f"    WHERE timestamp > NOW() - INTERVAL '{days} days' AND tools_called IS NOT NULL "
            f"    GROUP BY 1"
            f") "
            f"SELECT o.tool_name "
            f"FROM offered o "
            f"LEFT JOIN called c ON o.tool_name = c.tool_name "
            f"WHERE o.offered_count >= 20 "
            f"AND COALESCE(c.called_count, 0)::float / o.offered_count < 0.02 "
            f"ORDER BY o.offered_count DESC",
        )

        return [row["tool_name"] for row in rows] if rows else []
    except Exception:
        logger.debug("Failed to get wasted tools", exc_info=True)
        return []
