"""Stop hook — warn about uncommitted files at session end."""
from __future__ import annotations

import subprocess


def run(input: dict) -> dict | None:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None

        lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
        if not lines:
            return None

        files = [l[2:].strip() for l in lines][:10]
        summary = ", ".join(files)
        if len(lines) > 10:
            summary += f" ... and {len(lines) - 10} more"

        return {
            "systemMessage": (
                f"[uncommitted-guard] Warning: {len(lines)} uncommitted file(s): {summary}. "
                "Consider committing or stashing before ending the session."
            ),
        }
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
