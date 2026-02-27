"""Bead schema definition and validation for flow-group analysis.

Sub-LMs return JSON conforming to FLOW_ANALYSIS_SCHEMA. The validate
function checks structure, extracts JSON from markdown if needed, and
returns the parsed dict or raises ValidationError.
"""

from __future__ import annotations

import json
import re


class ValidationError(Exception):
    """Raised when sub-LM output doesn't conform to the bead schema."""


FLOW_ANALYSIS_SCHEMA: dict = {
    "required": [
        "flow_name", "entry_points", "exit_points", "namespaces",
        "data_flow", "bottlenecks", "security_findings", "coupling_issues",
    ],
    "namespace_required": ["name", "layer", "role", "side_effects", "security_notes"],
    "data_flow_required": ["from", "to", "transforms"],
}


def _extract_json(text: str) -> str:
    """Extract JSON from text that may contain markdown fences."""
    match = re.search(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return match.group(0)
    return text


def validate_flow_analysis(raw: str) -> dict:
    """Validate sub-LM output against the flow analysis schema.

    Extracts JSON from markdown fences if present. Validates required
    fields at top level, per-namespace, and per-data-flow-edge.

    Args:
        raw: Raw sub-LM response text.

    Returns:
        Parsed and validated dict.

    Raises:
        ValidationError: If JSON is invalid or required fields are missing.
    """
    extracted = _extract_json(raw)

    try:
        data = json.loads(extracted)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"Invalid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ValidationError(f"Expected JSON object, got {type(data).__name__}")

    missing = [f for f in FLOW_ANALYSIS_SCHEMA["required"] if f not in data]
    if missing:
        raise ValidationError(f"missing required fields: {missing}")

    for i, ns in enumerate(data.get("namespaces", [])):
        if not isinstance(ns, dict):
            raise ValidationError(f"namespace[{i}] must be a dict")
        ns_missing = [f for f in FLOW_ANALYSIS_SCHEMA["namespace_required"] if f not in ns]
        if ns_missing:
            raise ValidationError(f"namespace[{i}] missing required: {ns_missing}")

    for i, edge in enumerate(data.get("data_flow", [])):
        if not isinstance(edge, dict):
            raise ValidationError(f"data_flow[{i}] must be a dict")
        edge_missing = [f for f in FLOW_ANALYSIS_SCHEMA["data_flow_required"] if f not in edge]
        if edge_missing:
            raise ValidationError(f"data_flow[{i}] missing required: {edge_missing}")

    return data
