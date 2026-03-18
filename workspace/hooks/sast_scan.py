"""PostToolUse hook — scan edited files for common security anti-patterns. Advisory."""
from __future__ import annotations

import re
from pathlib import Path

# Security anti-patterns by file extension.
# Each tuple: (name, regex, severity, suggestion)
_PATTERNS: dict[str, list[tuple[str, str, str, str]]] = {
    "py": [
        ("SQL injection", r"""(?:execute|cursor\.execute|raw|query)\s*\(\s*f['""]""", "HIGH",
         "Use parameterized queries instead of f-strings"),
        ("SQL injection (format)", r"""(?:execute|cursor\.execute)\s*\(\s*['""].*%s.*['""]\.format""", "HIGH",
         "Use parameterized queries instead of .format()"),
        ("SQL injection (concat)", r"""(?:execute|cursor\.execute)\s*\(\s*['""].*['""]?\s*\+""", "HIGH",
         "Use parameterized queries instead of string concatenation"),
        ("eval() usage", r"""\beval\s*\(""", "HIGH",
         "Never use eval() with untrusted input"),
        ("exec() usage", r"""\bexec\s*\(""", "MEDIUM",
         "Avoid exec() — use safer alternatives"),
        ("pickle.loads", r"""pickle\.loads?\s*\(""", "HIGH",
         "Pickle is unsafe for untrusted data — use json instead"),
        ("yaml.load unsafe", r"""yaml\.load\s*\([^)]*(?!Loader)""", "MEDIUM",
         "Use yaml.safe_load() instead of yaml.load()"),
        ("subprocess shell=True", r"""subprocess\.\w+\(.*shell\s*=\s*True""", "HIGH",
         "Avoid shell=True — use list arguments instead"),
        ("os.system()", r"""\bos\.system\s*\(""", "HIGH",
         "Use subprocess.run() with list args instead of os.system()"),
        ("tempfile insecure", r"""(?:tempfile\.mktemp|open\s*\(\s*['""][/\\]tmp)""", "MEDIUM",
         "Use tempfile.mkstemp() or tempfile.NamedTemporaryFile()"),
    ],
    "js": [
        ("eval() usage", r"""\beval\s*\(""", "HIGH",
         "Never use eval() — use JSON.parse() for data"),
        ("innerHTML XSS", r"""\.innerHTML\s*=""", "HIGH",
         "Use textContent or a sanitization library instead"),
        ("document.write XSS", r"""document\.write\s*\(""", "HIGH",
         "Avoid document.write() — use DOM methods"),
        ("dangerouslySetInnerHTML", r"""dangerouslySetInnerHTML""", "MEDIUM",
         "Sanitize HTML before rendering"),
    ],
    "ts": [],  # Inherits from js
    "tsx": [],
    "jsx": [],
    "go": [
        ("SQL injection", r"""(?:Query|Exec)\s*\(\s*(?:ctx\s*,\s*)?(?:fmt\.Sprintf|['""].*['""]?\s*\+)""", "HIGH",
         "Use parameterized queries with $1/$2 placeholders"),
        ("command injection", r"""exec\.Command\s*\(\s*['""](?:sh|bash|cmd)['""]""", "HIGH",
         "Avoid shell execution — use exec.Command with direct args"),
    ],
    "rb": [
        ("eval() usage", r"""\beval\s*\(""", "HIGH",
         "Never use eval() with untrusted input"),
        ("system() usage", r"""\bsystem\s*\(""", "MEDIUM",
         "Use Open3 or similar for safer subprocess calls"),
    ],
}

# JS patterns apply to TS/JSX/TSX too
for _ext in ("ts", "tsx", "jsx"):
    _PATTERNS[_ext] = _PATTERNS.get(_ext, []) + _PATTERNS["js"]


def run(input: dict) -> dict | None:
    file_path = input.get("tool_input", {}).get("file_path", "")
    if not file_path or not Path(file_path).exists():
        return None

    ext = Path(file_path).suffix.lstrip(".")
    patterns = _PATTERNS.get(ext)
    if not patterns:
        return None

    findings = _scan_file(file_path, patterns)
    if not findings:
        return None

    details = "; ".join(findings[:3])
    context = f"[sast-scan] Security issues in {Path(file_path).name}: {details}"
    return {
        "systemMessage": context,
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": context,
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
            # Find the line number of the first match
            line_num = content[:matches[0].start()].count("\n") + 1
            findings.append(f"{severity}: {name} at L{line_num} — {suggestion}")

    return findings
