"""Runtime cost estimation and guardrail enforcement for the nuclode engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum

from knowledge.engine.config import GuardrailsConfig


class GuardrailStatus(Enum):
    OK = "ok"
    WARNING = "warning"
    EXCEEDED = "exceeded"


# Pricing per million tokens (approximate, for estimation only).
MODEL_PRICING: dict[str, dict[str, Decimal]] = {
    "anthropic/claude-opus-4-6": {"input": Decimal("15.00"), "output": Decimal("75.00")},
    "anthropic/claude-sonnet-4-6": {"input": Decimal("3.00"), "output": Decimal("15.00")},
    "anthropic/claude-haiku-4-5-20251001": {"input": Decimal("1.00"), "output": Decimal("5.00")},
}

# Safe default for unknown models — use Opus pricing (most expensive = conservative).
_DEFAULT_PRICING: dict[str, Decimal] = {"input": Decimal("15.00"), "output": Decimal("75.00")}

_ONE_MILLION = Decimal("1000000")


@dataclass(frozen=True)
class CostSummary:
    """Summary of all costs accumulated during a run."""

    total_cost_usd: Decimal
    total_input_tokens: int
    total_output_tokens: int
    calls_by_model: dict[str, int]
    status: GuardrailStatus


class CostTracker:
    """Tracks API call costs and enforces guardrails during engine runs."""

    def __init__(self, config: GuardrailsConfig) -> None:
        self._config = config
        self._total_input_tokens: int = 0
        self._total_output_tokens: int = 0
        self._total_cost: Decimal = Decimal("0")
        self._calls_by_model: dict[str, int] = {}
        self._sub_lm_calls: int = 0

    def record(self, model: str, input_tokens: int, output_tokens: int) -> None:
        """Record a completed API call and update running totals."""
        pricing = MODEL_PRICING.get(model, _DEFAULT_PRICING)
        input_cost = pricing["input"] * Decimal(input_tokens) / _ONE_MILLION
        output_cost = pricing["output"] * Decimal(output_tokens) / _ONE_MILLION

        self._total_input_tokens += input_tokens
        self._total_output_tokens += output_tokens
        self._total_cost += input_cost + output_cost
        self._calls_by_model[model] = self._calls_by_model.get(model, 0) + 1
        self._sub_lm_calls += 1

    @property
    def estimated_cost_usd(self) -> Decimal:
        """Current estimated total cost."""
        return self._total_cost

    @property
    def sub_lm_call_count(self) -> int:
        """Total sub-LM calls recorded so far."""
        return self._sub_lm_calls

    def check_guardrails(self) -> GuardrailStatus:
        """Check current state against guardrails.

        Returns OK, WARNING, or EXCEEDED. If guardrails disabled, always OK.
        """
        if not self._config.enabled:
            return GuardrailStatus.OK

        if self._total_cost >= self._config.max_cost_per_run_usd:
            return GuardrailStatus.EXCEEDED

        if self._sub_lm_calls >= self._config.max_sub_lm_calls:
            return GuardrailStatus.EXCEEDED

        if self._total_cost >= self._config.warn_cost_threshold_usd:
            return GuardrailStatus.WARNING

        return GuardrailStatus.OK

    def summary(self) -> CostSummary:
        """Return a summary of all costs accumulated so far."""
        return CostSummary(
            total_cost_usd=self._total_cost,
            total_input_tokens=self._total_input_tokens,
            total_output_tokens=self._total_output_tokens,
            calls_by_model=dict(self._calls_by_model),
            status=self.check_guardrails(),
        )
