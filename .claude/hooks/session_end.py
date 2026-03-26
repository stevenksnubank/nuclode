"""Stop hook — persist session metadata for next session's context injection."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def run(input: dict) -> dict | None:
    sessions_dir = Path.home() / ".claude" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    session_id = input.get("session_id", "")
    transcript = input.get("transcript_path", "")
    last_msg = input.get("last_assistant_message", "")

    cwd = os.getcwd()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Git branch
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        branch = result.stdout.strip() if result.returncode == 0 else "none"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        branch = "none"

    # Brief summary: first non-empty line, stripped of markdown, max 200 chars
    summary = ""
    if last_msg:
        for line in last_msg.splitlines():
            cleaned = line.strip().lstrip("#").strip().replace("*", "").replace("`", "")
            if cleaned:
                summary = cleaned[:200]
                break

    # Beads dirty count
    beads_dirty = 0
    if Path(".beads").is_dir():
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", ".beads/"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            beads_dirty = len([l for l in result.stdout.strip().splitlines() if l.strip()])
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    # Capture current beads task ID for session-to-task binding
    beads_task_id = ""
    if Path(".beads").is_dir():
        try:
            result = subprocess.run(
                ["bd", "current"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                beads_task_id = result.stdout.strip().splitlines()[0].split()[0]
        except (FileNotFoundError, subprocess.TimeoutExpired, IndexError):
            pass

    # Transcript size as session-size indicator (not a cost proxy — actual cost
    # depends on token counts, model pricing, and caching)
    transcript_bytes = 0
    if transcript and Path(transcript).exists():
        try:
            transcript_bytes = Path(transcript).stat().st_size
        except OSError:
            pass

    session_data = {
        "session_id": session_id,
        "cwd": cwd,
        "branch": branch,
        "timestamp": timestamp,
        "summary": summary,
        "transcript_path": transcript,
        "beads_dirty": beads_dirty,
        "beads_task_id": beads_task_id,
        "transcript_bytes": transcript_bytes,
    }

    # Clear live activity so watcher shows idle state
    _clear_activity()

    # Atomic write: write to temp, then rename (POSIX atomic)
    _atomic_write(sessions_dir / "latest.json", json.dumps(session_data, indent=2))

    # Append to history (keep last 50)
    history = sessions_dir / "history.jsonl"
    with history.open("a", encoding="utf-8") as f:
        f.write(json.dumps(session_data) + "\n")

    _trim_file(history, max_lines=50)

    return None  # Stop hooks don't output to Claude


def _atomic_write(path: Path, content: str) -> None:
    """Write content to path atomically via temp file + rename."""
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        os.write(fd, content.encode("utf-8"))
        os.close(fd)
        os.rename(tmp, str(path))
    except Exception:
        os.close(fd) if not os.get_inheritable(fd) else None
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _clear_activity() -> None:
    """Clear per-agent activity files so watcher shows idle state."""
    agents_dir = Path.home() / ".claude" / "sessions" / "agents"
    last_skill = Path.home() / ".claude" / "sessions" / "last-skill.txt"
    try:
        if agents_dir.exists():
            for f in agents_dir.glob("*.json"):
                try:
                    f.unlink()
                except OSError:
                    pass
        if last_skill.exists():
            last_skill.unlink()
    except OSError:
        pass


def _trim_file(path: Path, max_lines: int) -> None:
    """Keep only the last N lines of a file. Uses atomic write."""
    try:
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        if len(lines) > max_lines:
            _atomic_write(path, "\n".join(lines[-max_lines:]) + "\n")
    except OSError:
        pass
