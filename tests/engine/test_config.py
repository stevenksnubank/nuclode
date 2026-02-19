"""Tests for config loading, model resolution, and env var overrides."""

from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest

from engine.config import (
    MODEL_REGISTRY,
    EngineConfig,
    GuardrailsConfig,
    load_config,
    resolve_model,
)


class TestResolveModel:

    def test_resolve_known_alias(self) -> None:
        assert resolve_model("latest-opus") == "claude-opus-4-6"

    def test_resolve_all_aliases(self) -> None:
        for alias, expected in MODEL_REGISTRY.items():
            assert resolve_model(alias) == expected

    def test_passthrough_concrete_id(self) -> None:
        assert resolve_model("claude-opus-4-6") == "claude-opus-4-6"

    def test_unknown_alias_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown model alias"):
            resolve_model("nonexistent-model")

    def test_error_lists_known_aliases(self) -> None:
        with pytest.raises(ValueError, match="latest-opus"):
            resolve_model("bad")


class TestGuardrailsConfig:

    def test_defaults(self) -> None:
        g = GuardrailsConfig()
        assert g.enabled is True
        assert g.max_cost_per_run_usd == Decimal("50.00")
        assert g.warn_cost_threshold_usd == Decimal("30.00")
        assert g.max_sub_lm_calls == 500

    def test_frozen(self) -> None:
        g = GuardrailsConfig()
        with pytest.raises(AttributeError):
            g.enabled = False  # type: ignore[misc]


class TestEngineConfig:

    def test_frozen(self) -> None:
        config = EngineConfig(
            root_model="claude-opus-4-6",
            root_extended_thinking=True,
            root_max_iterations=30,
            sub_lm_high_model="claude-sonnet-4-6",
            sub_lm_low_model="claude-haiku-4-5-20251001",
            threshold_tokens=50000,
            guardrails=GuardrailsConfig(),
        )
        with pytest.raises(AttributeError):
            config.root_model = "changed"  # type: ignore[misc]


class TestLoadConfig:

    def test_loads_default_config(self) -> None:
        config = load_config()
        assert config.root_model == "claude-opus-4-6"
        assert config.root_extended_thinking is True
        assert config.root_max_iterations == 30
        assert config.sub_lm_high_model == "claude-sonnet-4-6"
        assert config.sub_lm_low_model == "claude-haiku-4-5-20251001"
        assert config.threshold_tokens == 50000
        assert config.guardrails.enabled is True

    def test_missing_config_uses_defaults(self, tmp_path: Path) -> None:
        config = load_config(tmp_path / "nonexistent.yaml")
        assert config.root_model == "claude-opus-4-6"
        assert config.threshold_tokens == 50000

    def test_env_var_overrides_root_model(self) -> None:
        with patch.dict(os.environ, {"NUCLODE_ROOT_LM_MODEL": "claude-opus-4-6"}):
            config = load_config()
            assert config.root_model == "claude-opus-4-6"

    def test_env_var_overrides_sub_lm_high(self) -> None:
        with patch.dict(os.environ, {"NUCLODE_SUB_LM_HIGH_MODEL": "latest-opus"}):
            config = load_config()
            assert config.sub_lm_high_model == "claude-opus-4-6"

    def test_env_var_overrides_sub_lm_low(self) -> None:
        with patch.dict(os.environ, {"NUCLODE_SUB_LM_LOW_MODEL": "latest-sonnet"}):
            config = load_config()
            assert config.sub_lm_low_model == "claude-sonnet-4-6"

    def test_env_var_disables_guardrails(self) -> None:
        with patch.dict(os.environ, {"NUCLODE_GUARDRAILS_ENABLED": "false"}):
            config = load_config()
            assert config.guardrails.enabled is False

    def test_custom_yaml_config(self, tmp_path: Path) -> None:
        custom = tmp_path / "custom.yaml"
        custom.write_text(
            "engine:\n"
            "  root_lm:\n"
            "    model: latest-haiku\n"
            "    extended_thinking: false\n"
            "    max_iterations: 10\n"
            "  threshold_tokens: 25000\n"
            "guardrails:\n"
            "  enabled: false\n"
            "  max_cost_per_run_usd: 10.00\n",
            encoding="utf-8",
        )
        config = load_config(custom)
        assert config.root_model == "claude-haiku-4-5-20251001"
        assert config.root_extended_thinking is False
        assert config.root_max_iterations == 10
        assert config.threshold_tokens == 25000
        assert config.guardrails.enabled is False
        assert config.guardrails.max_cost_per_run_usd == Decimal("10.00")
