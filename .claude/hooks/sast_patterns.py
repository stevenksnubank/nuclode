"""Shared SAST patterns used by both edit-time scan and commit-time gate."""
from __future__ import annotations

# Security anti-patterns by file extension.
# Each tuple: (name, regex, severity, suggestion)
# Severity: HIGH = blocked at commit, MEDIUM = warning only
PATTERNS: dict[str, list[tuple[str, str, str, str]]] = {
    "py": [
        # --- Injection ---
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
        ("subprocess shell=True", r"""subprocess\.\w+\(.*shell\s*=\s*True""", "HIGH",
         "shell=True lets attackers inject commands via the input — use list arguments instead"),
        ("os.system()", r"""\bos\.system\s*\(""", "HIGH",
         "os.system() runs commands through the shell — use subprocess.run() with list args instead"),

        # --- Deserialization ---
        ("pickle.loads", r"""pickle\.loads?\s*\(""", "HIGH",
         "Pickle can execute arbitrary code during deserialization — use json instead"),
        ("yaml.load unsafe", r"""yaml\.load\s*\([^)]*(?!Loader)""", "MEDIUM",
         "yaml.load() can execute code — use yaml.safe_load() instead"),

        # --- Crypto ---
        ("Weak hash (MD5)", r"""hashlib\.md5\(""", "HIGH",
         "MD5 is cryptographically broken — use hashlib.sha256() or bcrypt for passwords"),
        ("Weak hash (SHA1)", r"""hashlib\.sha1\(""", "MEDIUM",
         "SHA1 has known collisions — use hashlib.sha256() or stronger"),
        ("ECB mode", r"""AES\.new\(.*MODE_ECB""", "HIGH",
         "ECB mode leaks patterns in encrypted data — use CBC or GCM mode instead"),
        ("Hardcoded IV/nonce", r"""(?:iv|nonce)\s*=\s*b['\"]""", "MEDIUM",
         "Hardcoded IVs/nonces break encryption safety — generate randomly with os.urandom()"),

        # --- Path traversal ---
        ("Unsanitized file open", r"""open\(\s*(?:request\.|input\(|sys\.argv|args\[|params\[)""", "HIGH",
         "Opening files from user input enables path traversal — validate and resolve the path first"),
        ("Unsanitized Path()", r"""Path\(\s*(?:request\.|input\(|sys\.argv|args\[|params\[)""", "HIGH",
         "Constructing paths from user input enables traversal — use .resolve() and check against allowed dirs"),

        # --- SSRF ---
        ("Potential SSRF", r"""requests\.(?:get|post|put|delete|patch)\(\s*[a-zA-Z_]""", "MEDIUM",
         "Passing variables to requests can enable SSRF — validate URLs against an allowlist"),
        ("urllib SSRF", r"""urllib\.request\.urlopen\(\s*[a-zA-Z_]""", "MEDIUM",
         "Passing variables to urlopen can enable SSRF — validate URLs against an allowlist"),

        # --- Logging ---
        ("Logging sensitive data", r"""(?:log(?:ger|ging)?|print)\s*\(.*(?:password|passwd|token|secret|api_key|private_key|credential)""", "HIGH",
         "Sensitive data in logs can be exposed in monitoring systems — redact before logging"),

        # --- Redirect ---
        ("Open redirect", r"""redirect\(\s*(?:request\.|input\(|args\[|params\[)""", "MEDIUM",
         "Redirecting to user-supplied URLs enables phishing — validate against allowed destinations"),

        # --- Misc ---
        ("tempfile insecure", r"""(?:tempfile\.mktemp|open\s*\(\s*['""][/\\]tmp)""", "MEDIUM",
         "Predictable temp paths can be exploited — use tempfile.mkstemp() instead"),
        ("Hardcoded internal IP", r"""['\"]https?://(?:10\.\d|172\.(?:1[6-9]|2\d|3[01])\.|192\.168\.)""", "MEDIUM",
         "Hardcoded internal IPs break across environments — use config or environment variables"),
        ("Debug mode in production", r"""(?:DEBUG|debug)\s*=\s*True""", "MEDIUM",
         "Debug mode exposes internal state — ensure this is disabled in production config"),
    ],
    "js": [
        # --- Injection/XSS ---
        ("eval() usage", r"""\beval\s*\(""", "HIGH",
         "eval() executes arbitrary code — use JSON.parse() for data instead"),
        ("innerHTML XSS", r"""\.innerHTML\s*=""", "HIGH",
         "innerHTML renders raw HTML which enables XSS attacks — use textContent or a sanitization library"),
        ("document.write XSS", r"""document\.write\s*\(""", "HIGH",
         "document.write() can inject scripts — use DOM methods instead"),
        ("dangerouslySetInnerHTML", r"""dangerouslySetInnerHTML""", "MEDIUM",
         "Unsanitized HTML can enable XSS attacks — sanitize with DOMPurify or similar before rendering"),

        # --- Crypto ---
        ("Weak crypto (createCipher)", r"""crypto\.createCipher\(""", "HIGH",
         "createCipher uses weak key derivation — use createCipheriv with a proper key and IV"),
        ("MD5 in crypto", r"""(?:crypto\.createHash|CryptoJS\.MD5)\s*\(\s*['\"]md5""", "HIGH",
         "MD5 is cryptographically broken — use SHA-256 or stronger"),

        # --- Path/SSRF ---
        ("Unsanitized file read", r"""(?:fs\.readFile|fs\.readFileSync)\(\s*(?:req\.|input|args|params)""", "HIGH",
         "Reading files from user input enables path traversal — validate the path first"),
        ("Potential SSRF (fetch)", r"""fetch\(\s*[a-zA-Z_]""", "MEDIUM",
         "Passing variables to fetch can enable SSRF — validate URLs against an allowlist"),

        # --- Logging ---
        ("Logging sensitive data", r"""console\.(?:log|info|debug)\(.*(?:password|token|secret|apiKey|privateKey)""", "HIGH",
         "Sensitive data in console output can leak to browser devtools or log aggregators — redact first"),

        # --- Config ---
        ("Hardcoded internal IP", r"""['\"]https?://(?:10\.\d|172\.(?:1[6-9]|2\d|3[01])\.|192\.168\.)""", "MEDIUM",
         "Hardcoded internal IPs break across environments — use config or environment variables"),
    ],
    "ts": [],
    "tsx": [],
    "jsx": [],
    "go": [
        # --- Injection ---
        ("SQL injection", r"""(?:Query|Exec)\s*\(\s*(?:ctx\s*,\s*)?(?:fmt\.Sprintf|['""].*['""]?\s*\+)""", "HIGH",
         "String interpolation in SQL lets attackers manipulate queries — use parameterized queries with $1/$2 placeholders"),
        ("command injection", r"""exec\.Command\s*\(\s*['""](?:sh|bash|cmd)['""]""", "HIGH",
         "Shell execution lets attackers inject commands — use exec.Command with direct args instead"),

        # --- Crypto ---
        ("Weak hash (MD5)", r"""md5\.(?:New|Sum)""", "HIGH",
         "MD5 is cryptographically broken — use sha256 from crypto/sha256"),
        ("Weak hash (SHA1)", r"""sha1\.(?:New|Sum)""", "MEDIUM",
         "SHA1 has known collisions — use sha256 from crypto/sha256"),

        # --- Path ---
        ("Unsanitized file path", r"""os\.Open\(\s*(?:r\.|request\.|input|args)""", "HIGH",
         "Opening files from user input enables path traversal — use filepath.Clean and validate"),

        # --- SSRF ---
        ("Potential SSRF", r"""http\.(?:Get|Post)\(\s*[a-zA-Z_]""", "MEDIUM",
         "Passing variables to http.Get/Post can enable SSRF — validate URLs against an allowlist"),

        # --- Logging ---
        ("Logging sensitive data", r"""log\.(?:Print|Printf|Println)\(.*(?:password|token|secret|key|credential)""", "HIGH",
         "Sensitive data in logs can be exposed — redact before logging"),

        # --- Config ---
        ("Hardcoded internal IP", r"""['\"]https?://(?:10\.\d|172\.(?:1[6-9]|2\d|3[01])\.|192\.168\.)""", "MEDIUM",
         "Hardcoded internal IPs break across environments — use config or environment variables"),
    ],
    "rb": [
        ("eval() usage", r"""\beval\s*\(""", "HIGH",
         "eval() executes arbitrary code from the input — use a safe parser or dispatch table instead"),
        ("system() usage", r"""\bsystem\s*\(""", "MEDIUM",
         "system() runs commands through the shell — use Open3 for safer subprocess calls"),
        ("Open redirect", r"""redirect_to\s*(?:params|request)""", "MEDIUM",
         "Redirecting to user-supplied URLs enables phishing — validate against allowed paths"),
    ],
    "clj": [
        # --- Clojure (important for Nubank) ---
        ("eval usage", r"""\(eval\b""", "HIGH",
         "eval executes arbitrary Clojure forms — use a safe dispatch map instead"),
        ("shell-out injection", r"""(?:clojure\.java\.shell/sh|sh\s)\s""", "MEDIUM",
         "Shell commands can be injected via user input — validate and sanitize arguments"),
        ("SQL injection", r"""(?:execute!|query)\s.*(?:str\s|format\s)""", "HIGH",
         "String-built SQL lets attackers inject queries — use parameterized queries with ?"),
    ],
}

# JS patterns apply to TS/JSX/TSX too
for _ext in ("ts", "tsx", "jsx"):
    PATTERNS[_ext] = PATTERNS.get(_ext, []) + PATTERNS["js"]

# Files to skip
SKIP_EXTENSIONS = {".lock", ".sum", ".map", ".min.js", ".min.css", ".svg", ".png", ".jpg", ".gif", ".ico"}
SKIP_FILENAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "go.sum", "Cargo.lock", "uv.lock"}
