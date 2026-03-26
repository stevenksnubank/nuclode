"""Shared telemetry module — logs hook execution events to ~/.claude/metrics/hooks.jsonl.

Every hook can import and call log_event() to record what happened.
This provides the local observability layer. A separate exporter can
push these events to central telemetry (Datadog, HTTP endpoint, etc.).
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path


def log_event(
    hook_name: str,
    event_type: str,
    details: dict | None = None,
    blocked: bool = False,
    duration_ms: float | None = None,
) -> None:
    """Append a structured event to the hooks telemetry log.

    Args:
        hook_name: e.g. "secrets_scan", "sast_gate", "session_start"
        event_type: e.g. "block", "warn", "pass", "error", "skip"
        details: arbitrary dict of event-specific data (findings, file paths, etc.)
        blocked: True if this hook blocked an action
        duration_ms: execution time in milliseconds
    """
    metrics_dir = Path.home() / ".claude" / "metrics"
    try:
        metrics_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return

    event = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "hook": hook_name,
        "event": event_type,
        "blocked": blocked,
        "cwd": os.getcwd(),
        "details": details or {},
    }
    if duration_ms is not None:
        event["duration_ms"] = round(duration_ms, 1)

    try:
        log_path = metrics_dir / "hooks.jsonl"
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

        # Trim to last 2000 entries
        _trim_log(log_path, max_lines=2000)
    except OSError:
        pass


def _trim_log(path: Path, max_lines: int) -> None:
    """Keep only the last N lines."""
    try:
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        if len(lines) > max_lines:
            path.write_text("\n".join(lines[-max_lines:]) + "\n", encoding="utf-8")
    except OSError:
        pass


class Timer:
    """Context manager for timing hook execution."""

    def __init__(self):
        self.start = 0.0
        self.duration_ms = 0.0

    def __enter__(self):
        self.start = time.monotonic()
        return self

    def __exit__(self, *args):
        self.duration_ms = (time.monotonic() - self.start) * 1000
