"""PreToolUse hook — scan for secrets in staged files before git commit. BLOCKING."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

# Patterns that strongly indicate hardcoded secrets.
# Each tuple: (name, regex pattern, description)
_SECRET_PATTERNS: list[tuple[str, str, str]] = [
    ("AWS Access Key", r"AKIA[0-9A-Z]{16}", "AWS access key ID"),
    ("AWS Secret Key", r"(?i)aws_secret_access_key\s*[=:]\s*['\"]?[A-Za-z0-9/+=]{40}", "AWS secret access key"),
    ("GitHub Token", r"gh[pousr]_[A-Za-z0-9_]{36,}", "GitHub personal access token"),
    ("GitLab Token", r"glpat-[A-Za-z0-9\-_]{20,}", "GitLab personal access token"),
    ("Slack Token", r"xox[bpors]-[A-Za-z0-9\-]{10,}", "Slack API token"),
    ("Stripe Key", r"sk_live_[A-Za-z0-9]{20,}", "Stripe secret key"),
    ("Stripe Publishable", r"pk_live_[A-Za-z0-9]{20,}", "Stripe publishable key (live)"),
    ("Generic API Key", r"(?i)(api[_-]?key|apikey)\s*[=:]\s*['\"]?[A-Za-z0-9_\-]{20,}['\"]?", "Possible API key assignment"),
    ("Generic Secret", r"(?i)(secret|password|passwd|token)\s*[=:]\s*['\"][^'\"]{8,}['\"]", "Possible hardcoded secret"),
    ("Private Key", r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----", "Private key in file"),
    ("Heroku API Key", r"(?i)heroku.*[=:]\s*['\"]?[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "Heroku API key"),
    ("Generic Bearer Token", r"(?i)bearer\s+[A-Za-z0-9_\-.]{20,}", "Bearer token in code"),
]

# Files to skip (these commonly contain key-like patterns that aren't secrets)
_SKIP_EXTENSIONS = {".lock", ".sum", ".map", ".min.js", ".min.css", ".svg", ".png", ".jpg", ".gif", ".ico"}
_SKIP_FILENAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "go.sum", "Cargo.lock", "uv.lock"}


def run(input: dict) -> dict | None:
    tool_name = input.get("tool_name", "")
    tool_input = input.get("tool_input", {})

    # Only intercept git commit commands
    command = tool_input.get("command", "")
    if tool_name != "Bash" or "git commit" not in command:
        return None

    findings = _scan_staged_files()

    # Telemetry
    try:
        from hook_telemetry import log_event
        if findings:
            log_event("secrets_scan", "block", {"findings_count": len(findings), "findings": findings[:5]}, blocked=True)
        else:
            log_event("secrets_scan", "pass")
    except Exception:
        pass

    if not findings:
        return None

    # Format findings for blocking message
    details = "\n".join(f"  - {f}" for f in findings[:10])
    if len(findings) > 10:
        details += f"\n  ... and {len(findings) - 10} more"

    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "block",
            "permissionDecisionReason": (
                f"[secrets-scan] BLOCKED: Found {len(findings)} potential secret(s) in staged files:\n"
                f"{details}\n\n"
                "How to fix: Move secrets to environment variables.\n"
                "  Instead of:  API_KEY = \"sk_live_abc123\"\n"
                "  Use:         API_KEY = os.environ[\"API_KEY\"]\n\n"
                "Then set the variable in your shell: export API_KEY=sk_live_abc123"
            ),
        }
    }


def _scan_staged_files() -> list[str]:
    """Scan git staged files for secret patterns."""
    findings: list[str] = []

    # Get list of staged files
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

        # Skip binary/lock files
        if path.suffix in _SKIP_EXTENSIONS:
            continue
        if path.name in _SKIP_FILENAMES:
            continue

        # Get staged content (what will actually be committed)
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

        # Scan each line
        for line_num, line in enumerate(content.splitlines(), 1):
            # Skip comments that describe patterns (common in security tools/docs)
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("*"):
                # But still check for actual key assignments in comments
                if not re.search(r"[=:]\s*['\"]?[A-Za-z0-9_\-/+=]{20,}", stripped):
                    continue

            for name, pattern, desc in _SECRET_PATTERNS:
                if re.search(pattern, line):
                    # Redact the actual secret from the finding
                    findings.append(f"{file_path}:{line_num} — {name} ({desc})")
                    break  # One finding per line is enough

    return findings
