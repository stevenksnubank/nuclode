"""Tests for the engine runner / REPL loop.

Tests mock the Anthropic API — no real API calls are made.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from engine.config import EngineConfig, GuardrailsConfig
from engine.gate import GateDecision
from engine.runner import EngineRunner, _strip_code_fences


@pytest.fixture
def config() -> EngineConfig:
    return EngineConfig(
        root_model="claude-opus-4-6",
        root_extended_thinking=False,  # disabled for simpler test mocking
        root_max_iterations=5,
        sub_lm_high_model="claude-sonnet-4-6",
        sub_lm_low_model="claude-haiku-4-5-20251001",
        threshold_tokens=50000,
        guardrails=GuardrailsConfig(
            enabled=True,
            max_cost_per_run_usd=Decimal("10.00"),
            warn_cost_threshold_usd=Decimal("5.00"),
            max_sub_lm_calls=10,
        ),
    )


@pytest.fixture
def runner(config: EngineConfig) -> EngineRunner:
    return EngineRunner(config)


class TestStripCodeFences:

    def test_strips_python_fences(self) -> None:
        code = "```python\nprint('hello')\n```"
        assert _strip_code_fences(code) == "print('hello')"

    def test_strips_plain_fences(self) -> None:
        code = "```\nprint('hello')\n```"
        assert _strip_code_fences(code) == "print('hello')"

    def test_no_fences_unchanged(self) -> None:
        code = "print('hello')"
        assert _strip_code_fences(code) == "print('hello')"

    def test_empty_string(self) -> None:
        assert _strip_code_fences("") == ""

    def test_multiline_code(self) -> None:
        code = "```python\nx = 1\ny = 2\nprint(x + y)\n```"
        assert _strip_code_fences(code) == "x = 1\ny = 2\nprint(x + y)"


class TestRunDirect:
    """Test the below-threshold direct LM call path."""

    @patch.object(EngineRunner, "_call_root_lm")
    def test_small_context_routes_direct(self, mock_lm: MagicMock, runner: EngineRunner) -> None:
        mock_lm.return_value = "Analysis result"
        result = runner.run("small context")

        assert result.status == "completed"
        assert result.iterations == 1
        assert result.gate_decision.fan_out is False
        assert result.output == "Analysis result"

    @patch.object(EngineRunner, "_call_root_lm")
    def test_direct_error_returns_error_status(self, mock_lm: MagicMock, runner: EngineRunner) -> None:
        mock_lm.side_effect = RuntimeError("API error")
        result = runner.run("small context")

        assert result.status == "error"
        assert "API error" in result.error


class TestRunReplLoop:
    """Test the REPL loop path."""

    @patch.object(EngineRunner, "_call_root_lm")
    def test_final_terminates_loop(self, mock_lm: MagicMock, runner: EngineRunner) -> None:
        # Root LM returns code that calls FINAL()
        mock_lm.return_value = 'FINAL("done")'

        result = runner.run(
            "x" * 200_001,  # above 50K token threshold
            custom_tools={},
            system_prompt="Analyze this.",
        )

        assert result.status == "completed"
        assert result.output == "done"
        assert result.iterations == 1

    @patch.object(EngineRunner, "_call_root_lm")
    def test_max_iterations_stops_loop(self, mock_lm: MagicMock, runner: EngineRunner) -> None:
        # Root LM never calls FINAL
        mock_lm.return_value = 'print("still working")'

        result = runner.run(
            "x" * 200_001,
            custom_tools={},
            system_prompt="Analyze.",
        )

        assert result.status == "max_iterations"
        assert result.iterations == 5  # matches config.root_max_iterations

    @patch.object(EngineRunner, "_call_root_lm")
    def test_code_error_continues_loop(self, mock_lm: MagicMock, runner: EngineRunner) -> None:
        # First call raises, second calls FINAL
        mock_lm.side_effect = [
            "1/0",  # ZeroDivisionError
            'FINAL("recovered")',
        ]

        result = runner.run(
            "x" * 200_001,
            custom_tools={},
            system_prompt="Analyze.",
        )

        assert result.status == "completed"
        assert result.output == "recovered"
        assert result.iterations == 2

    @patch.object(EngineRunner, "_call_root_lm")
    def test_custom_tools_available_in_namespace(self, mock_lm: MagicMock, runner: EngineRunner) -> None:
        # Root LM code calls a custom tool
        mock_lm.return_value = 'result = my_tool("arg")\nFINAL(result)'

        tool_fn = MagicMock(return_value="tool_result")
        custom_tools = {
            "my_tool": {"tool": tool_fn, "description": "A test tool"},
        }

        result = runner.run(
            "x" * 200_001,
            custom_tools=custom_tools,
            system_prompt="Use tools.",
        )

        assert result.status == "completed"
        assert result.output == "tool_result"
        tool_fn.assert_called_once_with("arg")

    @patch.object(EngineRunner, "_call_root_lm")
    def test_print_captures_output(self, mock_lm: MagicMock, runner: EngineRunner) -> None:
        # First iteration prints, second calls FINAL
        mock_lm.side_effect = [
            'print("hello world")',
            'FINAL("done")',
        ]

        result = runner.run(
            "x" * 200_001,
            custom_tools={},
            system_prompt="Analyze.",
        )

        assert result.status == "completed"
        assert result.iterations == 2


class TestBudgetGuardrails:
    """Test that guardrails stop the run when exceeded."""

    @patch.object(EngineRunner, "_call_root_lm")
    def test_budget_exceeded_stops_loop(self, mock_lm: MagicMock, config: EngineConfig) -> None:
        runner = EngineRunner(config)
        # Simulate expensive calls by pre-loading the cost tracker
        runner._cost_tracker.record("claude-opus-4-6", input_tokens=1_000_000, output_tokens=0)
        # Now cost is ~$15, exceeds max of $10

        mock_lm.return_value = 'print("should not run")'

        result = runner.run(
            "x" * 200_001,
            custom_tools={},
            system_prompt="Analyze.",
        )

        assert result.status == "budget_exceeded"


class TestSubLmCalls:
    """Test sub-LM call dispatch."""

    @patch.object(EngineRunner, "_call_root_lm")
    @patch.object(EngineRunner, "_call_sub_lm")
    def test_llm_query_in_code(self, mock_sub: MagicMock, mock_root: MagicMock, runner: EngineRunner) -> None:
        mock_sub.return_value = "sub result"
        mock_root.return_value = 'result = llm_query("analyze this", tier="high")\nFINAL(result)'

        result = runner.run(
            "x" * 200_001,
            custom_tools={},
            system_prompt="Analyze.",
        )

        assert result.status == "completed"
        assert result.output == "sub result"
        mock_sub.assert_called_once_with("analyze this", "high")

    @patch.object(EngineRunner, "_call_root_lm")
    @patch.object(EngineRunner, "_call_sub_lm")
    def test_llm_query_batched_in_code(self, mock_sub: MagicMock, mock_root: MagicMock, runner: EngineRunner) -> None:
        mock_sub.side_effect = ["result1", "result2"]
        mock_root.return_value = (
            'results = llm_query_batched(["prompt1", "prompt2"], tier="low")\n'
            'FINAL(results)'
        )

        result = runner.run(
            "x" * 200_001,
            custom_tools={},
            system_prompt="Analyze.",
        )

        assert result.status == "completed"
        assert result.output == ["result1", "result2"]
        assert mock_sub.call_count == 2


class TestGateDecisionInResult:
    """Verify the gate decision is captured in the result."""

    @patch.object(EngineRunner, "_call_root_lm")
    def test_direct_path_captures_gate(self, mock_lm: MagicMock, runner: EngineRunner) -> None:
        mock_lm.return_value = "result"
        result = runner.run("small")
        assert result.gate_decision.fan_out is False
        assert result.gate_decision.stage == "threshold"

    @patch.object(EngineRunner, "_call_root_lm")
    def test_fan_out_path_captures_gate(self, mock_lm: MagicMock, runner: EngineRunner) -> None:
        mock_lm.return_value = 'FINAL("done")'
        result = runner.run("x" * 200_001)
        assert result.gate_decision.fan_out is True
        assert result.gate_decision.stage == "threshold"
