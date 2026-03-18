"""PreToolUse hook — BLOCK git commits containing HIGH severity security issues.

Tier 1 (BLOCKING): SQL injection, eval(), innerHTML XSS, shell=True, os.system(),
pickle.loads, command injection. These are always wrong in application code.

Tier 2 (WARNING via sast_scan.py): exec(), unsafe yaml.load, dangerouslySetInnerHTML,
system() in Ruby, insecure tempfile. These need judgment.

Tier 3 (GUIDANCE via nuclode-guide agent): Missing input validation, auth checks,
test coverage. These are enforced through workflow, not hooks.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

# Import shared patterns
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("sast_patterns", str(Path(__file__).parent / "sast_patterns.py"))
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
_PATTERNS = _mod.PATTERNS
_SKIP_EXTENSIONS = _mod.SKIP_EXTENSIONS
_SKIP_FILENAMES = _mod.SKIP_FILENAMES


def run(input: dict) -> dict | None:
    tool_name = input.get("tool_name", "")
    tool_input = input.get("tool_input", {})

    # Only intercept git commit commands
    command = tool_input.get("command", "")
    if tool_name != "Bash" or "git commit" not in command:
        return None

    findings = _scan_staged_files()

    try:
        from hook_telemetry import log_event
        if findings:
            log_event("sast_gate", "block", {"findings_count": len(findings), "findings": findings[:5]}, blocked=True)
        else:
            log_event("sast_gate", "pass")
    except Exception:
        pass

    if not findings:
        return None

    details = "\n".join(f"  - {f}" for f in findings[:10])
    if len(findings) > 10:
        details += f"\n  ... and {len(findings) - 10} more"

    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "block",
            "permissionDecisionReason": (
                f"[sast-gate] BLOCKED: Found {len(findings)} HIGH severity security issue(s) in staged files:\n"
                f"{details}\n\n"
                "Fix these security issues before committing. These patterns are blocked because they "
                "introduce exploitable vulnerabilities (injection, XSS, command execution)."
            ),
        }
    }


def _scan_staged_files() -> list[str]:
    """Scan git staged files for HIGH severity security patterns."""
    findings: list[str] = []

    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return []
        staged_files = [f.strip() for f in result.stdout.strip().splitlines() if f.strip()]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []

    for file_path in staged_files:
        path = Path(file_path)

        if path.suffix in _SKIP_EXTENSIONS or path.name in _SKIP_FILENAMES:
            continue

        ext = path.suffix.lstrip(".")
        patterns = _PATTERNS.get(ext)
        if not patterns:
            continue

        # Only HIGH severity patterns block commits
        high_patterns = [(n, p, s, sg) for n, p, s, sg in patterns if s == "HIGH"]
        if not high_patterns:
            continue

        # Get staged content
        try:
            result = subprocess.run(
                ["git", "show", f":{file_path}"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode != 0:
                continue
            content = result.stdout
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

        for line_num, line in enumerate(content.splitlines(), 1):
            # Skip comments
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("*"):
                continue

            for name, pattern, severity, suggestion in high_patterns:
                if re.search(pattern, line):
                    findings.append(f"{file_path}:{line_num} — {name}: {suggestion}")
                    break

    return findings
