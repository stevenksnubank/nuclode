"""Two-stage decision gate for the nuclode engine.

Stage 1: Token threshold (fast, free) -- estimate tokens, compare to threshold.
Stage 2: Opus override (smart) -- Opus sees structural summary and can override Stage 1.

The actual Opus API call for Stage 2 happens in the runner, not here.
This module implements the decision logic and accepts the override result.
"""

from __future__ import annotations

from dataclasses import dataclass

# Approximate characters per token for estimation.
# Conservative estimate aligned with Claude tokenizer averages.
_CHARS_PER_TOKEN: int = 4

# Default threshold in tokens. Below this, a single Opus call is usually reliable.
# Above this, sub-LM fan-out prevents information loss from single-pass analysis.
DEFAULT_THRESHOLD: int = 50_000


def estimate_tokens(context: str | dict) -> int:
    """Estimate token count from text or a context dict.

    Uses a simple heuristic of ~4 characters per token.

    Args:
        context: Either a plain string, or a dict mapping keys (e.g. file paths)
                 to string values (e.g. source code). If a dict, token counts
                 are summed across all values.

    Returns:
        Estimated token count. Returns 0 for empty input.

    Raises:
        TypeError: If context is neither a str nor a dict.
    """
    if isinstance(context, str):
        return len(context) // _CHARS_PER_TOKEN

    if isinstance(context, dict):
        total_chars = sum(len(str(v)) for v in context.values())
        return total_chars // _CHARS_PER_TOKEN

    raise TypeError(
        f"context must be str or dict, got {type(context).__name__}"
    )


def should_fan_out(token_count: int, threshold: int = DEFAULT_THRESHOLD) -> bool:
    """Stage 1: simple threshold check.

    Args:
        token_count: Estimated token count from estimate_tokens().
        threshold: Token threshold. Defaults to DEFAULT_THRESHOLD (50,000).

    Returns:
        True if token_count >= threshold (use sub-LM fan-out).
        False if token_count < threshold (single Opus call).
    """
    return token_count >= threshold


@dataclass(frozen=True)
class GateDecision:
    """Result of the two-stage decision gate.

    Attributes:
        fan_out: True = use sub-LM fan-out, False = single Opus call.
        token_count: Estimated token count for the input context.
        stage: Which stage produced the decision -- "threshold" or "opus_override".
        reason: Human-readable explanation of the routing decision.
    """

    fan_out: bool
    token_count: int
    stage: str
    reason: str


def route_task(
    context: str | dict,
    structure_summary: dict | None = None,
    threshold: int = DEFAULT_THRESHOLD,
) -> GateDecision:
    """Two-stage routing decision.

    Stage 1: Token threshold -- below threshold defaults to direct Opus call,
             above threshold defaults to sub-LM fan-out.

    Stage 2: If structure_summary is provided and contains an "opus_override"
             key with a boolean value, that value overrides Stage 1. The actual
             Opus API call that populates this field happens in the runner.

    Args:
        context: The input context (string or dict of path->source).
        structure_summary: Optional dict from the runner's Opus override call.
                          If it contains {"opus_override": bool}, that bool
                          is used as the fan_out decision. An optional
                          "opus_reason" key provides the explanation.
        threshold: Token threshold for Stage 1. Defaults to DEFAULT_THRESHOLD.

    Returns:
        A GateDecision describing the routing result.

    Raises:
        TypeError: If context is neither a str nor a dict.
    """
    token_count = estimate_tokens(context)

    # Stage 2: Opus override takes precedence when available.
    if structure_summary is not None and "opus_override" in structure_summary:
        opus_fan_out = bool(structure_summary["opus_override"])
        opus_reason = structure_summary.get(
            "opus_reason",
            "Opus override: fan-out" if opus_fan_out else "Opus override: direct",
        )
        return GateDecision(
            fan_out=opus_fan_out,
            token_count=token_count,
            stage="opus_override",
            reason=opus_reason,
        )

    # Stage 1: Token threshold.
    if should_fan_out(token_count, threshold):
        return GateDecision(
            fan_out=True,
            token_count=token_count,
            stage="threshold",
            reason=(
                f"Token count ({token_count:,}) >= threshold ({threshold:,}); "
                f"defaulting to sub-LM fan-out"
            ),
        )

    return GateDecision(
        fan_out=False,
        token_count=token_count,
        stage="threshold",
        reason=(
            f"Token count ({token_count:,}) < threshold ({threshold:,}); "
            f"defaulting to single Opus call"
        ),
    )
