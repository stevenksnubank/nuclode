#!/usr/bin/env python3
"""nuclode-watch — live per-agent dashboard for Claude Code sessions.

Run in a side terminal pane. Polls activity files every 0.5s and renders
a live view of what each agent is doing.

Usage:
    python3 ~/.claude/hooks/nuclode_watch.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# ANSI colour helpers
# ---------------------------------------------------------------------------

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

# Foreground colours
FG_WHITE = "\033[97m"
FG_CYAN = "\033[96m"
FG_GREEN = "\033[92m"
FG_YELLOW = "\033[93m"
FG_RED = "\033[91m"
FG_BLUE = "\033[94m"
FG_MAGENTA = "\033[95m"
FG_GRAY = "\033[90m"

# Phase → colour mapping
_PHASE_COLORS = {
    "planning": FG_BLUE,
    "implementing": FG_GREEN,
    "reviewing": FG_CYAN,
    "security review": FG_RED,
    "writing tests": FG_MAGENTA,
    "researching": FG_YELLOW,
    "routing": FG_GRAY,
}

_AGENTS_DIR = Path.home() / ".claude" / "sessions" / "agents"
_LAST_SKILL_FILE = Path.home() / ".claude" / "sessions" / "last-skill.txt"
_HOOKS_LOG = Path.home() / ".claude" / "metrics" / "hooks.jsonl"

_STOPPED_FADE_SECS = 3  # show stopped agents briefly before removing


def _clr(text: str, color: str) -> str:
    return f"{color}{text}{RESET}"


def _bold(text: str) -> str:
    return f"{BOLD}{text}{RESET}"


def _dim(text: str) -> str:
    return f"{DIM}{text}{RESET}"


def _elapsed(start_time: float) -> str:
    secs = int(time.time() - start_time)
    if secs < 60:
        return f"{secs}s"
    return f"{secs // 60}m{secs % 60:02d}s"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def _load_agents() -> list[dict]:
    """Load all agent state files, sorted by start_time."""
    agents = []
    if not _AGENTS_DIR.exists():
        return agents

    for f in _AGENTS_DIR.glob("*.json"):
        if f.name.endswith("-activity.json"):
            continue
        try:
            state = json.loads(f.read_text(encoding="utf-8"))
            # Skip stopped agents that have faded out
            if state.get("status") == "stopped":
                stopped_at = state.get("stopped_time", 0)
                if time.time() - stopped_at > _STOPPED_FADE_SECS:
                    try:
                        f.unlink()
                    except OSError:
                        pass
                    continue

            # Load activity for this agent
            key = state.get("key", f.stem)
            activity_file = _AGENTS_DIR / f"{key}-activity.json"
            activity = {}
            if activity_file.exists():
                try:
                    activity = json.loads(activity_file.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    pass

            state["_activity"] = activity
            agents.append(state)
        except (json.JSONDecodeError, OSError):
            continue

    agents.sort(key=lambda a: a.get("start_time", 0))
    return agents


def _load_recent_events(n: int = 6) -> list[dict]:
    """Load last N hook events from hooks.jsonl."""
    if not _HOOKS_LOG.exists():
        return []
    try:
        lines = _HOOKS_LOG.read_text(encoding="utf-8").strip().splitlines()
        events = []
        for line in reversed(lines[-50:]):
            try:
                events.append(json.loads(line))
                if len(events) >= n:
                    break
            except json.JSONDecodeError:
                continue
        return events
    except OSError:
        return []


def _load_last_skill() -> str:
    try:
        if _LAST_SKILL_FILE.exists():
            return _LAST_SKILL_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    return ""


def _project_info() -> tuple[str, str]:
    """Return (project_name, branch)."""
    try:
        root = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], stderr=subprocess.DEVNULL, text=True
        ).strip()
        project = Path(root).name
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], stderr=subprocess.DEVNULL, text=True
        ).strip()
        return project, branch
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "claude", ""


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _render(project: str, branch: str) -> str:
    agents = _load_agents()
    events = _load_recent_events()
    last_skill = _load_last_skill()
    now = datetime.now().strftime("%H:%M:%S")

    lines: list[str] = []

    # Header
    header = _bold(f" nuclode-watch")
    location = f"{_clr(project, FG_CYAN)}"
    if branch:
        location += f" {_dim('|')} {_clr(branch, FG_YELLOW)}"
    lines.append(f"{header}  {location}  {_dim(now)}")
    lines.append(_dim("─" * 60))

    # Agents section
    active = [a for a in agents if a.get("status") == "active"]
    stopped = [a for a in agents if a.get("status") == "stopped"]

    if not active and not stopped:
        lines.append(_dim("  No active agents"))
    else:
        count_label = f"{len(active)} active" if active else "idle"
        lines.append(_bold(f" AGENTS  ") + _dim(f"({count_label})"))

        all_shown = active + stopped
        for i, agent in enumerate(all_shown):
            is_last = i == len(all_shown) - 1
            prefix = "  └─" if is_last else "  ├─"

            name = agent.get("name", "unknown")
            phase = agent.get("phase", "")
            status = agent.get("status", "active")
            start_time = agent.get("start_time", time.time())
            elapsed = _elapsed(start_time)

            phase_color = _PHASE_COLORS.get(phase, FG_WHITE)

            if status == "stopped":
                row = f"{_dim(prefix)} {_dim(name):<20} {_dim('done'):<18} {_dim(elapsed)}"
            else:
                activity = agent.get("_activity", {})
                tool = activity.get("tool", "")
                summary = activity.get("summary", "")
                skill = activity.get("skill", "")

                tool_str = ""
                if skill:
                    tool_str = _clr(f"/{skill}", FG_MAGENTA)
                elif tool and summary:
                    tool_str = _dim(f"{tool}: {summary[:28]}")
                elif tool:
                    tool_str = _dim(tool)

                phase_str = _clr(f"{phase:<16}", phase_color) if phase else " " * 16
                row = f"{prefix} {_bold(name):<20} {phase_str}  {tool_str:<35} {_dim(elapsed)}"

            lines.append(row)

    lines.append("")

    # Last skill
    if last_skill:
        lines.append(_bold(" LAST SKILL") + f"  {_clr('/' + last_skill, FG_MAGENTA)}")
        lines.append("")

    # Recent hook events
    if events:
        lines.append(_bold(" RECENT EVENTS"))
        for event in events:
            ts = event.get("timestamp", "")
            hook = event.get("hook", "")
            ev_type = event.get("event", "")
            blocked = event.get("blocked", False)

            try:
                t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                ts_str = t.strftime("%H:%M:%S")
            except (ValueError, AttributeError):
                ts_str = ts[:8] if ts else "?"

            if blocked:
                icon = _clr("⊘", FG_RED)
                label = _clr(f"{hook} blocked", FG_RED)
            elif ev_type == "pass":
                icon = _dim("·")
                label = _dim(f"{hook}")
            else:
                icon = _clr("!", FG_YELLOW)
                label = _clr(f"{hook} {ev_type}", FG_YELLOW)

            lines.append(f"  {icon} {_dim(ts_str)}  {label}")
    else:
        lines.append(_dim("  No recent hook events"))

    lines.append(_dim("─" * 60))
    lines.append(_dim("  Ctrl+C to exit"))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def main() -> None:
    project, branch = _project_info()

    # Hide cursor
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()

    try:
        while True:
            output = _render(project, branch)

            # Count lines so we can move cursor back up
            line_count = output.count("\n") + 1

            # Move to top of our render area (or clear screen on first run)
            sys.stdout.write("\033[2J\033[H")
            sys.stdout.write(output + "\n")
            sys.stdout.flush()

            time.sleep(0.5)

    except KeyboardInterrupt:
        pass
    finally:
        # Restore cursor, clear screen
        sys.stdout.write("\033[?25h")
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
