"""Auto-postmortem generation from skill plan outputs."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger("pulse_agent.postmortem")


@dataclass
class Postmortem:
    """Structured postmortem record."""

    id: str
    incident_type: str
    plan_id: str
    timeline: str = ""
    root_cause: str = ""
    contributing_factors: list[str] = field(default_factory=list)
    blast_radius: list[str] = field(default_factory=list)
    actions_taken: list[str] = field(default_factory=list)
    prevention: list[str] = field(default_factory=list)
    metrics_impact: str = ""
    confidence: float = 0.0
    generated_at: int = 0


def build_postmortem_context(phase_outputs: dict) -> str:
    """Build context for the postmortem skill from completed plan phases.

    Compresses all phase outputs into a structured summary that the
    postmortem skill can use to generate the report.
    """
    if not phase_outputs:
        return "No investigation data available."

    lines = ["## Investigation Evidence\n"]

    for phase_id, output in phase_outputs.items():
        lines.append(f"### Phase: {phase_id}")
        lines.append(f"Status: {output.status} (confidence: {output.confidence:.2f})")

        if output.evidence_summary:
            lines.append(f"Evidence: {output.evidence_summary}")

        if output.findings:
            for k, v in list(output.findings.items())[:8]:
                lines.append(f"- {k}: {v}")

        if output.actions_taken:
            lines.append(f"Actions: {', '.join(output.actions_taken)}")

        if output.risk_flags:
            lines.append(f"Risks: {', '.join(output.risk_flags)}")

        if output.open_questions:
            lines.append(f"Open questions: {', '.join(output.open_questions)}")

        lines.append("")

    return "\n".join(lines)


def save_postmortem(postmortem: Postmortem) -> None:
    """Save a postmortem to the database. Fire-and-forget."""
    try:
        import json

        from .db import get_database

        db = get_database()
        db.execute(
            "INSERT INTO postmortems (id, incident_type, plan_id, timeline, root_cause, "
            "contributing_factors, blast_radius, actions_taken, prevention, metrics_impact, "
            "confidence, generated_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (id) DO UPDATE SET "
            "timeline = EXCLUDED.timeline, root_cause = EXCLUDED.root_cause, "
            "confidence = EXCLUDED.confidence",
            (
                postmortem.id,
                postmortem.incident_type,
                postmortem.plan_id,
                postmortem.timeline,
                postmortem.root_cause,
                json.dumps(postmortem.contributing_factors),
                json.dumps(postmortem.blast_radius),
                json.dumps(postmortem.actions_taken),
                json.dumps(postmortem.prevention),
                postmortem.metrics_impact,
                postmortem.confidence,
                postmortem.generated_at,
            ),
        )
        db.commit()
        logger.info("Saved postmortem %s for %s", postmortem.id, postmortem.incident_type)
    except Exception:
        logger.debug("Failed to save postmortem", exc_info=True)
