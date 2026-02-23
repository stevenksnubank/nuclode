"""Tests for the two-stage decision gate.

Covers: string estimation, dict estimation, below threshold, above threshold,
        opus override true/false, empty context, edge cases, type errors,
        and GateDecision immutability.
"""

from __future__ import annotations

import pytest

from engine.gate import (
    DEFAULT_THRESHOLD,
    GateDecision,
    _CHARS_PER_TOKEN,
    estimate_tokens,
    route_task,
    should_fan_out,
)


# ---------------------------------------------------------------------------
# estimate_tokens
# ---------------------------------------------------------------------------


class TestEstimateTokensString:
    """Token estimation from plain string context."""

    def test_empty_string(self) -> None:
        assert estimate_tokens("") == 0

    def test_short_string(self) -> None:
        # 12 chars / 4 = 3 tokens
        assert estimate_tokens("hello world!") == 3

    def test_exact_multiple(self) -> None:
        # 8 chars / 4 = 2 tokens exactly
        text = "abcdefgh"
        assert estimate_tokens(text) == 2

    def test_rounds_down(self) -> None:
        # 5 chars / 4 = 1 (integer division rounds down)
        assert estimate_tokens("abcde") == 1

    def test_single_char(self) -> None:
        # 1 char / 4 = 0
        assert estimate_tokens("x") == 0

    def test_large_string(self) -> None:
        # 200,000 chars / 4 = 50,000 tokens
        text = "x" * 200_000
        assert estimate_tokens(text) == 50_000

    def test_realistic_code_string(self) -> None:
        code = "(defn process-payment [request]\n  (let [amount (:amount request)]\n    amount))\n"
        expected = len(code) // _CHARS_PER_TOKEN
        assert estimate_tokens(code) == expected


class TestEstimateTokensDict:
    """Token estimation from dict context (path -> source code)."""

    def test_empty_dict(self) -> None:
        assert estimate_tokens({}) == 0

    def test_single_entry(self) -> None:
        context = {"src/core.clj": "abcdefgh"}  # 8 chars -> 2 tokens
        assert estimate_tokens(context) == 2

    def test_multiple_entries_summed(self) -> None:
        context = {
            "src/a.clj": "x" * 40,   # 40 chars -> 10 tokens
            "src/b.clj": "y" * 60,   # 60 chars -> 15 tokens
        }
        # Total: 100 chars / 4 = 25
        assert estimate_tokens(context) == 25

    def test_dict_with_empty_values(self) -> None:
        context = {"a.clj": "", "b.clj": ""}
        assert estimate_tokens(context) == 0

    def test_dict_values_converted_to_string(self) -> None:
        # Non-string values are coerced via str()
        context = {"count": 12345}  # str(12345) = "12345", 5 chars -> 1 token
        assert estimate_tokens(context) == 1

    def test_large_dict_context(self) -> None:
        # Simulate a 200-namespace BFF: ~450K tokens worth of source
        context = {f"ns_{i}.clj": "x" * 9_000 for i in range(200)}
        # 200 * 9000 = 1,800,000 chars / 4 = 450,000 tokens
        assert estimate_tokens(context) == 450_000


