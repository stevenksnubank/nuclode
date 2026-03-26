"""Stop hook (async) — auto-sync beads to git after each response."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


# ── Two beads databases ───────────────────────────────────────────────────────
# This hook manages the TASK TRACKING database only:
#   <project>/.beads/beads.db  — agent task tracking (bd/bv workflow), synced to git
#
# A separate ANALYSIS database exists at:
#   <nuclode>/.nuclode-data/projects/<name>/.beads/beads.db
#   — written by the knowledge engine pipeline (reduce_to_beads), intentionally local-only
#
# This hook will NOT fire for the analysis database. That is by design.
# ─────────────────────────────────────────────────────────────────────────────


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
            capture_output=True,
            text=True,
            timeout=5,
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
