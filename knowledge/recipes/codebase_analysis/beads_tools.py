"""Beads CLI wrappers for the codebase analysis recipe.

All bd CLI calls use subprocess.run with list arguments — never shell=True.
Input validation prevents shell injection.
"""

from __future__ import annotations

import re
import subprocess
from functools import partial
from pathlib import Path

_VALID_BEAD_ID_RE = re.compile(r"^[a-zA-Z0-9\-_]+$")
_VALID_REL_TYPES = frozenset({"depends-on", "relates-to", "blocks"})
_VALID_TAG_RE = re.compile(r"^[a-zA-Z0-9\-_]+$")


def _validate_bead_id(bead_id: str) -> None:
    if not _VALID_BEAD_ID_RE.match(bead_id):
        raise ValueError(f"Invalid bead ID format: {bead_id!r}")


def _validate_rel_type(rel_type: str) -> None:
    if rel_type not in _VALID_REL_TYPES:
        raise ValueError(
            f"Invalid rel_type: {rel_type!r}. Must be one of: {sorted(_VALID_REL_TYPES)}"
        )


def _validate_tag(tag: str) -> None:
    if not _VALID_TAG_RE.match(tag):
        raise ValueError(f"Invalid tag format: {tag!r}")


def _run_bd(args: list[str], project_dir: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run a bd CLI command safely."""
    cmd = ["bd"] + args
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(project_dir) if project_dir else None,
        timeout=30,
    )


def create_bead(
    title: str, body: str, tags: list[str] | None = None, project_dir: Path | None = None
) -> str:
    """Create a bead via bd CLI. Returns bead ID."""
    args = ["create", title, "-b", body]
    if tags:
        for tag in tags:
            _validate_tag(tag)
            args.extend(["-t", tag])

    result = _run_bd(args, project_dir)
    if result.returncode != 0:
        raise RuntimeError(f"bd create failed: {result.stderr}")
    return result.stdout.strip()


def link_beads(
    from_id: str, to_id: str, rel_type: str, project_dir: Path | None = None
) -> bool:
    """Link two beads. Returns True on success."""
    _validate_bead_id(from_id)
    _validate_bead_id(to_id)
    _validate_rel_type(rel_type)

    result = _run_bd(["link", from_id, to_id, "--type", rel_type], project_dir)
    return result.returncode == 0


def tag_bead(bead_id: str, tags: list[str], project_dir: Path | None = None) -> bool:
    """Add tags to a bead. Returns True on success."""
    _validate_bead_id(bead_id)
    for tag in tags:
        _validate_tag(tag)

    args = ["tag", bead_id]
    for tag in tags:
        args.extend(["-t", tag])

    result = _run_bd(args, project_dir)
    return result.returncode == 0


def comment_bead(bead_id: str, text: str, project_dir: Path | None = None) -> bool:
    """Add a comment to a bead. Returns True on success."""
    _validate_bead_id(bead_id)
    result = _run_bd(["comment", bead_id, text], project_dir)
    return result.returncode == 0


def close_bead(bead_id: str, summary: str, project_dir: Path | None = None) -> bool:
    """Close a bead with a summary. Returns True on success."""
    _validate_bead_id(bead_id)
    result = _run_bd(["close", bead_id, "-m", summary], project_dir)
    return result.returncode == 0


def query_beads(filter_expr: str, project_dir: Path | None = None) -> str:
    """Query beads with a filter expression. Returns bd output."""
    result = _run_bd(["query", "--filter", filter_expr], project_dir)
    if result.returncode != 0:
        raise RuntimeError(f"bd query failed: {result.stderr}")
    return result.stdout


def export_graph(project_dir: Path | None = None) -> str:
    """Export the beads graph. Returns export output."""
    result = _run_bd(["export"], project_dir)
    if result.returncode != 0:
        raise RuntimeError(f"bd export failed: {result.stderr}")
    return result.stdout


def get_custom_tools(project_dir: Path) -> dict:
    """Return custom_tools dict formatted for the engine's REPL loop."""
    return {
        "create_bead": {
            "tool": partial(create_bead, project_dir=project_dir),
            "description": "Create a bead. Args: title (str), body (str), tags (list[str]). Returns: bead ID.",
        },
        "link_beads": {
            "tool": partial(link_beads, project_dir=project_dir),
            "description": "Link two beads. Args: from_id (str), to_id (str), rel_type (str: 'depends-on'|'relates-to'|'blocks'). Returns: bool.",
        },
        "tag_bead": {
            "tool": partial(tag_bead, project_dir=project_dir),
            "description": "Add tags to a bead. Args: bead_id (str), tags (list[str]). Returns: bool.",
        },
        "comment_bead": {
            "tool": partial(comment_bead, project_dir=project_dir),
            "description": "Add a comment to a bead. Args: bead_id (str), text (str). Returns: bool.",
        },
        "close_bead": {
            "tool": partial(close_bead, project_dir=project_dir),
            "description": "Close a bead with summary. Args: bead_id (str), summary (str). Returns: bool.",
        },
        "query_beads": {
            "tool": partial(query_beads, project_dir=project_dir),
            "description": "Query beads. Args: filter_expr (str). Returns: str.",
        },
        "export_graph": {
            "tool": partial(export_graph, project_dir=project_dir),
            "description": "Export the beads graph. Returns: str.",
        },
    }
