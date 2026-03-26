"""PostToolUse hook — auto-format edited files based on language/project tooling."""

# ⚠️  NOT ACTIVE — This file is NOT invoked by settings.json.
# The active version of this logic lives in post_tool_use.py.
# Edit that file instead. Changes here will have no effect.
from __future__ import annotations

import subprocess
from pathlib import Path


def run(input: dict) -> dict | None:
    file_path = input.get("tool_input", {}).get("file_path", "")
    if not file_path:
        return None

    path = Path(file_path)
    if not path.exists():
        return None

    ext = path.suffix.lstrip(".")
    _format_file(ext, file_path)

    return None  # Silent hook — formatting is its own reward


def _format_file(ext: str, file_path: str) -> None:
    """Run the appropriate formatter for the file extension."""
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

    # JS/TS formatters depend on project config (check from file's directory upward)
    if ext in ("ts", "tsx", "js", "jsx"):
        js_cmd = _find_js_formatter(file_path)
        if js_cmd:
            formatters[ext] = [js_cmd]
        else:
            return  # No JS formatter config found; skip

    candidates = formatters.get(ext, [])
    for cmd in candidates:
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=10)
            if result.returncode == 0:
                return  # First successful formatter wins
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue


def _find_js_formatter(file_path: str) -> list[str] | None:
    """Walk up from file's directory to find Biome or Prettier config."""
    search_dir = Path(file_path).resolve().parent
    for d in [search_dir, *search_dir.parents]:
        if (d / "biome.json").exists() or (d / "biome.jsonc").exists():
            return ["npx", "--no-install", "@biomejs/biome", "format", "--write", file_path]
        if any((d / f).exists() for f in [".prettierrc", ".prettierrc.json", "prettier.config.js"]):
            return ["npx", "--no-install", "prettier", "--write", file_path]
        # Stop at git root or filesystem root
        if (d / ".git").exists():
            break
    return None
