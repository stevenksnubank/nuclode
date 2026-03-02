"""Tests for the deterministic analysis pipeline."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from knowledge.backends.base import NamespaceInfo
from knowledge.engine.chunking import FlowGroup
from knowledge.engine.config import EngineConfig, GuardrailsConfig
from knowledge.engine.pipeline import PipelineResult, PipelineRunner


@pytest.fixture
def config() -> EngineConfig:
    return EngineConfig(
        root_model="anthropic/claude-opus-4-6",
        root_extended_thinking=False,
        root_max_iterations=5,
        sub_lm_high_model="anthropic/claude-sonnet-4-6",
        sub_lm_low_model="anthropic/claude-haiku-4-5-20251001",
        threshold_tokens=50000,
        guardrails=GuardrailsConfig(
            enabled=True,
            max_cost_per_run_usd=Decimal("10.00"),
            warn_cost_threshold_usd=Decimal("5.00"),
            max_sub_lm_calls=100,
        ),
    )


def _valid_response(flow_name: str = "flow-test") -> str:
    return json.dumps({
        "flow_name": flow_name,
        "entry_points": ["svc.wire.in.test"],
        "exit_points": ["svc.logic.test"],
        "namespaces": [
            {"name": "svc.logic.test", "layer": "logic",
             "role": "Core test logic", "side_effects": [], "security_notes": None}
        ],
        "data_flow": [],
        "bottlenecks": [],
        "security_findings": [],
        "coupling_issues": [],
    })


def _make_group(name: str = "flow-a") -> FlowGroup:
    return FlowGroup(
        name=name, namespaces=[], entry_points=[], exit_points=[], internal_deps={},
    )


class TestPipelineRunner:

    @patch.object(PipelineRunner, "_call_sub_lm_for_group")
    def test_runs_all_groups(self, mock_call: MagicMock, config: EngineConfig) -> None:
        mock_call.return_value = _valid_response()
        groups = [_make_group("flow-a"), _make_group("flow-b")]
        runner = PipelineRunner(config)
        result = runner.run(groups, source_by_namespace={})
        assert result.status == "completed"
        assert len(result.analyses) == 2
        assert mock_call.call_count == 2

    @patch.object(PipelineRunner, "_call_sub_lm_for_group")
    def test_validation_failure_retries_once(self, mock_call: MagicMock, config: EngineConfig) -> None:
        mock_call.side_effect = ["not json", _valid_response()]
        groups = [_make_group()]
        runner = PipelineRunner(config)
        result = runner.run(groups, source_by_namespace={})
        assert result.status == "completed"
        assert mock_call.call_count == 2  # first fails validation, retry succeeds

    @patch.object(PipelineRunner, "_call_sub_lm_for_group")
    def test_persistent_validation_failure_captured(self, mock_call: MagicMock, config: EngineConfig) -> None:
        mock_call.return_value = "not json at all"
        groups = [_make_group()]
        runner = PipelineRunner(config)
        result = runner.run(groups, source_by_namespace={})
        assert result.status == "completed_with_errors"
        assert len(result.validation_errors) == 1

    @patch.object(PipelineRunner, "_call_sub_lm_for_group")
    def test_cost_tracked(self, mock_call: MagicMock, config: EngineConfig) -> None:
        mock_call.return_value = _valid_response()
        groups = [_make_group()]
        runner = PipelineRunner(config)
        result = runner.run(groups, source_by_namespace={})
        assert "total_cost_usd" in result.cost_summary

    @patch.object(PipelineRunner, "_call_sub_lm_for_group")
    def test_empty_groups(self, mock_call: MagicMock, config: EngineConfig) -> None:
        runner = PipelineRunner(config)
        result = runner.run([], source_by_namespace={})
        assert result.status == "completed"
        assert result.groups_total == 0
        mock_call.assert_not_called()

    @patch.object(PipelineRunner, "_call_sub_lm_for_group")
    def test_groups_succeeded_count(self, mock_call: MagicMock, config: EngineConfig) -> None:
        mock_call.side_effect = [_valid_response("flow-a"), "bad json", "bad json"]
        groups = [_make_group("flow-a"), _make_group("flow-b")]
        runner = PipelineRunner(config)
        result = runner.run(groups, source_by_namespace={})
        assert result.groups_total == 2
        assert result.groups_succeeded == 1


class TestPipelineResult:

    def test_frozen(self) -> None:
        result = PipelineResult(
            status="completed", analyses=[], validation_errors=[],
            cost_summary={}, groups_total=0, groups_succeeded=0,
        )
        with pytest.raises(AttributeError):
            result.status = "changed"  # type: ignore[misc]
