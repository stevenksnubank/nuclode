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

    auth_warnings: list[str] = []
    _check_auth_preflight(parts, auth_warnings)
    _detect_project(parts, project_dir)
    _check_beads(parts, project_dir)
    _check_analysis_freshness(parts, project_dir)
    has_previous = _load_previous_session(parts, str(project_dir))
    _write_session_bead(project_dir, auth_warnings)

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


def _write_session_bead(project_dir: Path, auth_warnings: list[str]) -> None:
    """Write an ephemeral session bead capturing preflight state.

    Non-blocking — failures are silently ignored.
    Only writes if bd CLI is available and project has a beads db.
    """
    from datetime import datetime

    beads_dir = project_dir / ".beads"
    if not (beads_dir / "beads.jsonl").exists() and not (beads_dir / "issues.jsonl").exists():
        return

    try:
        subprocess.run(["bd", "--version"], capture_output=True, timeout=3)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return

    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=3,
            cwd=str(project_dir),
        ).strip()
    except Exception:
        branch = "unknown"

    try:
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=3,
            cwd=str(project_dir),
        )
        uncommitted = len([l for l in status_result.stdout.splitlines() if l.strip()])
        git_status = f"clean" if uncommitted == 0 else f"{uncommitted} uncommitted"
    except Exception:
        git_status = "unknown"

    # AWS status
    try:
        aws_result = subprocess.run(
            ["aws", "sts", "get-caller-identity"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        aws_status = "✓" if aws_result.returncode == 0 else "✗ invalid/expired"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        aws_status = "n/a"

    # SSH status
    try:
        agent_result = subprocess.run(
            ["ssh-add", "-l"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        ssh_status = "✓" if agent_result.returncode == 0 else "✗ no keys loaded"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        ssh_status = "n/a"

    # MCP tool availability (check via env or known config)
    mcp_glean = "✓" if os.environ.get("GLEAN_API_TOKEN") else "unknown"

    auth_note = (" WARNINGS: " + "; ".join(auth_warnings)) if auth_warnings else ""

    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    body = (
        f"## Preflight{auth_note}\n"
        f"- git: {git_status}, branch={branch}\n"
        f"- aws: {aws_status}\n"
        f"- ssh: {ssh_status}\n"
        f"- mcp/glean: {mcp_glean}\n"
        f"- bd: ✓\n"
        f"- uncommitted: {uncommitted if 'uncommitted' in locals() else 'unknown'}"
    )

    try:
        subprocess.run(
            [
                "bd",
                "create",
                f"Session: {date_str} {branch}",
                "--type",
                "event",
                "--event-category",
                "session.start",
                "--event-actor",
                "claude-code",
                "-d",
                body,
                "-l",
                "session",
                "--ephemeral",
                "--silent",
            ],
            capture_output=True,
            timeout=5,
            cwd=str(project_dir),
        )
    except Exception:
        pass  # Non-blocking — session continues regardless


def _check_auth_preflight(parts: list[str], auth_warnings: list[str] | None = None) -> None:
    """Check critical auth dependencies at session start. Non-blocking — warns only."""
    profile = os.environ.get("NUCLODE_HOOK_PROFILE", "standard")
    if profile == "minimal":
        return

    warnings: list[str] = []
    if auth_warnings is None:
        auth_warnings = warnings

    # AWS credentials
    try:
        result = subprocess.run(
            ["aws", "sts", "get-caller-identity"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            warnings.append(
                "AWS credentials invalid or expired (aws sts get-caller-identity failed)"
            )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass  # AWS CLI not installed — not a warning

    # SSH key for git — check agent, open new Terminal to load key if needed
    try:
        agent_result = subprocess.run(
            ["ssh-add", "-l"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if agent_result.returncode != 0:
            # Open a new Terminal window for interactive ssh-add (non-blocking)
            subprocess.Popen(
                [
                    "osascript",
                    "-e",
                    'tell application "Terminal" to do script "ssh-add; echo \\"\\nDone — you can close this window\\""',
                ]
            )
            warnings.append(
                "SSH keys not loaded — enter passphrase in the Terminal window that just opened"
            )
        else:
            # Keys loaded — verify GitHub accepts them
            ssh_host = "git@" + "github.com"
            result = subprocess.run(
                ["ssh", "-T", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=3", ssh_host],
                capture_output=True,
                text=True,
                timeout=6,
            )
            # GitHub returns exit code 1 on success ("Hi username!"), 255 on auth failure
            if result.returncode == 255 or "Permission denied" in result.stderr:
                warnings.append("SSH key not accepted by GitHub — git push may fail")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    if warnings:
        auth_warnings.extend(warnings)
        parts.append(
            "⚠️ Auth issues: " + "; ".join(warnings) + ". Fix before starting auth-dependent work."
        )


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
