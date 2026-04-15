"""Log fingerprint extraction — classifies pod log errors into routing signals.

Pulls recent logs from affected pods, matches against known error patterns,
and returns fingerprint categories used by the skill selector and
investigation prompts for faster, more accurate routing.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger("pulse_agent.log_fingerprinter")

# Error pattern → category mapping
# Each category maps to skill routing hints
ERROR_PATTERNS: dict[str, list[re.Pattern]] = {
    "oom": [
        re.compile(r"OOMKilled", re.IGNORECASE),
        re.compile(r"out of memory", re.IGNORECASE),
        re.compile(r"memory limit exceeded", re.IGNORECASE),
        re.compile(r"cannot allocate memory", re.IGNORECASE),
        re.compile(r"killed.*memory", re.IGNORECASE),
    ],
    "connection": [
        re.compile(r"connection refused"),
        re.compile(r"dial tcp.*refused"),
        re.compile(r"no route to host"),
        re.compile(r"connect: connection timed out"),
        re.compile(r"i/o timeout"),
        re.compile(r"connection reset by peer"),
    ],
    "timeout": [
        re.compile(r"context deadline exceeded"),
        re.compile(r"timeout", re.IGNORECASE),
        re.compile(r"timed out", re.IGNORECASE),
        re.compile(r"deadline exceeded"),
    ],
    "auth": [
        re.compile(r"unauthorized", re.IGNORECASE),
        re.compile(r"forbidden", re.IGNORECASE),
        re.compile(r"403 Forbidden"),
        re.compile(r"401 Unauthorized"),
        re.compile(r"authentication failed", re.IGNORECASE),
        re.compile(r"certificate.*expired", re.IGNORECASE),
    ],
    "crash": [
        re.compile(r"panic:"),
        re.compile(r"fatal error:"),
        re.compile(r"segfault"),
        re.compile(r"SIGSEGV"),
        re.compile(r"SIGABRT"),
        re.compile(r"Traceback \(most recent call last\)"),
        re.compile(r"Exception in thread"),
    ],
    "config": [
        re.compile(r"missing.*key", re.IGNORECASE),
        re.compile(r"invalid.*config", re.IGNORECASE),
        re.compile(r"no such file or directory"),
        re.compile(r"FileNotFoundError"),
        re.compile(r"configmap.*not found", re.IGNORECASE),
        re.compile(r"secret.*not found", re.IGNORECASE),
    ],
    "image": [
        re.compile(r"ImagePullBackOff"),
        re.compile(r"ErrImagePull"),
        re.compile(r"manifest unknown"),
        re.compile(r"repository does not exist"),
        re.compile(r"image.*not found", re.IGNORECASE),
    ],
    "resource": [
        re.compile(r"quota exceeded", re.IGNORECASE),
        re.compile(r"insufficient cpu", re.IGNORECASE),
        re.compile(r"insufficient memory", re.IGNORECASE),
        re.compile(r"exceeded quota"),
        re.compile(r"LimitRange"),
    ],
    "dns": [
        re.compile(r"could not resolve host", re.IGNORECASE),
        re.compile(r"name resolution failure", re.IGNORECASE),
        re.compile(r"NXDOMAIN"),
        re.compile(r"no such host"),
    ],
    "storage": [
        re.compile(r"disk full", re.IGNORECASE),
        re.compile(r"no space left on device"),
        re.compile(r"volume.*not found", re.IGNORECASE),
        re.compile(r"FailedMount"),
        re.compile(r"MountVolume.*failed"),
    ],
}

# Fingerprint category → skill routing hint
FINGERPRINT_SKILL_MAP: dict[str, str] = {
    "oom": "sre",
    "connection": "sre",
    "timeout": "sre",
    "auth": "security",
    "crash": "sre",
    "config": "sre",
    "image": "sre",
    "resource": "capacity_planner",
    "dns": "sre",
    "storage": "sre",
}


def fingerprint_text(text: str) -> list[dict]:
    """Classify a text block against known error patterns.

    Returns list of {category, pattern, skill_hint, count} sorted by count.
    """
    if not text:
        return []

    results: dict[str, dict] = {}

    for category, patterns in ERROR_PATTERNS.items():
        total_matches = 0
        first_match = ""
        for pattern in patterns:
            matches = pattern.findall(text)
            if matches:
                total_matches += len(matches)
                if not first_match:
                    first_match = matches[0]

        if total_matches > 0:
            results[category] = {
                "category": category,
                "pattern": first_match,
                "skill_hint": FINGERPRINT_SKILL_MAP.get(category, "sre"),
                "count": total_matches,
            }

    return sorted(results.values(), key=lambda x: -x["count"])


def fingerprint_pod_logs(pod_name: str, namespace: str, tail_lines: int = 100) -> list[dict]:
    """Pull recent logs from a pod and fingerprint them.

    Returns list of {category, pattern, skill_hint, count}.
    """
    try:
        from .k8s_client import get_core_client, safe

        result = safe(lambda: get_core_client().read_namespaced_pod_log(pod_name, namespace, tail_lines=tail_lines))

        if isinstance(result, str) and not result.startswith("Error"):
            return fingerprint_text(result)

        return []
    except Exception:
        logger.debug("Failed to fingerprint logs for %s/%s", namespace, pod_name, exc_info=True)
        return []


def fingerprint_finding(finding: dict) -> list[dict]:
    """Fingerprint logs from all resources in a finding.

    Combines fingerprints across all pods in the finding.
    """
    all_fingerprints: dict[str, dict] = {}

    # Fingerprint from finding summary text
    summary = finding.get("summary", "")
    title = finding.get("title", "")
    for fp in fingerprint_text(f"{title} {summary}"):
        cat = fp["category"]
        if cat in all_fingerprints:
            all_fingerprints[cat]["count"] += fp["count"]
        else:
            all_fingerprints[cat] = fp

    # Fingerprint from pod logs
    for resource in finding.get("resources", [])[:3]:  # limit to 3 pods
        if resource.get("kind") == "Pod":
            pod_fps = fingerprint_pod_logs(
                resource["name"],
                resource.get("namespace", "default"),
            )
            for fp in pod_fps:
                cat = fp["category"]
                if cat in all_fingerprints:
                    all_fingerprints[cat]["count"] += fp["count"]
                else:
                    all_fingerprints[cat] = fp

    return sorted(all_fingerprints.values(), key=lambda x: -x["count"])
