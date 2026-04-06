"""View Validator — thin wrapper around quality_engine for backward compatibility.

All validation logic now lives in ``quality_engine.py``. This module
re-exports ``is_generic_title`` and ``validate_components`` so existing
callers (api.py, tests) continue to work.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .quality_engine import VALID_KINDS, evaluate_components, is_generic_title  # noqa: F401


@dataclass
class ValidationResult:
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    deduped_count: int = 0
    components: list[dict] = field(default_factory=list)


def validate_components(
    components: list[dict],
    *,
    max_widgets: int = 8,
    min_widgets: int = 3,
) -> ValidationResult:
    """Validate and deduplicate a list of dashboard components.

    Delegates to ``quality_engine.evaluate_components`` and converts the
    result to the legacy ``ValidationResult`` shape.
    """
    qr = evaluate_components(components, positions=None, max_widgets=max_widgets, min_widgets=min_widgets)
    vr = ValidationResult(
        valid=qr.valid,
        errors=qr.errors,
        warnings=qr.warnings,
        deduped_count=qr.deduped_count,
        components=qr.components,
    )
    return vr
