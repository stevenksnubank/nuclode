#!/usr/bin/env python3
"""Consolidated PostToolUse hook — single process for all post-tool checks.

Replaces separate spawns of post_edit_format, console_warn, sast_scan.
(quality_gate remains separate because it runs async with a 30s timeout.)

Checks (in order):
  1. Auto-format — format edited files by language (silent)
  2. SAST scan — warn about security anti-patterns (advisory)
  3. Console warn — flag debug/logging statements (advisory)

Env vars:
    NUCLODE_HOOK_PROFILE    - minimal|standard|strict (default: standard)
    NUCLODE_DISABLED_HOOKS  - comma-separated hook IDs to disable
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

HOOK_DIR = Path(__file__).parent


def _load_profile():
    profile = os.environ.get("NUCLODE_HOOK_PROFILE", "standard")
    disabled = {
        h.strip()
        for h in os.environ.get("NUCLODE_DISABLED_HOOKS", "").split(",")
        if h.strip()
    }
    return profile, disabled


def _is_enabled(hook_id: str, profile: str, disabled: set, required_profiles: set) -> bool:
    if hook_id in disabled:
        return False
    if profile not in required_profiles:
        return False
    return True


def _log_event(hook_name: str, event_type: str, details: dict | None = None):
    try:
        from hook_telemetry import log_event
        log_event(hook_name, event_type, details)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Check 1: Auto-format (silent)
# ---------------------------------------------------------------------------

def _auto_format(file_path: str) -> None:
    """Run the appropriate formatter for the file extension."""
    path = Path(file_path)
    if not path.exists():
        return

    ext = path.suffix.lstrip(".")

    formatters: dict[str, list[list[str]]] = {
        "py": [
            ["ruff", "format", file_path],
            ["black", "-q", file_path],
        ],
        "go": [["gofmt", "-w", file_path]],
        "rs": [["rustfmt", file_path]],
        "clj": [["cljfmt", "fix", file_path]],
        "cljc": [["cljfmt", "fix", file_path]],
        "cljs": [["cljfmt", "fix", file_path]],
        "edn": [["cljfmt", "fix", file_path]],
    }

    if ext in ("ts", "tsx", "js", "jsx"):
        js_cmd = _find_js_formatter(file_path)
        if js_cmd:
            formatters[ext] = [js_cmd]
        else:
            return

    candidates = formatters.get(ext, [])
    for cmd in candidates:
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=10)
            if result.returncode == 0:
                return
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue


def _find_js_formatter(file_path: str) -> list[str] | None:
    search_dir = Path(file_path).resolve().parent
    for d in [search_dir, *search_dir.parents]:
        if (d / "biome.json").exists() or (d / "biome.jsonc").exists():
            return ["npx", "--no-install", "@biomejs/biome", "format", "--write", file_path]
        if any((d / f).exists() for f in [".prettierrc", ".prettierrc.json", "prettier.config.js"]):
            return ["npx", "--no-install", "prettier", "--write", file_path]
        if (d / ".git").exists():
            break
    return None


# ---------------------------------------------------------------------------
# Check 2: SAST scan (advisory)
# ---------------------------------------------------------------------------

def _check_sast_scan(file_path: str) -> dict | None:
    """Scan edited file for security anti-patterns. Advisory only."""
    path = Path(file_path)
    if not path.exists():
        return None

    ext = path.suffix.lstrip(".")

    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "sast_patterns", str(HOOK_DIR / "sast_patterns.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        patterns = mod.PATTERNS.get(ext)
    except Exception:
        return None

    if not patterns:
        return None

    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return None

    findings: list[str] = []
    for name, pattern, severity, suggestion in patterns:
        matches = list(re.finditer(pattern, content))
        if matches:
            line_num = content[:matches[0].start()].count("\n") + 1
            findings.append(f"{severity}: {name} at L{line_num} — {suggestion}")

    if not findings:
        return None

    _log_event("sast_scan", "warn", {"file": path.name, "findings_count": len(findings)})

    details = "; ".join(findings[:3])
    return {
        "systemMessage": f"Heads up — I spotted a security concern in {path.name}. Let me explain what I found.",
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": (
                f"[security-check] {path.name}: {details}. "
                "IMPORTANT: Do NOT silently fix. Explain what was found, why it matters, "
                "propose the fix, get user agreement, then show what changed."
            ),
        }
    }


# ---------------------------------------------------------------------------
# Check 3: Console/debug warn (advisory)
# ---------------------------------------------------------------------------

_DEBUG_PATTERNS: dict[str, str] = {
    "py": r"(breakpoint\(\)|pdb\.set_trace|print\(.*debug)",
    "ts": r"console\.(log|debug)\(",
    "tsx": r"console\.(log|debug)\(",
    "js": r"console\.(log|debug)\(",
    "jsx": r"console\.(log|debug)\(",
    "go": r"(log\.Print(ln|f)?)\(",
    "rs": r"(println!|dbg!)\(",
    "rb": r"(puts |binding\.pry|byebug)",
}


def _check_console_warn(file_path: str) -> dict | None:
    """Warn about debug/logging statements in edited files."""
    path = Path(file_path)
    if not path.exists():
        return None

    ext = path.suffix.lstrip(".")
    pattern = _DEBUG_PATTERNS.get(ext)
    if not pattern:
        return None

    # Check git diff for newly added lines (prefer this over full scan)
    hits: list[str] = []
    try:
        result = subprocess.run(
            ["git", "diff", "-U0", file_path],
            capture_output=True, text=True, timeout=5,
        )
        if result.stdout:
            added = [
                l[1:].strip()
                for l in result.stdout.splitlines()
                if l.startswith("+") and not l.startswith("+++")
            ]
            hits = [l for l in added if re.search(pattern, l, re.IGNORECASE)][:3]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    if not hits:
        # Fallback: scan file directly
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
            hits = [
                f"L{i+1}: {l.strip()}"
                for i, l in enumerate(lines)
                if re.search(pattern, l, re.IGNORECASE)
            ][:3]
        except OSError:
            return None

    if not hits:
        return None

    basename = path.name
    return {
        "systemMessage": f"I noticed what looks like debug code left in {basename}. Want me to clean it up?",
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": (
                f"[debug-cleanup] {basename}: {'; '.join(hits[:3])}. "
                "Tell the user what you found (e.g. 'there's a console.log on line 5 that looks like it was "
                "used for debugging'). Ask if they want it removed — it may be intentional."
            ),
        }
    }


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

def main() -> None:
    profile, disabled = _load_profile()

    input_text = sys.stdin.read()
    try:
        input_data = json.loads(input_text) if input_text.strip() else {}
    except json.JSONDecodeError:
        input_data = {}

    file_path = input_data.get("tool_input", {}).get("file_path", "")
    if not file_path:
        return

    # Collect all advisory results — we'll return the most important one.
    # (Claude Code only processes one hook result per invocation.)
    advisories: list[dict] = []

    # 1. Auto-format (silent, always runs for standard+strict)
    if _is_enabled("post:edit:format", profile, disabled, {"standard", "strict"}):
        _auto_format(file_path)

    # 2. SAST scan (advisory, standard+strict)
    if _is_enabled("post:sast-scan", profile, disabled, {"standard", "strict"}):
        result = _check_sast_scan(file_path)
        if result:
            advisories.append(result)

    # 3. Console/debug warn (advisory, standard+strict)
    if _is_enabled("post:console-warn", profile, disabled, {"standard", "strict"}):
        result = _check_console_warn(file_path)
        if result:
            advisories.append(result)

    # Return the highest-priority advisory (SAST > debug warnings)
    if advisories:
        json.dump(advisories[0], sys.stdout)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"post_tool_use error: {e}", file=sys.stderr)
        sys.exit(0)
