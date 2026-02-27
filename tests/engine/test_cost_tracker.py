"""Tests for cost tracking and guardrail enforcement."""

from __future__ import annotations

from decimal import Decimal

import pytest

from knowledge.engine.config import GuardrailsConfig
from knowledge.engine.cost_tracker import CostTracker, GuardrailStatus, MODEL_PRICING


@pytest.fixture
def default_guardrails() -> GuardrailsConfig:
    return GuardrailsConfig()


@pytest.fixture
def tight_guardrails() -> GuardrailsConfig:
    return GuardrailsConfig(
        enabled=True,
        max_cost_per_run_usd=Decimal("1.00"),
        warn_cost_threshold_usd=Decimal("0.50"),
        max_sub_lm_calls=5,
    )


@pytest.fixture
def disabled_guardrails() -> GuardrailsConfig:
    return GuardrailsConfig(enabled=False)


class TestCostTrackerRecording:

    def test_initial_state(self, default_guardrails: GuardrailsConfig) -> None:
        tracker = CostTracker(default_guardrails)
        assert tracker.estimated_cost_usd == Decimal("0")
        assert tracker.sub_lm_call_count == 0

    def test_record_updates_totals(self, default_guardrails: GuardrailsConfig) -> None:
        tracker = CostTracker(default_guardrails)
        tracker.record("anthropic/claude-haiku-4-5-20251001", input_tokens=1000, output_tokens=500)
        assert tracker.estimated_cost_usd > Decimal("0")
        assert tracker.sub_lm_call_count == 1

    def test_record_accumulates(self, default_guardrails: GuardrailsConfig) -> None:
        tracker = CostTracker(default_guardrails)
        tracker.record("anthropic/claude-haiku-4-5-20251001", input_tokens=1000, output_tokens=500)
        cost1 = tracker.estimated_cost_usd
        tracker.record("anthropic/claude-haiku-4-5-20251001", input_tokens=1000, output_tokens=500)
        assert tracker.estimated_cost_usd == cost1 * 2
        assert tracker.sub_lm_call_count == 2

    def test_haiku_cost_calculation(self, default_guardrails: GuardrailsConfig) -> None:
        tracker = CostTracker(default_guardrails)
        # 1M input tokens at $1/M + 1M output tokens at $5/M = $6.00
        tracker.record("anthropic/claude-haiku-4-5-20251001", input_tokens=1_000_000, output_tokens=1_000_000)
        assert tracker.estimated_cost_usd == Decimal("6.00")

    def test_opus_cost_calculation(self, default_guardrails: GuardrailsConfig) -> None:
        tracker = CostTracker(default_guardrails)
        # 1M input at $15/M + 1M output at $75/M = $90.00
        tracker.record("anthropic/claude-opus-4-6", input_tokens=1_000_000, output_tokens=1_000_000)
        assert tracker.estimated_cost_usd == Decimal("90.00")

    def test_unknown_model_uses_default_pricing(self, default_guardrails: GuardrailsConfig) -> None:
        tracker = CostTracker(default_guardrails)
        # Unknown model should use conservative (Opus) pricing, not crash
        tracker.record("claude-future-model-99", input_tokens=1000, output_tokens=1000)
        assert tracker.estimated_cost_usd > Decimal("0")

    def test_calls_by_model_tracked(self, default_guardrails: GuardrailsConfig) -> None:
        tracker = CostTracker(default_guardrails)
        tracker.record("anthropic/claude-haiku-4-5-20251001", input_tokens=100, output_tokens=100)
        tracker.record("anthropic/claude-haiku-4-5-20251001", input_tokens=100, output_tokens=100)
        tracker.record("anthropic/claude-sonnet-4-6", input_tokens=100, output_tokens=100)
        summary = tracker.summary()
        assert summary.calls_by_model["anthropic/claude-haiku-4-5-20251001"] == 2
        assert summary.calls_by_model["anthropic/claude-sonnet-4-6"] == 1


class TestGuardrailChecks:

    def test_ok_status(self, tight_guardrails: GuardrailsConfig) -> None:
        tracker = CostTracker(tight_guardrails)
        assert tracker.check_guardrails() == GuardrailStatus.OK

    def test_warning_at_threshold(self, tight_guardrails: GuardrailsConfig) -> None:
        tracker = CostTracker(tight_guardrails)
        # Haiku: $1/M input + $5/M output. To hit $0.50 warning:
        # 83333 input tokens * $1/M = $0.083, need output tokens
        # Use Opus for faster cost accumulation: $15/M input
        tracker.record("anthropic/claude-opus-4-6", input_tokens=33_334, output_tokens=0)
        # ~$0.50 in input costs
        assert tracker.check_guardrails() == GuardrailStatus.WARNING

    def test_exceeded_at_max_cost(self, tight_guardrails: GuardrailsConfig) -> None:
        tracker = CostTracker(tight_guardrails)
        tracker.record("anthropic/claude-opus-4-6", input_tokens=66_667, output_tokens=0)
        # ~$1.00 in costs
        assert tracker.check_guardrails() == GuardrailStatus.EXCEEDED

    def test_exceeded_at_max_calls(self, tight_guardrails: GuardrailsConfig) -> None:
        tracker = CostTracker(tight_guardrails)
        for _ in range(5):
            tracker.record("anthropic/claude-haiku-4-5-20251001", input_tokens=1, output_tokens=1)
        assert tracker.check_guardrails() == GuardrailStatus.EXCEEDED

    def test_disabled_guardrails_always_ok(self, disabled_guardrails: GuardrailsConfig) -> None:
        tracker = CostTracker(disabled_guardrails)
        tracker.record("anthropic/claude-opus-4-6", input_tokens=10_000_000, output_tokens=10_000_000)
        assert tracker.check_guardrails() == GuardrailStatus.OK


class TestCostSummary:

    def test_summary_structure(self, default_guardrails: GuardrailsConfig) -> None:
        tracker = CostTracker(default_guardrails)
        tracker.record("anthropic/claude-haiku-4-5-20251001", input_tokens=1000, output_tokens=500)
        summary = tracker.summary()
        assert summary.total_input_tokens == 1000
        assert summary.total_output_tokens == 500
        assert summary.total_cost_usd > Decimal("0")
        assert summary.status == GuardrailStatus.OK
        assert "anthropic/claude-haiku-4-5-20251001" in summary.calls_by_model

    def test_empty_summary(self, default_guardrails: GuardrailsConfig) -> None:
        tracker = CostTracker(default_guardrails)
        summary = tracker.summary()
        assert summary.total_cost_usd == Decimal("0")
        assert summary.total_input_tokens == 0
        assert summary.total_output_tokens == 0
        assert summary.calls_by_model == {}