class TestEstimateTokensTypeError:
    """estimate_tokens rejects invalid types."""

    def test_list_raises_type_error(self) -> None:
        with pytest.raises(TypeError, match="context must be str or dict"):
            estimate_tokens(["not", "valid"])  # type: ignore[arg-type]

    def test_int_raises_type_error(self) -> None:
        with pytest.raises(TypeError, match="context must be str or dict"):
            estimate_tokens(42)  # type: ignore[arg-type]

    def test_none_raises_type_error(self) -> None:
        with pytest.raises(TypeError, match="context must be str or dict"):
            estimate_tokens(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# should_fan_out
# ---------------------------------------------------------------------------


class TestShouldFanOut:
    """Stage 1 threshold check."""

    def test_below_threshold(self) -> None:
        assert should_fan_out(49_999) is False

    def test_at_threshold(self) -> None:
        assert should_fan_out(50_000) is True

    def test_above_threshold(self) -> None:
        assert should_fan_out(100_000) is True

    def test_zero_tokens(self) -> None:
        assert should_fan_out(0) is False

    def test_custom_threshold_below(self) -> None:
        assert should_fan_out(999, threshold=1_000) is False

    def test_custom_threshold_at(self) -> None:
        assert should_fan_out(1_000, threshold=1_000) is True

    def test_custom_threshold_above(self) -> None:
        assert should_fan_out(1_001, threshold=1_000) is True


# ---------------------------------------------------------------------------
# GateDecision
# ---------------------------------------------------------------------------


class TestGateDecision:
    """GateDecision dataclass properties."""

    def test_frozen_immutability(self) -> None:
        decision = GateDecision(
            fan_out=True,
            token_count=60_000,
            stage="threshold",
            reason="test",
        )
        with pytest.raises(AttributeError):
            decision.fan_out = False  # type: ignore[misc]

    def test_fields_accessible(self) -> None:
        decision = GateDecision(
            fan_out=False,
            token_count=1_000,
            stage="opus_override",
            reason="Opus says direct",
        )
        assert decision.fan_out is False
        assert decision.token_count == 1_000
        assert decision.stage == "opus_override"
        assert decision.reason == "Opus says direct"

    def test_equality(self) -> None:
        a = GateDecision(fan_out=True, token_count=50_000, stage="threshold", reason="r")
        b = GateDecision(fan_out=True, token_count=50_000, stage="threshold", reason="r")
        assert a == b


# ---------------------------------------------------------------------------
# route_task
# ---------------------------------------------------------------------------


class TestRouteTaskStage1:
    """Stage 1: threshold-only routing (no structure_summary)."""

    def test_small_string_routes_direct(self) -> None:
        decision = route_task("x" * 40)
        assert decision.fan_out is False
        assert decision.token_count == 10
        assert decision.stage == "threshold"

    def test_large_string_routes_fan_out(self) -> None:
        decision = route_task("x" * 200_000)
        assert decision.fan_out is True
        assert decision.token_count == 50_000
        assert decision.stage == "threshold"

    def test_above_threshold_string(self) -> None:
        decision = route_task("x" * 400_000)
        assert decision.fan_out is True
        assert decision.token_count == 100_000

    def test_empty_string_routes_direct(self) -> None:
        decision = route_task("")
        assert decision.fan_out is False
        assert decision.token_count == 0
        assert decision.stage == "threshold"

    def test_dict_context_below_threshold(self) -> None:
        context = {"a.clj": "x" * 100, "b.clj": "y" * 100}
        decision = route_task(context)
        assert decision.fan_out is False
        assert decision.token_count == 50

    def test_dict_context_above_threshold(self) -> None:
        context = {f"ns_{i}.clj": "x" * 10_000 for i in range(100)}
        decision = route_task(context)
        assert decision.fan_out is True
        assert decision.token_count == 250_000

    def test_empty_dict_routes_direct(self) -> None:
        decision = route_task({})
        assert decision.fan_out is False
        assert decision.token_count == 0

    def test_custom_threshold(self) -> None:
        decision = route_task("x" * 40, threshold=5)
        assert decision.fan_out is True
        assert decision.token_count == 10

    def test_reason_contains_token_count(self) -> None:
        decision = route_task("x" * 40)
        assert "10" in decision.reason
        assert str(DEFAULT_THRESHOLD) in decision.reason.replace(",", "")


class TestRouteTaskStage2:
    """Stage 2: Opus override routing."""

    def test_opus_override_true_forces_fan_out(self) -> None:
        small_context = "x" * 40
        decision = route_task(
            small_context,
            structure_summary={"opus_override": True},
        )
        assert decision.fan_out is True
        assert decision.stage == "opus_override"
        assert decision.token_count == 10

    def test_opus_override_false_forces_direct(self) -> None:
        large_context = "x" * 400_000
        decision = route_task(
            large_context,
            structure_summary={"opus_override": False},
        )
        assert decision.fan_out is False
        assert decision.stage == "opus_override"
        assert decision.token_count == 100_000

    def test_opus_override_with_custom_reason(self) -> None:
        decision = route_task(
            "x" * 40,
            structure_summary={
                "opus_override": True,
                "opus_reason": "Complex protocols detected despite small size",
            },
        )
        assert decision.fan_out is True
        assert decision.reason == "Complex protocols detected despite small size"
        assert decision.stage == "opus_override"

    def test_opus_override_false_with_custom_reason(self) -> None:
        decision = route_task(
            "x" * 400_000,
            structure_summary={
                "opus_override": False,
                "opus_reason": "Flat architecture, I can handle this directly",
            },
        )
        assert decision.fan_out is False
        assert decision.reason == "Flat architecture, I can handle this directly"

    def test_structure_summary_without_opus_override_falls_through(self) -> None:
        decision = route_task(
            "x" * 40,
            structure_summary={"namespaces": 20, "complexity": "low"},
        )
        assert decision.stage == "threshold"
        assert decision.fan_out is False

    def test_empty_structure_summary_falls_through(self) -> None:
        decision = route_task("x" * 40, structure_summary={})
        assert decision.stage == "threshold"

    def test_none_structure_summary_falls_through(self) -> None:
        decision = route_task("x" * 40, structure_summary=None)
        assert decision.stage == "threshold"


class TestRouteTaskTypeErrors:
    """route_task propagates TypeError from estimate_tokens."""

    def test_invalid_context_type(self) -> None:
        with pytest.raises(TypeError, match="context must be str or dict"):
            route_task(12345)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Integration: end-to-end scenarios from the design doc
# ---------------------------------------------------------------------------


class TestDesignDocScenarios:
    """Scenarios from the design doc to verify gate behavior end-to-end."""

    def test_small_service_20_namespaces_direct(self) -> None:
        context = {f"ns_{i}.clj": "x" * 2_250 for i in range(20)}
        decision = route_task(context)
        assert decision.fan_out is False
        assert decision.token_count < DEFAULT_THRESHOLD

    def test_medium_service_35_namespaces_fan_out(self) -> None:
        context = {f"ns_{i}.clj": "x" * 9_000 for i in range(35)}
        decision = route_task(context)
        assert decision.fan_out is True
        assert decision.token_count > DEFAULT_THRESHOLD

    def test_large_bff_200_namespaces_fan_out(self) -> None:
        context = {f"ns_{i}.clj": "x" * 9_000 for i in range(200)}
        decision = route_task(context)
        assert decision.fan_out is True
        assert decision.token_count == 450_000

    def test_60k_tokens_but_opus_says_direct(self) -> None:
        context = "x" * 240_000
        decision = route_task(
            context,
            structure_summary={
                "opus_override": False,
                "opus_reason": "60K tokens but flat architecture -- I got this",
            },
        )
        assert decision.fan_out is False
        assert decision.stage == "opus_override"

    def test_30k_tokens_but_opus_says_fan_out(self) -> None:
        context = "x" * 120_000
        decision = route_task(
            context,
            structure_summary={
                "opus_override": True,
                "opus_reason": "30K tokens but complex protocols -- fan out",
            },
        )
        assert decision.fan_out is True
        assert decision.stage == "opus_override"
