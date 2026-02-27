"""Tests for analysis prompts."""

from __future__ import annotations

import pytest

from knowledge.recipes.codebase_analysis.prompts import (
    LAYER_PROMPTS,
    build_analysis_prompt,
    get_layer_prompt,
)


class TestBuildAnalysisPrompt:

    def test_includes_project_name(self) -> None:
        prompt = build_analysis_prompt("my-service", {"namespaces": []})
        assert "my-service" in prompt

    def test_includes_structure_data(self) -> None:
        structure = {"namespaces": [{"name": "nu.customer.logic.payment"}]}
        prompt = build_analysis_prompt("svc", structure)
        assert "nu.customer.logic.payment" in prompt

    def test_includes_tool_descriptions(self) -> None:
        prompt = build_analysis_prompt("svc", {})
        assert "llm_query" in prompt
        assert "create_bead" in prompt
        assert "link_beads" in prompt
        assert "FINAL()" in prompt

    def test_includes_tag_taxonomy(self) -> None:
        prompt = build_analysis_prompt("svc", {})
        assert "diplomat-logic" in prompt
        assert "has-side-effects" in prompt
        assert "structure" in prompt

    def test_includes_bead_body_format(self) -> None:
        prompt = build_analysis_prompt("svc", {})
        assert "## Purpose" in prompt
        assert "## Key Functions" in prompt
        assert "## Security Surface" in prompt

    def test_security_mode_appends_instructions(self) -> None:
        prompt = build_analysis_prompt("svc", {}, mode="security")
        assert "Security Mode" in prompt
        assert "tier='high'" in prompt

    def test_structure_mode_no_security_section(self) -> None:
        prompt = build_analysis_prompt("svc", {}, mode="structure")
        assert "Security Mode" not in prompt


class TestGetLayerPrompt:

    def test_known_layers(self) -> None:
        for layer in ("logic", "model", "controller", "adapter", "wire"):
            prompt = get_layer_prompt(layer)
            assert "{namespace}" in prompt
            assert "{source}" in prompt

    def test_logic_is_deep(self) -> None:
        prompt = get_layer_prompt("logic")
        assert "deeply" in prompt.lower() or "deep" in prompt.lower()
        assert "Business rules" in prompt

    def test_adapter_is_light(self) -> None:
        prompt = get_layer_prompt("adapter")
        assert "lightly" in prompt.lower() or "light" in prompt.lower()

    def test_unknown_layer_returns_generic(self) -> None:
        prompt = get_layer_prompt("unknown-layer")
        assert "{namespace}" in prompt
        assert "{source}" in prompt

    def test_all_layer_prompts_have_placeholders(self) -> None:
        for layer, prompt in LAYER_PROMPTS.items():
            assert "{namespace}" in prompt, f"{layer} missing {{namespace}}"
            assert "{source}" in prompt, f"{layer} missing {{source}}"
