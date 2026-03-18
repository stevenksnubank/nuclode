"""Shared SAST patterns used by both edit-time scan and commit-time gate."""
from __future__ import annotations

# Security anti-patterns by file extension.
# Each tuple: (name, regex, severity, suggestion)
# Severity: HIGH = blocked at commit, MEDIUM = warning only
PATTERNS: dict[str, list[tuple[str, str, str, str]]] = {
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
    "ts": [],
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
    PATTERNS[_ext] = PATTERNS.get(_ext, []) + PATTERNS["js"]

# Files to skip
SKIP_EXTENSIONS = {".lock", ".sum", ".map", ".min.js", ".min.css", ".svg", ".png", ".jpg", ".gif", ".ico"}
SKIP_FILENAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "go.sum", "Cargo.lock", "uv.lock"}
