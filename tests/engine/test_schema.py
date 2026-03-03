"""Tests for bead schema definition and validation."""

from __future__ import annotations

import json

import pytest

from knowledge.engine.schema import FLOW_ANALYSIS_SCHEMA, validate_flow_analysis, ValidationError


class TestValidateFlowAnalysis:

    def test_valid_minimal(self) -> None:
        data = {
            "flow_name": "payment",
            "entry_points": ["svc.wire.in.payment"],
            "exit_points": ["svc.diplomat.datomic.payment"],
            "namespaces": [
                {
                    "name": "svc.wire.in.payment",
                    "layer": "wire-in",
                    "role": "Input schema for payment requests",
                    "side_effects": [],
                    "security_notes": None,
                }
            ],
            "data_flow": [
                {"from": "svc.wire.in.payment", "to": "svc.adapter.payment", "transforms": "wire-to-model"}
            ],
            "bottlenecks": [],
            "security_findings": [],
            "coupling_issues": [],
        }
        result = validate_flow_analysis(json.dumps(data))
        assert result["flow_name"] == "payment"

    def test_rejects_missing_required_field(self) -> None:
        data = {"flow_name": "payment"}
        with pytest.raises(ValidationError, match="missing required"):
            validate_flow_analysis(json.dumps(data))

    def test_rejects_invalid_json(self) -> None:
        with pytest.raises(ValidationError, match="Invalid JSON"):
            validate_flow_analysis("not json {{{")

    def test_rejects_namespace_missing_name(self) -> None:
        data = {
            "flow_name": "x",
            "entry_points": [],
            "exit_points": [],
            "namespaces": [{"layer": "logic", "role": "x", "side_effects": [], "security_notes": None}],
            "data_flow": [],
            "bottlenecks": [],
            "security_findings": [],
            "coupling_issues": [],
        }
        with pytest.raises(ValidationError, match="namespace.*missing.*name"):
            validate_flow_analysis(json.dumps(data))

    def test_rejects_data_flow_missing_from(self) -> None:
        data = {
            "flow_name": "x",
            "entry_points": [],
            "exit_points": [],
            "namespaces": [],
            "data_flow": [{"to": "b", "transforms": "none"}],
            "bottlenecks": [],
            "security_findings": [],
            "coupling_issues": [],
        }
        with pytest.raises(ValidationError, match="data_flow.*missing.*from"):
            validate_flow_analysis(json.dumps(data))

    def test_extracts_json_from_markdown(self) -> None:
        data = {
            "flow_name": "payment",
            "entry_points": [],
            "exit_points": [],
            "namespaces": [],
            "data_flow": [],
            "bottlenecks": [],
            "security_findings": [],
            "coupling_issues": [],
        }
        wrapped = f"Here is the analysis:\n```json\n{json.dumps(data)}\n```"
        result = validate_flow_analysis(wrapped)
        assert result["flow_name"] == "payment"


class TestSchemaConstant:

    def test_schema_has_required_fields(self) -> None:
        required = {"flow_name", "entry_points", "exit_points", "namespaces",
                     "data_flow", "bottlenecks", "security_findings", "coupling_issues"}
        assert required == set(FLOW_ANALYSIS_SCHEMA["required"])
