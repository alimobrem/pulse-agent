"""Structured JSON logging configuration."""

import logging
import os
import sys

from pythonjsonlogger.json import JsonFormatter


def configure_logging():
    """Configure structured JSON logging for production, human-readable for dev."""
    log_format = os.environ.get("PULSE_AGENT_LOG_FORMAT", "json")
    log_level = os.environ.get("PULSE_AGENT_LOG_LEVEL", "INFO").upper()

    root = logging.getLogger()
    root.setLevel(log_level)

    # Remove existing handlers
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stderr)

    if log_format == "json":
        formatter = JsonFormatter(
            fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
            rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
            static_fields={"service": "pulse-agent"},
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )

    handler.setFormatter(formatter)
    root.addHandler(handler)

    # Suppress noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("kubernetes").setLevel(logging.WARNING)
