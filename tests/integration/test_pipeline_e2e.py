"""End-to-end integration test for the deterministic pipeline."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from knowledge.backends.clojure_nrepl import ClojureNREPLBackend
from knowledge.engine.chunking import partition_flow_groups
from knowledge.engine.config import EngineConfig, GuardrailsConfig
from knowledge.engine.pipeline import PipelineRunner
from knowledge.engine.schema import validate_flow_analysis
from knowledge.recipes.codebase_analysis.context_loader import load_codebase_context, load_source_map


@pytest.fixture
def clojure_project(tmp_path: Path) -> Path:
    """Create a realistic mini Diplomat service."""
    src = tmp_path / "src" / "svc"
    for sub in ["wire/in", "adapters", "controllers", "logic", "models", "diplomat/datomic"]:
        (src / sub.replace("/", "/")).mkdir(parents=True, exist_ok=True)

    (src / "wire" / "in" / "payment.clj").write_text(
        "(ns svc.wire.in.payment\n  (:require [schema.core :as s]))\n"
        "(s/defschema PaymentRequest {:amount s/Num :customer-id s/Uuid})\n",
        encoding="utf-8",
    )
    (src / "adapters" / "payment.clj").write_text(
        "(ns svc.adapters.payment\n  (:require [svc.wire.in.payment :as wire]))\n"
        "(defn wire->model [req] {:amount (:amount req)})\n",
        encoding="utf-8",
    )
    (src / "controllers" / "payment.clj").write_text(
        "(ns svc.controllers.payment\n"
        "  (:require [svc.logic.payment :as logic]\n"
        "            [svc.adapters.payment :as adapter]\n"
        "            [svc.diplomat.datomic.payment :as ddb]))\n"
        "(defn process! [req datomic]\n"
        "  (let [model (adapter/wire->model req)\n"
        "        result (logic/validate model)]\n"
        "    (ddb/save! result datomic)))\n",
        encoding="utf-8",
    )
    (src / "logic" / "payment.clj").write_text(
        "(ns svc.logic.payment\n  (:require [svc.models.payment :as model]))\n"
        "(defn validate [payment] (when (pos? (:amount payment)) payment))\n",
        encoding="utf-8",
    )
    (src / "models" / "payment.clj").write_text(
        "(ns svc.models.payment)\n"
        "(def Payment {:amount 'Num :status 'Keyword})\n",
        encoding="utf-8",
    )
    (src / "diplomat" / "datomic" / "payment.clj").write_text(
        "(ns svc.diplomat.datomic.payment\n"
        "  (:require [common-datomic.protocols.datomic :as datomic]))\n"
        "(defn save! [entity datomic] (datomic/transact! datomic [entity]))\n",
        encoding="utf-8",
    )
    return tmp_path


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


class TestPipelineE2E:

    def test_structure_to_groups(self, clojure_project: Path) -> None:
        """Extract structure -> partition into flow groups."""
        backend = ClojureNREPLBackend(nrepl_port=None)
        ctx = load_codebase_context(clojure_project, backend)
        groups = partition_flow_groups(ctx.structure)

        # All namespaces connected via deps -> should be 1 or few groups
        total_ns = sum(len(g.namespaces) for g in groups)
        assert total_ns == len(ctx.structure.namespaces)
        assert len(groups) >= 1

    def test_source_map_complete(self, clojure_project: Path) -> None:
        """Source map has content for every namespace."""
        backend = ClojureNREPLBackend(nrepl_port=None)
        ctx = load_codebase_context(clojure_project, backend)
        source_map = load_source_map(ctx.structure, clojure_project)
        for ns in ctx.structure.namespaces:
            assert ns.name in source_map
            assert len(source_map[ns.name]) > 0

    @patch.object(PipelineRunner, "_call_sub_lm_for_group")
    def test_full_pipeline_with_mock_llm(
        self, mock_call: MagicMock, clojure_project: Path, config: EngineConfig
    ) -> None:
        """Full pipeline: structure -> groups -> mock sub-LM -> validate -> result."""
        backend = ClojureNREPLBackend(nrepl_port=None)
        ctx = load_codebase_context(clojure_project, backend)
        groups = partition_flow_groups(ctx.structure)
        source_map = load_source_map(ctx.structure, clojure_project)

        # Mock sub-LM returns valid schema for each group
        def _mock_response(prompt: str) -> str:
            return json.dumps({
                "flow_name": "flow-payment",
                "entry_points": ["svc.wire.in.payment"],
                "exit_points": ["svc.diplomat.datomic.payment"],
                "namespaces": [
                    {"name": ns.name, "layer": ns.layer or "unknown",
                     "role": f"Handles {ns.name.split('.')[-1]}",
                     "side_effects": ["datomic"] if "datomic" in ns.name else [],
                     "security_notes": None}
                    for g in groups for ns in g.namespaces
                ],
                "data_flow": [],
                "bottlenecks": [],
                "security_findings": [],
                "coupling_issues": [],
            })

        mock_call.side_effect = _mock_response

        pipeline = PipelineRunner(config)
        result = pipeline.run(groups, source_map)

        assert result.status == "completed"
        assert result.groups_succeeded == len(groups)
        assert len(result.validation_errors) == 0
        for analysis in result.analyses:
            validate_flow_analysis(json.dumps(analysis))  # should not raise
