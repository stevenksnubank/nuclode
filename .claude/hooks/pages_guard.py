"""PreToolUse hook — BLOCK GitHub Pages publishing from personal repos.

Prevents accidental publication of confidential material via GitHub Pages.
Catches: gh-pages branch creation/push, Pages config files, Jekyll setup,
GitHub Actions deploying to Pages.

This is a Nubank-specific guard: org repos may have Pages configured
intentionally, but personal repos publishing Pages is a data leak risk.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


def run(input: dict) -> dict | None:
    tool_name = input.get("tool_name", "")
    tool_input = input.get("tool_input", {})

    if tool_name == "Bash":
        return _check_bash_command(tool_input.get("command", ""))
    elif tool_name in ("Write", "Edit"):
        return _check_file_write(tool_input.get("file_path", ""))

    return None


def _check_bash_command(command: str) -> dict | None:
    """Block git push to gh-pages or GitHub Pages setup commands."""

    # Block pushing to gh-pages branch
    if re.search(r"git\s+push.*gh-pages", command):
        return _block(
            "You're pushing to a gh-pages branch, which publishes content as a public website. "
            "At Nubank, this can accidentally expose confidential material. "
            "If this is intentional and approved, use a Nubank org repo with access controls."
        )

    # Block creating gh-pages branch
    if re.search(r"git\s+(checkout|switch)\s+(-b\s+)?gh-pages", command):
        return _block(
            "You're creating a gh-pages branch. This branch automatically publishes content "
            "as a public GitHub Pages website. Confidential material pushed here is visible to anyone. "
            "If you need a public page, coordinate with your team lead first."
        )

    # Block GitHub CLI pages commands
    if re.search(r"gh\s+pages", command):
        return _block(
            "GitHub Pages publishes content publicly. Confidential material should not be deployed this way."
        )

    # Block Jekyll/static site serve commands that indicate Pages setup
    if re.search(r"(jekyll\s+serve|bundle\s+exec\s+jekyll|mkdocs\s+gh-deploy)", command):
        return _warn(
            "This looks like GitHub Pages or static site deployment. Make sure no confidential "
            "content is included — GitHub Pages is publicly accessible."
        )

    return None


def _check_file_write(file_path: str) -> dict | None:
    """Warn when creating GitHub Pages configuration files."""
    if not file_path:
        return None

    name = Path(file_path).name
    rel_path = file_path

    # Jekyll config (GitHub Pages default)
    if name == "_config.yml" or name == "_config.yaml":
        return _warn(
            "You're creating a Jekyll config file, which is used by GitHub Pages. "
            "If this site will be published, ensure no confidential content is included."
        )

    # GitHub Actions deploying to Pages
    if ".github/workflows" in rel_path:
        try:
            content = (
                Path(file_path).read_text(encoding="utf-8") if Path(file_path).exists() else ""
            )
            if "pages" in content.lower() and (
                "deploy" in content.lower() or "publish" in content.lower()
            ):
                return _warn(
                    "This GitHub Actions workflow appears to deploy to GitHub Pages. "
                    "Pages content is publicly accessible — verify no confidential data is included."
                )
        except OSError:
            pass

    # CNAME file (custom domain for GitHub Pages)
    if name == "CNAME" and Path(file_path).parent.name in (".", "docs", "public"):
        return _warn(
            "A CNAME file configures a custom domain for GitHub Pages. "
            "This means the content will be publicly accessible at that domain."
        )

    return None


def _block(reason: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "block",
            "permissionDecisionReason": f"I caught a potential data exposure risk: {reason}",
        }
    }


def _warn(reason: str) -> dict:
    return {
        "systemMessage": f"Heads up — {reason}",
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": f"[pages-guard] {reason}. Confirm with the user this is intentional.",
        },
    }
