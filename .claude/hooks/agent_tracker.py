"""SubagentStart/SubagentStop hook — track which agent is active for status line."""
from __future__ import annotations

import os
from pathlib import Path

# Map agent names to user-friendly phase labels
_PHASE_LABELS = {
    "code-planner": "planning",
    "code-implementer": "implementing",
    "code-reviewer": "reviewing",
    "active-defender": "security review",
    "test-writer": "writing tests",
    "nuclode-guide": "",  # guide is the default, don't show
}


def run(input: dict) -> dict | None:
    sessions_dir = Path.home() / ".claude" / "sessions"
    try:
        sessions_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None

    phase_file = sessions_dir / "active-phase"

    # Determine if this is a start or stop event
    # SubagentStart sends agent info, SubagentStop clears it
    agent_name = input.get("agent_name", "") or input.get("agent", "")
    event_type = input.get("event_type", "")

    if event_type == "stop" or not agent_name:
        # Agent finished — clear the phase
        try:
            phase_file.write_text("", encoding="utf-8")
        except OSError:
            pass
        return None

    # Agent started — write the friendly phase label
    label = _PHASE_LABELS.get(agent_name, agent_name)
    if label:
        try:
            phase_file.write_text(label, encoding="utf-8")
        except OSError:
            pass

    return None
