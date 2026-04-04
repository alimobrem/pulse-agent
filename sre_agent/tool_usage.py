"""Tool usage recording — fire-and-forget functions for tracking tool calls and turns."""

from __future__ import annotations

import json
import logging

logger = logging.getLogger("pulse_agent.tool_usage")

# Secret field names to redact
_SECRET_FIELDS = {
    "token",
    "password",
    "key",
    "secret",
    "credential",
    "yaml_content",
    "new_content",
    "content",
}

_MAX_STRING_LEN = 256
_MAX_JSON_BYTES = 1024


def sanitize_input(input_data: dict | None) -> dict | None:
    """Sanitize tool input data for storage.

    - Returns None if input is None
    - Returns {} if input is empty
    - Strips secret fields (replaces with <redacted N chars>)
    - Truncates strings longer than 256 chars
    - Caps total JSON size at ~1KB
    """
    if input_data is None:
        return None

    if not input_data:
        return {}

    # First pass: redact secrets and truncate strings
    sanitized = {}
    for key, value in input_data.items():
        if key.lower() in _SECRET_FIELDS:
            if isinstance(value, str):
                sanitized[key] = f"<redacted {len(value)} chars>"
            else:
                sanitized[key] = "<redacted>"
        elif isinstance(value, str):
            if len(value) > _MAX_STRING_LEN:
                sanitized[key] = value[:_MAX_STRING_LEN] + "..."
            else:
                sanitized[key] = value
        else:
            sanitized[key] = value

    # Second pass: cap total size
    encoded = json.dumps(sanitized)
    if len(encoded) <= _MAX_JSON_BYTES:
        return sanitized

    # Drop keys until we fit
    result = {}
    for key, value in sanitized.items():
        result[key] = value
        if len(json.dumps(result)) > _MAX_JSON_BYTES:
            del result[key]
            break

    return result


def record_tool_call(
    *,
    session_id: str,
    turn_number: int,
    agent_mode: str,
    tool_name: str,
    tool_category: str | None,
    input_data: dict | None,
    status: str,
    error_message: str | None,
    error_category: str | None,
    duration_ms: int,
    result_bytes: int,
    requires_confirmation: bool,
    was_confirmed: bool | None,
) -> None:
    """Record a tool call to the tool_usage table.

    Fire-and-forget: swallows all exceptions, logs at debug level.
    Uses %s placeholders for PostgreSQL.
    """
    try:
        from .db import get_database

        db = get_database()
        sanitized = sanitize_input(input_data)

        db.execute(
            "INSERT INTO tool_usage "
            "(session_id, turn_number, agent_mode, tool_name, tool_category, "
            "input_summary, status, error_message, error_category, "
            "duration_ms, result_bytes, requires_confirmation, was_confirmed) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                session_id,
                turn_number,
                agent_mode,
                tool_name,
                tool_category,
                json.dumps(sanitized) if sanitized is not None else None,
                status,
                error_message,
                error_category,
                duration_ms,
                result_bytes,
                requires_confirmation,
                was_confirmed,
            ),
        )
        db.commit()
        logger.debug(f"Recorded tool call: {tool_name} (session={session_id}, turn={turn_number}, status={status})")
    except Exception as e:
        logger.debug(f"Failed to record tool call: {e}")


def record_turn(
    *,
    session_id: str,
    turn_number: int,
    agent_mode: str,
    query_summary: str,
    tools_offered: list[str],
    tools_called: list[str],
) -> None:
    """Record a turn to the tool_turns table.

    Fire-and-forget: swallows all exceptions, logs at debug level.
    Uses ON CONFLICT upsert on (session_id, turn_number).
    Truncates query_summary to 200 chars.
    """
    try:
        from .db import get_database

        db = get_database()

        # Truncate query summary
        if len(query_summary) > 200:
            query_summary = query_summary[:200]

        db.execute(
            "INSERT INTO tool_turns "
            "(session_id, turn_number, agent_mode, query_summary, tools_offered, tools_called) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (session_id, turn_number) DO UPDATE SET "
            "tools_called = EXCLUDED.tools_called",
            (session_id, turn_number, agent_mode, query_summary, tools_offered, tools_called),
        )
        db.commit()
        logger.debug(
            f"Recorded turn: session={session_id}, turn={turn_number}, offered={len(tools_offered)}, called={len(tools_called)}"
        )
    except Exception as e:
        logger.debug(f"Failed to record turn: {e}")


def update_turn_feedback(
    *,
    session_id: str,
    feedback: str,
) -> None:
    """Update the most recent turn for a session with feedback.

    Fire-and-forget: swallows all exceptions, logs at debug level.
    Uses subquery to find the latest turn by turn_number.
    """
    try:
        from .db import get_database

        db = get_database()

        db.execute(
            "UPDATE tool_turns SET feedback = %s "
            "WHERE id = (SELECT id FROM tool_turns WHERE session_id = %s ORDER BY turn_number DESC LIMIT 1)",
            (feedback, session_id),
        )
        db.commit()
        logger.debug(f"Updated turn feedback: session={session_id}, feedback={feedback}")
    except Exception as e:
        logger.debug(f"Failed to update turn feedback: {e}")
