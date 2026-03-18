"""Shared SAST patterns used by both edit-time scan and commit-time gate."""
from __future__ import annotations

# Security anti-patterns by file extension.
# Each tuple: (name, regex, severity, suggestion)
# Severity: HIGH = blocked at commit, MEDIUM = warning only
PATTERNS: dict[str, list[tuple[str, str, str, str]]] = {
    "py": [
        ("SQL injection", r"""(?:execute|cursor\.execute|raw|query)\s*\(\s*f['""]""", "HIGH",
         "f-strings in SQL let attackers run arbitrary queries — use parameterized queries instead"),
        ("SQL injection (format)", r"""(?:execute|cursor\.execute)\s*\(\s*['""].*%s.*['""]\.format""", "HIGH",
         ".format() in SQL lets attackers manipulate queries — use parameterized queries instead"),
        ("SQL injection (concat)", r"""(?:execute|cursor\.execute)\s*\(\s*['""].*['""]?\s*\+""", "HIGH",
         "String concatenation in SQL lets attackers inject commands — use parameterized queries instead"),
        ("eval() usage", r"""\beval\s*\(""", "HIGH",
         "eval() executes arbitrary code — replace with ast.literal_eval() or a safe parser"),
        ("exec() usage", r"""\bexec\s*\(""", "MEDIUM",
         "exec() runs arbitrary code — consider a safer alternative"),
        ("pickle.loads", r"""pickle\.loads?\s*\(""", "HIGH",
         "Pickle can execute arbitrary code during deserialization — use json instead"),
        ("yaml.load unsafe", r"""yaml\.load\s*\([^)]*(?!Loader)""", "MEDIUM",
         "yaml.load() can execute code — use yaml.safe_load() instead"),
        ("subprocess shell=True", r"""subprocess\.\w+\(.*shell\s*=\s*True""", "HIGH",
         "shell=True lets attackers inject commands via the input — use list arguments instead"),
        ("os.system()", r"""\bos\.system\s*\(""", "HIGH",
         "os.system() runs commands through the shell — use subprocess.run() with list args instead"),
        ("tempfile insecure", r"""(?:tempfile\.mktemp|open\s*\(\s*['""][/\\]tmp)""", "MEDIUM",
         "Predictable temp paths can be exploited — use tempfile.mkstemp() instead"),
    ],
    "js": [
        ("eval() usage", r"""\beval\s*\(""", "HIGH",
         "eval() executes arbitrary code — use JSON.parse() for data instead"),
        ("innerHTML XSS", r"""\.innerHTML\s*=""", "HIGH",
         "innerHTML renders raw HTML which enables XSS attacks — use textContent or a sanitization library"),
        ("document.write XSS", r"""document\.write\s*\(""", "HIGH",
         "document.write() can inject scripts — use DOM methods instead"),
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
