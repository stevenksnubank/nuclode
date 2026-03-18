"""Stop hook (async) — auto-sync beads to git after each response."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def run(input: dict) -> dict | None:
    # Only sync if beads data exists in this project
    beads_dir = Path(".beads")
    if not beads_dir.is_dir():
        return None
    if not (beads_dir / "beads.jsonl").exists() and not (beads_dir / "issues.jsonl").exists():
        return None

    # Check bd is installed before attempting sync
    if not shutil.which("bd"):
        return None

    # Check for uncommitted beads changes (more reliable than bd status)
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", ".beads/"],
            capture_output=True, text=True, timeout=5,
        )
        if not result.stdout.strip():
            return None  # Nothing to sync
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None

    # Sync (separate try/except for clear diagnostics)
    try:
        subprocess.run(["bd", "sync"], capture_output=True, timeout=10)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return None  # Stop hooks don't output to Claude
