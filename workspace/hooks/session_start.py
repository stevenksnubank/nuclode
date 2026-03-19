"""SessionStart hook — project detection, beads context, previous session loading."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


def run(input: dict) -> dict | None:
    source = input.get("source", "startup")
    cwd = input.get("cwd", ".")

    # Only run on fresh session starts
    if source != "startup":
        return None

    project_dir = Path(cwd).resolve()
    parts: list[str] = []

    _detect_project(parts, project_dir)
    _check_beads(parts, project_dir)
    _check_analysis_freshness(parts, project_dir)
    has_previous = _load_previous_session(parts, str(project_dir))

    if not parts:
        return None

    context = "[nuclode] " + " ".join(parts)

    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        },
        # Trigger nuclode-guide to show a proactive welcome before the user types anything
        "prompt": "nuclode:startup",
    }


def _detect_project(parts: list[str], project_dir: Path) -> None:
    """Detect project type from lockfiles and config files."""
    if (project_dir / "pyproject.toml").exists() or (project_dir / "setup.py").exists():
        parts.append("Python project.")

    if (project_dir / "package.json").exists():
        pkg_mgr = "npm"
        if (project_dir / "pnpm-lock.yaml").exists():
            pkg_mgr = "pnpm"
        elif (project_dir / "yarn.lock").exists():
            pkg_mgr = "yarn"
        elif (project_dir / "bun.lockb").exists():
            pkg_mgr = "bun"
        parts.append(f"Node project ({pkg_mgr}).")

    if (project_dir / "go.mod").exists():
        parts.append("Go project.")
    if (project_dir / "deps.edn").exists() or (project_dir / "project.clj").exists():
        parts.append("Clojure project.")
    if (project_dir / "Cargo.toml").exists():
        parts.append("Rust project.")


def _check_beads(parts: list[str], project_dir: Path) -> None:
    """Check beads availability and ready task count."""
    beads_dir = project_dir / ".beads"
    if not (beads_dir / "beads.jsonl").exists() and not (beads_dir / "issues.jsonl").exists():
        return

    try:
        result = subprocess.run(
            ["bd", "ready"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(project_dir),
        )
        if result.returncode != 0:
            return
        count = len([l for l in result.stdout.strip().splitlines() if l.strip()])
        parts.append(f"Beads active: {count} tasks ready.")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Auto-inject currently claimed task details
    try:
        current_result = subprocess.run(
            ["bd", "current"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(project_dir),
        )
        if current_result.returncode == 0 and current_result.stdout.strip():
            task_id = current_result.stdout.strip().splitlines()[0].split()[0]
            show_result = subprocess.run(
                ["bd", "show", task_id],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=str(project_dir),
            )
            if show_result.returncode == 0 and show_result.stdout.strip():
                task_detail = show_result.stdout.strip()[:500]
                parts.append(f"Current task: {task_detail}")
    except (FileNotFoundError, subprocess.TimeoutExpired, IndexError):
        pass


def _check_analysis_freshness(parts: list[str], project_dir: Path) -> None:
    """Check if codebase analysis is current."""
    meta_path = project_dir / ".beads" / "analysis_metadata.json"
    if not meta_path.exists():
        return

    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        last_sha = meta.get("last_analyzed_sha", "")
        if not last_sha:
            return

        result = subprocess.run(
            ["git", "diff", "--name-only", f"{last_sha}..HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(project_dir),
        )
        changed = len([l for l in result.stdout.strip().splitlines() if l.strip()])
        if changed > 0:
            parts.append(f"Analysis stale: {changed} files changed since last run.")
        else:
            parts.append("Analysis is current.")
    except (subprocess.TimeoutExpired, OSError, json.JSONDecodeError):
        pass


def _load_previous_session(parts: list[str], current_cwd: str) -> bool:
    """Load previous session context if available. Returns True if a relevant session was found."""
    latest = Path.home() / ".claude" / "sessions" / "latest.json"
    if not latest.exists():
        return False

    try:
        session = json.loads(latest.read_text(encoding="utf-8"))
        prev_cwd = session.get("cwd", "")
        prev_branch = session.get("branch", "")
        prev_ts = session.get("timestamp", "")
        prev_summary = session.get("summary", "")

        # Only inject if same project directory
        if prev_cwd == current_cwd and prev_summary:
            prev_task_id = session.get("beads_task_id", "")
            task_context = f", task: {prev_task_id}" if prev_task_id else ""
            parts.append(
                f"Previous session ({prev_ts}, branch: {prev_branch}{task_context}): {prev_summary}"
            )
            return True
    except (json.JSONDecodeError, OSError):
        pass
    return False
