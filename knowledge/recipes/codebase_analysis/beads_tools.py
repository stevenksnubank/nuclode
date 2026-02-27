"""Beads CLI wrappers for the codebase analysis recipe.

All bd CLI calls use subprocess.run with list arguments — never shell=True.
Input validation prevents shell injection.

bd CLI reference (verified against bd v0.x):
  bd create <title> [-d description] [-l label1,label2] [--silent]
  bd dep add <blocked-id> <blocker-id>
  bd label add <issue-id> <label>
  bd comments add <issue-id> "text"
  bd close <id> [-r reason]
  bd query --filter <expr>
  bd export
"""

from __future__ import annotations

import json as _json
import logging
import re
import subprocess
from functools import partial
from pathlib import Path

_logger = logging.getLogger(__name__)

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


def _run_bd(args: list[str], db_path: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run a bd CLI command safely.

    When db_path is provided, injects --db <path> before the subcommand args
    so that bd operates on a specific database file without needing cwd.
    """
    cmd = ["bd"]
    if db_path:
        cmd.extend(["--db", str(db_path), "--no-daemon"])
    cmd.extend(args)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=30,
    )


def create_bead(
    title: str, body: str, tags: list[str] | None = None, db_path: Path | None = None
) -> str:
    """Create a bead via bd CLI. Returns bead ID."""
    args = ["create", title, "-d", body, "--silent"]
    if tags:
        for tag in tags:
            _validate_tag(tag)
        args.extend(["-l", ",".join(tags)])

    result = _run_bd(args, db_path)
    if result.returncode != 0:
        raise RuntimeError(f"bd create failed: {result.stderr}")
    return result.stdout.strip()


def link_beads(
    from_id: str, to_id: str, rel_type: str, db_path: Path | None = None
) -> bool:
    """Link two beads via bd dep add. Returns True on success.

    rel_type mapping:
      "depends-on" → bd dep add <from_id> <to_id>  (from depends on to)
      "blocks"     → bd dep add <to_id> <from_id>   (from blocks to)
      "relates-to" → bd dep add <from_id> <to_id>   (generic association)
    """
    _validate_bead_id(from_id)
    _validate_bead_id(to_id)
    _validate_rel_type(rel_type)

    if rel_type == "blocks":
        # "from blocks to" means "to depends on from"
        result = _run_bd(["dep", "add", to_id, from_id], db_path)
    else:
        # "from depends on to" or "from relates to to"
        result = _run_bd(["dep", "add", from_id, to_id], db_path)
    return result.returncode == 0


def tag_bead(bead_id: str, tags: list[str], db_path: Path | None = None) -> bool:
    """Add labels to a bead. Returns True on success."""
    _validate_bead_id(bead_id)
    for tag in tags:
        _validate_tag(tag)

    success = True
    for tag in tags:
        result = _run_bd(["label", "add", bead_id, tag], db_path)
        if result.returncode != 0:
            success = False
    return success


def comment_bead(bead_id: str, text: str, db_path: Path | None = None) -> bool:
    """Add a comment to a bead. Returns True on success."""
    _validate_bead_id(bead_id)
    result = _run_bd(["comments", "add", bead_id, text], db_path)
    return result.returncode == 0


def close_bead(bead_id: str, summary: str, db_path: Path | None = None) -> bool:
    """Close a bead with a reason. Returns True on success."""
    _validate_bead_id(bead_id)
    result = _run_bd(["close", bead_id, "-r", summary], db_path)
    return result.returncode == 0


def query_beads(filter_expr: str, db_path: Path | None = None) -> str:
    """Query beads with a filter expression. Returns bd output."""
    result = _run_bd(["query", "--filter", filter_expr], db_path)
    if result.returncode != 0:
        raise RuntimeError(f"bd query failed: {result.stderr}")
    return result.stdout


def export_graph(db_path: Path | None = None) -> str:
    """Export the beads graph. Returns export output."""
    result = _run_bd(["export"], db_path)
    if result.returncode != 0:
        raise RuntimeError(f"bd export failed: {result.stderr}")
    return result.stdout


def reduce_to_beads(
    analyses: list[dict],
    project_dir: Path,
) -> dict:
    """Mechanically create beads from validated flow-group analyses.

    No LM judgment — maps validated JSON to bd CLI calls.

    Args:
        analyses: List of validated flow-analysis dicts.
        project_dir: Path to the project (for bd CLI cwd).

    Returns:
        Summary dict with beads_created, links_created, tags_applied, bead_ids.
    """
    beads_created = 0
    links_created = 0
    tags_applied = 0
    bead_ids: dict[str, str] = {}  # flow_name → bead_id

    for analysis in analyses:
        flow_name = analysis["flow_name"]
        body = _json.dumps(analysis, indent=2)

        # Collect tags from namespace layers and side effects
        tags: set[str] = {"structure"}
        for ns in analysis.get("namespaces", []):
            layer = ns.get("layer")
            if layer:
                tags.add(f"diplomat-{layer}")
            for effect in ns.get("side_effects", []):
                tags.add(f"has-{effect}")
            if ns.get("security_notes"):
                tags.add("has-security-notes")
        if analysis.get("security_findings"):
            tags.add("has-security-findings")
        if analysis.get("bottlenecks"):
            tags.add("has-bottlenecks")

        # Create the bead
        try:
            bead_id = create_bead(
                title=flow_name,
                body=body,
                tags=sorted(tags),
                db_path=project_dir,
            )
            bead_ids[flow_name] = bead_id
            beads_created += 1
            _logger.info("Created bead %s for %s", bead_id, flow_name)
        except RuntimeError as exc:
            _logger.error("Failed to create bead for %s: %s", flow_name, exc)
            continue

        # Tag with additional labels
        tag_list = sorted(tags)
        if tag_list:
            tag_bead(bead_id, tag_list, db_path=project_dir)
            tags_applied += len(tag_list)

    # Link beads based on cross-flow dependencies
    for analysis in analyses:
        flow_name = analysis["flow_name"]
        bead_id = bead_ids.get(flow_name)
        if not bead_id:
            continue
        for edge in analysis.get("data_flow", []):
            target_flow = _find_flow_for_namespace(edge.get("to", ""), analyses)
            if target_flow and target_flow != flow_name:
                target_bead_id = bead_ids.get(target_flow)
                if target_bead_id:
                    link_beads(bead_id, target_bead_id, "depends-on", db_path=project_dir)
                    links_created += 1

    return {
        "beads_created": beads_created,
        "links_created": links_created,
        "tags_applied": tags_applied,
        "bead_ids": bead_ids,
    }


def _find_flow_for_namespace(ns_name: str, analyses: list[dict]) -> str | None:
    """Find which flow group a namespace belongs to."""
    for analysis in analyses:
        for ns in analysis.get("namespaces", []):
            if ns.get("name") == ns_name:
                return analysis["flow_name"]
    return None


def get_custom_tools(db_path: Path) -> dict:
    """Return custom_tools dict formatted for the engine's REPL loop."""
    return {
        "create_bead": {
            "tool": partial(create_bead, db_path=db_path),
            "description": "Create a bead. Args: title (str), body (str), tags (list[str]|None). Returns: bead ID string.",
        },
        "link_beads": {
            "tool": partial(link_beads, db_path=db_path),
            "description": "Link two beads as dependency. Args: from_id (str), to_id (str), rel_type (str: 'depends-on'|'relates-to'|'blocks'). Returns: bool.",
        },
        "tag_bead": {
            "tool": partial(tag_bead, db_path=db_path),
            "description": "Add labels to a bead. Args: bead_id (str), tags (list[str]). Returns: bool.",
        },
        "comment_bead": {
            "tool": partial(comment_bead, db_path=db_path),
            "description": "Add a comment to a bead. Args: bead_id (str), text (str). Returns: bool.",
        },
        "close_bead": {
            "tool": partial(close_bead, db_path=db_path),
            "description": "Close a bead with reason. Args: bead_id (str), summary (str). Returns: bool.",
        },
        "query_beads": {
            "tool": partial(query_beads, db_path=db_path),
            "description": "Query beads. Args: filter_expr (str). Returns: str.",
        },
        "export_graph": {
            "tool": partial(export_graph, db_path=db_path),
            "description": "Export the beads graph. Returns: str.",
        },
    }
