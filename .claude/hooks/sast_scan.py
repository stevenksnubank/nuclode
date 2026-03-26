"""PostToolUse hook — scan edited files for security anti-patterns. Advisory.

Shows warnings to the user via systemMessage for any findings.
HIGH severity findings are also blocked at commit time by sast_gate.py.
"""
from __future__ import annotations

import re
from pathlib import Path

# Import shared patterns (co-located in hooks/)
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("sast_patterns", str(Path(__file__).parent / "sast_patterns.py"))
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
_PATTERNS = _mod.PATTERNS


def run(input: dict) -> dict | None:
    file_path = input.get("tool_input", {}).get("file_path", "")
    if not file_path or not Path(file_path).exists():
        return None

    ext = Path(file_path).suffix.lstrip(".")
    patterns = _PATTERNS.get(ext)
    if not patterns:
        return None

    findings = _scan_file(file_path, patterns)
    try:
        from hook_telemetry import log_event
        if findings:
            log_event("sast_scan", "warn", {"file": Path(file_path).name, "findings_count": len(findings)})
    except Exception:
        pass

    if not findings:
        return None

    details = "; ".join(findings[:3])
    # User sees a friendly heads-up; Claude gets full details + instruction to explain, not silently fix
    user_msg = f"Heads up — I spotted a security concern in {Path(file_path).name}. Let me explain what I found."
    claude_context = (
        f"[security-check] {Path(file_path).name}: {details}. "
        "IMPORTANT: Do NOT silently fix. Explain what was found, why it matters, "
        "propose the fix, get user agreement, then show what changed."
    )
    return {
        "systemMessage": user_msg,
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": claude_context,
        }
    }


def _scan_file(file_path: str, patterns: list[tuple[str, str, str, str]]) -> list[str]:
    """Scan file for security anti-patterns. Returns list of finding descriptions."""
    try:
        content = Path(file_path).read_text(encoding="utf-8")
    except OSError:
        return []

    findings: list[str] = []
    for name, pattern, severity, suggestion in patterns:
        matches = list(re.finditer(pattern, content))
        if matches:
            line_num = content[:matches[0].start()].count("\n") + 1
            findings.append(f"{severity}: {name} at L{line_num} — {suggestion}")

    return findings
