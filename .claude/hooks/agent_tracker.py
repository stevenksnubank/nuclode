"""SubagentStart/SubagentStop hook — per-agent state tracking for live dashboard."""

from __future__ import annotations

import json
import time
from pathlib import Path

_PHASE_LABELS = {
    "code-planner": "planning",
    "code-implementer": "implementing",
    "code-reviewer": "reviewing",
    "active-defender": "security review",
    "test-writer": "writing tests",
    "research-analyst": "researching",
    "nuclode-guide": "routing",
}

_AGENTS_DIR = Path.home() / ".claude" / "sessions" / "agents"
_PHASE_FILE = Path.home() / ".claude" / "sessions" / "active-phase"  # keep for statusline compat


def run(input: dict) -> dict | None:
    try:
        _AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None

    session_id = input.get("session_id", "")
    agent_name = input.get("agent_name", "") or input.get("agent", "")
    event_type = input.get("event_type", "")

    # Use session_id as key; fall back to agent_name if missing
    key = session_id or agent_name or "unknown"
    agent_file = _AGENTS_DIR / f"{key}.json"
    activity_file = _AGENTS_DIR / f"{key}-activity.json"

    if event_type == "stop" or (not agent_name and not session_id):
        _handle_stop(agent_file, activity_file)
        _refresh_phase_file()
        return None

    _handle_start(agent_file, agent_name, key)
    _refresh_phase_file()
    return None


def _handle_start(agent_file: Path, agent_name: str, key: str) -> None:
    label = _PHASE_LABELS.get(agent_name, agent_name)
    state = {
        "key": key,
        "name": agent_name,
        "phase": label,
        "status": "active",
        "start_time": time.time(),
        "stopped_time": None,
    }
    try:
        agent_file.write_text(json.dumps(state), encoding="utf-8")
    except OSError:
        pass


def _handle_stop(agent_file: Path, activity_file: Path) -> None:
    # Mark stopped — watcher will fade it out, then clean up
    try:
        if agent_file.exists():
            state = json.loads(agent_file.read_text(encoding="utf-8"))
            state["status"] = "stopped"
            state["stopped_time"] = time.time()
            agent_file.write_text(json.dumps(state), encoding="utf-8")
        # Clear activity on stop
        if activity_file.exists():
            activity_file.unlink()
    except (OSError, json.JSONDecodeError):
        pass


def _refresh_phase_file() -> None:
    """Keep legacy active-phase file in sync for statusline."""
    try:
        active = []
        for f in _AGENTS_DIR.glob("*.json"):
            if f.name.endswith("-activity.json"):
                continue
            try:
                state = json.loads(f.read_text(encoding="utf-8"))
                if state.get("status") == "active" and state.get("phase"):
                    active.append(state["phase"])
            except (OSError, json.JSONDecodeError):
                pass
        _PHASE_FILE.write_text(", ".join(active) if active else "", encoding="utf-8")
    except OSError:
        pass
