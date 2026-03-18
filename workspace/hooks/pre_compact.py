"""PreCompact hook — save session checkpoint with recently-edited files and active task."""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def run(input: dict) -> dict | None:
    sessions_dir = Path.home() / ".claude" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    session_id = input.get("session_id", "")
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cwd = os.getcwd()

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        branch = result.stdout.strip() if result.returncode == 0 else "none"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        branch = "none"

    # Capture recently modified files (differentiates this from session_end)
    modified_files: list[str] = []
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True, text=True, timeout=5,
        )
        modified_files = [l.strip() for l in result.stdout.splitlines() if l.strip()][:20]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Active beads task (if any)
    active_task = ""
    if Path(".beads").is_dir():
        try:
            result = subprocess.run(
                ["bd", "current"], capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                active_task = result.stdout.strip().splitlines()[0][:200]
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    checkpoint = {
        "session_id": session_id,
        "cwd": cwd,
        "branch": branch,
        "timestamp": timestamp,
        "event": "pre-compact",
        "modified_files": modified_files,
        "active_task": active_task,
    }

    (sessions_dir / "pre-compact-latest.json").write_text(
        json.dumps(checkpoint, indent=2), encoding="utf-8"
    )

    return None  # PreCompact hooks don't output to Claude
