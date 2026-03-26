"""PostToolUse hook — warn about debug/logging statements in edited files."""

# ⚠️  NOT ACTIVE — This file is NOT invoked by settings.json.
# The active version of this logic lives in post_tool_use.py.
# Edit that file instead. Changes here will have no effect.
from __future__ import annotations

import re
import subprocess
from pathlib import Path

# Debug statement patterns by file extension.
# Only patterns that are unambiguously debug-only (not standard output).
_PATTERNS: dict[str, str] = {
    "py": r"(breakpoint\(\)|pdb\.set_trace|print\(.*debug)",
    "ts": r"console\.(log|debug)\(",
    "tsx": r"console\.(log|debug)\(",
    "js": r"console\.(log|debug)\(",
    "jsx": r"console\.(log|debug)\(",
    "go": r"(log\.Print(ln|f)?)\(",  # log.Print is debug; fmt.Print is standard output
    "rs": r"(println!|dbg!)\(",
    "rb": r"(puts |binding\.pry|byebug)",
}


def run(input: dict) -> dict | None:
    file_path = input.get("tool_input", {}).get("file_path", "")
    if not file_path or not Path(file_path).exists():
        return None

    ext = Path(file_path).suffix.lstrip(".")
    pattern = _PATTERNS.get(ext)
    if not pattern:
        return None

    hits = _find_debug_statements(file_path, pattern)
    if not hits:
        return None

    basename = Path(file_path).name
    warn = f"Debug statements detected in {basename}: {'; '.join(hits[:3])}"

    user_msg = f"I noticed what looks like debug code left in {basename}. Want me to clean it up?"
    claude_context = (
        f"[debug-cleanup] {basename}: {'; '.join(hits[:3])}. "
        "Tell the user what you found (e.g. 'there's a console.log on line 5 that looks like it was "
        "used for debugging'). Ask if they want it removed — it may be intentional."
    )
    return {
        "systemMessage": user_msg,
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": claude_context,
        },
    }


def _find_debug_statements(file_path: str, pattern: str) -> list[str]:
    """Check git diff for added debug statements, fall back to file scan."""
    # Try git diff first (only newly added lines)
    try:
        result = subprocess.run(
            ["git", "diff", "-U0", file_path],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.stdout:
            added = [
                l[1:].strip()
                for l in result.stdout.splitlines()
                if l.startswith("+") and not l.startswith("+++")
            ]
            return [l for l in added if re.search(pattern, l, re.IGNORECASE)][:3]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fallback: scan the file directly (outside git repo)
    try:
        lines = Path(file_path).read_text(encoding="utf-8").splitlines()
        return [
            f"L{i + 1}: {l.strip()}"
            for i, l in enumerate(lines)
            if re.search(pattern, l, re.IGNORECASE)
        ][:3]
    except OSError:
        return []
