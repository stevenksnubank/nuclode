#!/usr/bin/env python3
"""Consolidated PreToolUse hook — single process for all pre-tool checks.

Replaces separate spawns of secrets_scan, sast_gate, pages_guard, suggest_compact.
Reduces shell-spawn overhead from 4-5 processes to 1.

Checks (in order, first block wins):
  1. Secrets scan — block git commits containing API keys/tokens (BLOCKING)
  2. SAST gate — block git commits with HIGH severity security issues (BLOCKING)
  3. Pages guard — block GitHub Pages publishing from personal repos (BLOCKING/WARN)
  4. Git commit quality — version history, link quality on markdown files (BLOCKING)
  5. Suggest compact — advisory after N edits

Env vars:
    NUCLODE_HOOK_PROFILE    - minimal|standard|strict (default: standard)
    NUCLODE_DISABLED_HOOKS  - comma-separated hook IDs to disable
    NUCLODE_COMPACT_THRESHOLD - edits before suggesting compact (default: 30)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Shared infrastructure
# ---------------------------------------------------------------------------

HOOK_DIR = Path(__file__).parent


def _load_profile():
    """Return (current_profile, disabled_hooks) from env."""
    profile = os.environ.get("NUCLODE_HOOK_PROFILE", "standard")
    disabled = {
        h.strip()
        for h in os.environ.get("NUCLODE_DISABLED_HOOKS", "").split(",")
        if h.strip()
    }
    return profile, disabled


def _is_enabled(hook_id: str, profile: str, disabled: set, required_profiles: set) -> bool:
    """Check if a hook should run given the current profile and disabled set."""
    if hook_id in disabled:
        return False
    if profile not in required_profiles:
        return False
    return True


def _log_event(hook_name: str, event_type: str, details: dict | None = None, blocked: bool = False):
    """Best-effort telemetry logging."""
    try:
        from hook_telemetry import log_event
        log_event(hook_name, event_type, details, blocked=blocked)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Check 1: Secrets scan (on git commit)
# ---------------------------------------------------------------------------

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

_SKIP_EXTENSIONS = {".lock", ".sum", ".map", ".min.js", ".min.css", ".svg", ".png", ".jpg", ".gif", ".ico"}
_SKIP_FILENAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "go.sum", "Cargo.lock", "uv.lock"}


def _check_secrets(command: str) -> dict | None:
    """Scan staged files for secrets before git commit."""
    if "git commit" not in command:
        return None

    findings = _scan_staged_for_secrets()
    _log_event("secrets_scan", "block" if findings else "pass",
               {"findings_count": len(findings)} if findings else None,
               blocked=bool(findings))

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
                f"I found {len(findings)} potential secret(s) in staged files that shouldn't be committed:\n"
                f"{details}\n\n"
                "How to fix: Move secrets to environment variables.\n"
                "  Instead of:  API_KEY = \"sk_live_abc123\"\n"
                "  Use:         API_KEY = os.environ[\"API_KEY\"]\n\n"
                "Then set the variable in your shell: export API_KEY=sk_live_abc123"
            ),
        }
    }


def _scan_staged_for_secrets() -> list[str]:
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
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("*"):
                if not re.search(r"[=:]\s*['\"]?[A-Za-z0-9_\-/+=]{20,}", stripped):
                    continue
            for name, pattern, desc in _SECRET_PATTERNS:
                if re.search(pattern, line):
                    findings.append(f"{file_path}:{line_num} — {name} ({desc})")
                    break
    return findings


# ---------------------------------------------------------------------------
# Check 2: SAST gate (on git commit)
# ---------------------------------------------------------------------------

def _check_sast_gate(command: str) -> dict | None:
    """Block git commits with HIGH severity security patterns."""
    if "git commit" not in command:
        return None

    # Import patterns from shared module
    try:
        spec = __import__("importlib").util.spec_from_file_location(
            "sast_patterns", str(HOOK_DIR / "sast_patterns.py"))
        mod = __import__("importlib").util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        patterns = mod.PATTERNS
        skip_ext = mod.SKIP_EXTENSIONS
        skip_names = mod.SKIP_FILENAMES
    except Exception:
        return None

    findings = _scan_staged_for_sast(patterns, skip_ext, skip_names)
    _log_event("sast_gate", "block" if findings else "pass",
               {"findings_count": len(findings)} if findings else None,
               blocked=bool(findings))

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
                f"I caught {len(findings)} security issue(s) in staged files that need attention:\n"
                f"{details}\n\n"
                "This is a common pattern to catch — just say \"fix the security issues\" "
                "and I'll rewrite the code safely."
            ),
        }
    }


def _scan_staged_for_sast(patterns, skip_ext, skip_names) -> list[str]:
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
        if path.suffix in skip_ext or path.name in skip_names:
            continue
        ext = path.suffix.lstrip(".")
        file_patterns = patterns.get(ext)
        if not file_patterns:
            continue
        high_patterns = [(n, p, s, sg) for n, p, s, sg in file_patterns if s == "HIGH"]
        if not high_patterns:
            continue
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
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("*"):
                continue
            for name, pattern, severity, suggestion in high_patterns:
                if re.search(pattern, line):
                    findings.append(f"{file_path}:{line_num} — {name}: {suggestion}")
                    break
    return findings


# ---------------------------------------------------------------------------
# Check 3: Pages guard (Bash, Write, Edit)
# ---------------------------------------------------------------------------

def _check_pages_guard(tool_name: str, tool_input: dict) -> dict | None:
    """Block GitHub Pages publishing from personal repos."""
    if tool_name == "Bash":
        return _pages_check_bash(tool_input.get("command", ""))
    elif tool_name in ("Write", "Edit"):
        return _pages_check_file(tool_input.get("file_path", ""))
    return None


def _pages_check_bash(command: str) -> dict | None:
    if re.search(r"git\s+push.*gh-pages", command):
        return _pages_block(
            "You're pushing to a gh-pages branch, which publishes content as a public website. "
            "This can accidentally expose confidential material. "
            "If this is intentional and approved, use an org repo with access controls."
        )
    if re.search(r"git\s+(checkout|switch)\s+(-b\s+)?gh-pages", command):
        return _pages_block(
            "You're creating a gh-pages branch. This branch automatically publishes content "
            "as a public GitHub Pages website. Confidential material pushed here is visible to anyone."
        )
    if re.search(r"gh\s+pages", command):
        return _pages_block(
            "GitHub Pages publishes content publicly. Confidential material should not be deployed this way."
        )
    if re.search(r"(jekyll\s+serve|bundle\s+exec\s+jekyll|mkdocs\s+gh-deploy)", command):
        return _pages_warn(
            "This looks like GitHub Pages or static site deployment. Make sure no confidential "
            "content is included — GitHub Pages is publicly accessible."
        )
    return None


def _pages_check_file(file_path: str) -> dict | None:
    if not file_path:
        return None
    name = Path(file_path).name
    if name in ("_config.yml", "_config.yaml"):
        return _pages_warn(
            "You're creating a Jekyll config file, which is used by GitHub Pages. "
            "If this site will be published, ensure no confidential content is included."
        )
    if ".github/workflows" in file_path:
        try:
            content = Path(file_path).read_text(encoding="utf-8") if Path(file_path).exists() else ""
            if "pages" in content.lower() and ("deploy" in content.lower() or "publish" in content.lower()):
                return _pages_warn(
                    "This GitHub Actions workflow appears to deploy to GitHub Pages. "
                    "Pages content is publicly accessible — verify no confidential data is included."
                )
        except OSError:
            pass
    if name == "CNAME" and Path(file_path).parent.name in (".", "docs", "public"):
        return _pages_warn(
            "A CNAME file configures a custom domain for GitHub Pages. "
            "This means the content will be publicly accessible at that domain."
        )
    return None


def _pages_block(reason: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "block",
            "permissionDecisionReason": f"I caught a potential data exposure risk: {reason}",
        }
    }


def _pages_warn(reason: str) -> dict:
    return {
        "systemMessage": f"Heads up — {reason}",
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": f"[pages-guard] {reason}. Confirm with the user this is intentional.",
        },
    }


# ---------------------------------------------------------------------------
# Check 4: Git commit quality gates (markdown files)
# Adapted from stu-ai-projects consolidated pre-tool-use hook.
# Checks version history, link quality, and errata on staged .md files.
# ---------------------------------------------------------------------------

def _check_commit_quality(command: str) -> dict | None:
    """Quality checks on staged markdown files before git commit."""
    if "git commit" not in command:
        return None

    today = date.today().isoformat()

    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return None
        # Only check .md files in subdirectories (not top-level like README.md)
        staged_md = [
            f.strip() for f in result.stdout.strip().splitlines()
            if f.strip().endswith(".md") and "/" in f.strip()
        ]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None

    if not staged_md:
        return None

    warnings: list[str] = []

    for file_path in staged_md:
        if not Path(file_path).exists():
            continue

        try:
            content = Path(file_path).read_text(encoding="utf-8")
        except OSError:
            continue

        # Version history check: staged research docs should have today's entry
        if "## Version History" in content:
            if f"| {today}" not in content:
                warnings.append(f"  - {file_path}: Version History has no entry for today ({today})")
        # Only warn about missing version history for research-like docs (has AI disclaimer or Sources)
        elif "AI Disclaimer" in content or "## Sources" in content:
            warnings.append(f"  - {file_path}: no Version History section found")

        # Link quality: imprecise code links (branch names instead of commit hashes)
        for match in re.finditer(r'github\.com/[^)]*/(blob|tree)/(main|master|develop|HEAD)/', content):
            line_num = content[:match.start()].count("\n") + 1
            warnings.append(f"  - {file_path}:L{line_num}: imprecise code link (uses branch name, not commit hash)")

        # Link quality: raw URLs as link display text
        for match in re.finditer(r'\[https?://[^\]]*\]\(https?://', content):
            line_num = content[:match.start()].count("\n") + 1
            warnings.append(f"  - {file_path}:L{line_num}: raw URL used as link display text")

        # Errata section check (only for research docs)
        if ("AI Disclaimer" in content or "## Sources" in content) and "## Errata" not in content:
            warnings.append(f"  - {file_path}: no Errata section found (required for research docs)")

        # Unescaped pipe chars inside backticks in table rows (GFM rendering issue)
        for line_num, line in enumerate(content.splitlines(), 1):
            if line.startswith("|"):
                # Find backtick spans and check for unescaped pipes
                for span_match in re.finditer(r'`[^`]*`', line):
                    span = span_match.group()
                    # Check for pipe not preceded by backslash
                    if re.search(r'(?<!\\)\|', span):
                        warnings.append(
                            f"  - {file_path}:L{line_num}: unescaped pipe inside backticks in table row "
                            "(escape as \\| per GFM Example 200)"
                        )
                        break

    if not warnings:
        return None

    _log_event("commit_quality", "block", {"warnings": warnings[:5]}, blocked=True)

    details = "\n".join(warnings[:15])
    if len(warnings) > 15:
        details += f"\n  ... and {len(warnings) - 15} more"

    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "block",
            "permissionDecisionReason": (
                f"Pre-commit quality checks found {len(warnings)} issue(s) in staged markdown files:\n"
                f"{details}\n\n"
                "Fix these before committing. Consider running /research-review for deeper analysis."
            ),
        }
    }


# ---------------------------------------------------------------------------
# Check 5: Suggest compact (on Edit|Write)
# ---------------------------------------------------------------------------

def _check_suggest_compact(tool_name: str, input_data: dict) -> dict | None:
    """Track edit count and suggest compaction at intervals."""
    if tool_name not in ("Edit", "Write"):
        return None

    threshold = int(os.environ.get("NUCLODE_COMPACT_THRESHOLD", "30"))
    session_id = input_data.get("session_id", str(os.getppid()))

    counter_dir = Path.home() / ".claude" / "sessions"
    counter_dir.mkdir(parents=True, exist_ok=True)
    counter_file = counter_dir / f"edit-count-{session_id}"

    count = 0
    if counter_file.exists():
        try:
            count = int(counter_file.read_text(encoding="utf-8").strip())
        except (ValueError, OSError):
            count = 0

    count += 1
    try:
        counter_file.write_text(str(count), encoding="utf-8")
    except OSError:
        pass

    if count > 0 and count % threshold == 0:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": (
                    f"[suggest-compact] {count} edits in this session. "
                    "Consider running /compact to free context window space."
                ),
            }
        }
    return None


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

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    command = tool_input.get("command", "") if tool_name == "Bash" else ""

    # --- Blocking checks (first block wins) ---

    # 1. Secrets scan (Bash only, standard+strict)
    if tool_name == "Bash" and _is_enabled("pre:secrets-scan", profile, disabled, {"standard", "strict"}):
        result = _check_secrets(command)
        if result:
            json.dump(result, sys.stdout)
            return

    # 2. SAST gate (Bash only, standard+strict)
    if tool_name == "Bash" and _is_enabled("pre:sast-gate", profile, disabled, {"standard", "strict"}):
        result = _check_sast_gate(command)
        if result:
            json.dump(result, sys.stdout)
            return

    # 3. Pages guard (Bash|Write|Edit, standard+strict)
    if tool_name in ("Bash", "Write", "Edit") and _is_enabled("pre:pages-guard", profile, disabled, {"standard", "strict"}):
        result = _check_pages_guard(tool_name, tool_input)
        if result:
            json.dump(result, sys.stdout)
            return

    # 4. Commit quality gates (Bash only, standard+strict)
    if tool_name == "Bash" and _is_enabled("pre:commit-quality", profile, disabled, {"standard", "strict"}):
        result = _check_commit_quality(command)
        if result:
            json.dump(result, sys.stdout)
            return

    # --- Advisory checks (non-blocking, collect context) ---

    # 5. Suggest compact (Edit|Write, strict only)
    if _is_enabled("pre:suggest-compact", profile, disabled, {"strict"}):
        result = _check_suggest_compact(tool_name, input_data)
        if result:
            json.dump(result, sys.stdout)
            return


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Advisory hooks never block Claude. Log to stderr, exit clean.
        print(f"pre_tool_use error: {e}", file=sys.stderr)
        sys.exit(0)
