"""PreToolUse hook — track edit count and suggest compaction at intervals. Strict only."""
from __future__ import annotations

import os
from pathlib import Path


def run(input: dict) -> dict | None:
    threshold = int(os.environ.get("NUCLODE_COMPACT_THRESHOLD", "30"))

    # Use session_id from input for reliable scoping (not PPID which is unstable)
    session_id = input.get("session_id", "")
    if not session_id:
        # Fallback: use parent PID if no session_id available
        session_id = str(os.getppid())

    # Store counter under ~/.claude/sessions/ (not /tmp — avoids predictable paths,
    # permission issues, and stale file accumulation)
    counter_dir = Path.home() / ".claude" / "sessions"
    counter_dir.mkdir(parents=True, exist_ok=True)
    counter_file = counter_dir / f"edit-count-{session_id}"

    # Increment counter
    count = 0
    if counter_file.exists():
        try:
            count = int(counter_file.read_text(encoding="utf-8").strip())
        except (ValueError, OSError):
            count = 0

    count += 1
    counter_file.write_text(str(count), encoding="utf-8")

    # Suggest at threshold intervals
    if count > 0 and count % threshold == 0:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": (
                    f"[suggest-compact] {count} edits in this session. "
                    "Consider running /compact to free context window space."
                ),
            }
        }

    return None
