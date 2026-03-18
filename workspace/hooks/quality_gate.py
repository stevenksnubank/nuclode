"""PostToolUse async hook — run language-appropriate linters after edits. Strict only."""
from __future__ import annotations

import subprocess
from pathlib import Path


def run(input: dict) -> dict | None:
    file_path = input.get("tool_input", {}).get("file_path", "")
    if not file_path or not Path(file_path).exists():
        return None

    ext = Path(file_path).suffix.lstrip(".")
    issues = _check(ext, file_path)

    if not issues:
        return None

    return {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": f"[quality-gate] {issues}",
        }
    }


def _check(ext: str, file_path: str) -> str:
    """Run linter and return issues string, or empty string."""
    checkers: dict[str, list[list[str]]] = {
        "py": [["ruff", "check", file_path]],
        "ts": [],  # handled below
        "tsx": [],
        "go": [["go", "vet", f"./{Path(file_path).parent}/..."]],
    }

    if ext in ("ts", "tsx") and Path("tsconfig.json").exists():
        return _run_cmd(
            ["npx", "--no-install", "tsc", "--noEmit", "--pretty", "false"],
            prefix="tsc",
            filter_path=file_path,
        )

    cmds = checkers.get(ext, [])
    for cmd in cmds:
        result = _run_cmd(cmd, prefix=cmd[0])
        if result:
            return result

    return ""


def _run_cmd(cmd: list[str], prefix: str, max_lines: int = 5, filter_path: str = "") -> str:
    """Run a command and return formatted output."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        output = result.stdout.strip() or result.stderr.strip()
        if output:
            lines = output.splitlines()
            if filter_path:
                lines = [l for l in lines if filter_path in l]
            lines = lines[:max_lines]
            if lines:
                return f"{prefix}: {'; '.join(lines)}"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return ""
