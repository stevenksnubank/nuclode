"""Stop hook (async) — append session metrics to ~/.claude/metrics/costs.jsonl.

Records session metadata and transcript size as a session-size indicator.
Actual cost depends on token counts, model pricing, and caching — full
token-level tracking is deferred to a future enhancement.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def run(input: dict) -> dict | None:
    metrics_dir = Path.home() / ".claude" / "metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)

    session_id = input.get("session_id", "")
    transcript = input.get("transcript_path", "")
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cwd = os.getcwd()

    transcript_bytes = 0
    if transcript and Path(transcript).exists():
        try:
            transcript_bytes = Path(transcript).stat().st_size
        except OSError:
            pass

    entry = {
        "session_id": session_id,
        "timestamp": timestamp,
        "cwd": cwd,
        "transcript_bytes": transcript_bytes,
    }

    costs_file = metrics_dir / "costs.jsonl"
    with costs_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    _trim_file(costs_file, max_lines=500)

    return None  # Stop hooks don't output to Claude


def _trim_file(path: Path, max_lines: int) -> None:
    """Keep only the last N lines of a file. Uses atomic write."""
    try:
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        if len(lines) > max_lines:
            content = "\n".join(lines[-max_lines:]) + "\n"
            fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
            try:
                os.write(fd, content.encode("utf-8"))
                os.close(fd)
                os.rename(tmp, str(path))
            except Exception:
                try:
                    os.close(fd)
                except OSError:
                    pass
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
    except OSError:
        pass
