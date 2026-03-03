"""Model registry and configuration loading for the nuclode engine."""

from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import yaml

MODEL_REGISTRY: dict[str, str] = {
    "latest-opus": "anthropic/claude-opus-4-6",
    "latest-sonnet": "anthropic/claude-sonnet-4-6",
    "latest-haiku": "anthropic/claude-haiku-4-5-20251001",
}

_DEFAULT_CONFIG_PATH = Path(__file__).parent / "config.yaml"


def resolve_model(alias: str) -> str:
    """Resolve a model alias to its concrete model ID.

    Args:
        alias: Model alias (e.g., "latest-opus") or concrete ID.

    Returns:
        Concrete model ID string.

    Raises:
        ValueError: If alias is not found in registry and doesn't look like a concrete ID.
    """
    if alias in MODEL_REGISTRY:
        return MODEL_REGISTRY[alias]
    if alias.startswith("claude-") or alias.startswith("anthropic/"):
        return alias
    raise ValueError(
        f"Unknown model alias: {alias!r}. "
        f"Known aliases: {sorted(MODEL_REGISTRY.keys())}"
    )


@dataclass(frozen=True)
class GuardrailsConfig:
    """Cost guardrail configuration."""

    enabled: bool = True
    max_cost_per_run_usd: Decimal = Decimal("50.00")
    warn_cost_threshold_usd: Decimal = Decimal("30.00")
    max_sub_lm_calls: int = 500


@dataclass(frozen=True)
class EngineConfig:
    """Complete engine configuration."""

    root_model: str
    root_extended_thinking: bool
    root_max_iterations: int
    sub_lm_high_model: str
    sub_lm_low_model: str
    threshold_tokens: int
    guardrails: GuardrailsConfig


def load_config(config_path: Path | None = None) -> EngineConfig:
    """Load engine configuration from YAML, with env var overrides.

    Args:
        config_path: Path to config YAML. Defaults to engine/config.yaml.

    Returns:
        Frozen EngineConfig dataclass.

    Raises:
        FileNotFoundError: If config file doesn't exist and no defaults available.
    """
    path = config_path or _DEFAULT_CONFIG_PATH

    if path.exists():
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    else:
        raw = {}

    engine = raw.get("engine", {})
    root_lm = engine.get("root_lm", {})
    sub_lm = engine.get("sub_lm", {})
    guardrails_raw = raw.get("guardrails", {})

    # Resolve models with env var overrides
    root_model_alias = os.environ.get(
        "NUCLODE_ROOT_LM_MODEL",
        root_lm.get("model", "latest-opus"),
    )
    sub_high_alias = os.environ.get(
        "NUCLODE_SUB_LM_HIGH_MODEL",
        sub_lm.get("high_ambiguity", {}).get("model", "latest-sonnet"),
    )
    sub_low_alias = os.environ.get(
        "NUCLODE_SUB_LM_LOW_MODEL",
        sub_lm.get("low_ambiguity", {}).get("model", "latest-haiku"),
    )

    # Guardrails enabled check includes env var
    guardrails_enabled = guardrails_raw.get("enabled", True)
    if os.environ.get("NUCLODE_GUARDRAILS_ENABLED", "").lower() == "false":
        guardrails_enabled = False

    guardrails = GuardrailsConfig(
        enabled=guardrails_enabled,
        max_cost_per_run_usd=Decimal(str(guardrails_raw.get("max_cost_per_run_usd", "50.00"))),
        warn_cost_threshold_usd=Decimal(str(guardrails_raw.get("warn_cost_threshold_usd", "30.00"))),
        max_sub_lm_calls=int(guardrails_raw.get("max_sub_lm_calls", 500)),
    )

    return EngineConfig(
        root_model=resolve_model(root_model_alias),
        root_extended_thinking=root_lm.get("extended_thinking", True),
        root_max_iterations=int(root_lm.get("max_iterations", 30)),
        sub_lm_high_model=resolve_model(sub_high_alias),
        sub_lm_low_model=resolve_model(sub_low_alias),
        threshold_tokens=int(engine.get("threshold_tokens", 50000)),
        guardrails=guardrails,
    )
