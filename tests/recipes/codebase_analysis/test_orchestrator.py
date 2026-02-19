"""Tests for the codebase analysis orchestrator.

Tests mock git commands, bd CLI, and the engine runner — no real
API calls or external tools required.
"""

from __future__ import annotations

import json
import subprocess
import textwrap
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from engine.backends.clojure_nrepl import ClojureNREPLBackend
from engine.config import EngineConfig, GuardrailsConfig
from engine.gate import GateDecision
from engine.runner import EngineResult, EngineRunner
from recipes.codebase_analysis.orchestrator import (
    AnalysisResult,
    CodebaseAnalyzer,
    StalenessResult,
    StalenessStatus,
    _get_changed_files,
    _get_current_sha,
    _map_files_to_namespaces,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config() -> EngineConfig:
    return EngineConfig(
        root_model="claude-opus-4-6",
        root_extended_thinking=False,
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
def backend() -> ClojureNREPLBackend:
    return ClojureNREPLBackend(nrepl_port=None)


@pytest.fixture
def mock_project(tmp_path: Path) -> Path:
    """Create a mock Clojure project with beads directory."""
    logic_dir = tmp_path / "src" / "nu" / "svc" / "logic"
    logic_dir.mkdir(parents=True)
    model_dir = tmp_path / "src" / "nu" / "svc" / "model"
    model_dir.mkdir(parents=True)

    (logic_dir / "core.clj").write_text(textwrap.dedent("""\
        (ns nu.svc.logic.core
          (:require [nu.svc.model.data :as data]))
        (defn process [x] (data/transform x))
    """), encoding="utf-8")

    (model_dir / "data.clj").write_text(textwrap.dedent("""\
        (ns nu.svc.model.data)
        (defn transform [x] {:result x})
    """), encoding="utf-8")

    return tmp_path


@pytest.fixture
def mock_project_with_beads(mock_project: Path) -> Path:
    """Mock project with .beads directory."""
    beads_dir = mock_project / ".beads"
    beads_dir.mkdir()
    return mock_project


@pytest.fixture
def mock_project_with_metadata(mock_project_with_beads: Path) -> Path:
    """Mock project with analysis metadata."""
    metadata = {"commit_sha": "abc123", "backend": "clojure-nrepl"}
    metadata_path = mock_project_with_beads / ".beads" / "analysis_metadata.json"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    return mock_project_with_beads


@pytest.fixture
def analyzer(
    mock_project: Path, backend: ClojureNREPLBackend, config: EngineConfig
) -> CodebaseAnalyzer:
    return CodebaseAnalyzer(mock_project, backend, config)


def _make_engine_result(status: str = "completed", **kwargs) -> EngineResult:
    """Helper to create mock EngineResult."""
    defaults = {
        "iterations": 1,
        "gate_decision": GateDecision(
            fan_out=False, token_count=100, stage="threshold", reason="test"
        ),
        "cost_summary": {"total_cost_usd": "0.50"},
        "output": "analysis done",
    }
    defaults.update(kwargs)
    return EngineResult(status=status, **defaults)


# ---------------------------------------------------------------------------
# Staleness detection
# ---------------------------------------------------------------------------


class TestCheckStaleness:

    def test_no_beads_dir(
        self, mock_project: Path, backend: ClojureNREPLBackend, config: EngineConfig
    ) -> None:
        analyzer = CodebaseAnalyzer(mock_project, backend, config)
        result = analyzer.check_staleness()
        assert result.status == StalenessStatus.NO_BEADS

    def test_no_metadata_file(
        self, mock_project_with_beads: Path, backend: ClojureNREPLBackend, config: EngineConfig
    ) -> None:
        analyzer = CodebaseAnalyzer(mock_project_with_beads, backend, config)
        result = analyzer.check_staleness()
        assert result.status == StalenessStatus.NO_PRIOR_ANALYSIS

    @patch("recipes.codebase_analysis.orchestrator._get_current_sha")
    def test_same_sha_is_fresh(
        self, mock_sha: MagicMock,
        mock_project_with_metadata: Path, backend: ClojureNREPLBackend, config: EngineConfig
    ) -> None:
        mock_sha.return_value = "abc123"
        analyzer = CodebaseAnalyzer(mock_project_with_metadata, backend, config)
        result = analyzer.check_staleness()
        assert result.status == StalenessStatus.FRESH
        assert result.last_sha == "abc123"
        assert result.current_sha == "abc123"

    @patch("recipes.codebase_analysis.orchestrator._get_changed_files")
    @patch("recipes.codebase_analysis.orchestrator._get_current_sha")
    def test_different_sha_no_source_changes_is_fresh(
        self, mock_sha: MagicMock, mock_changed: MagicMock,
        mock_project_with_metadata: Path, backend: ClojureNREPLBackend, config: EngineConfig
    ) -> None:
        mock_sha.return_value = "def456"
        mock_changed.return_value = ["README.md", "docs/notes.txt"]  # no .clj files
        analyzer = CodebaseAnalyzer(mock_project_with_metadata, backend, config)
        result = analyzer.check_staleness()
        assert result.status == StalenessStatus.FRESH
        assert result.changed_namespaces == []

    @patch("recipes.codebase_analysis.orchestrator._get_changed_files")
    @patch("recipes.codebase_analysis.orchestrator._get_current_sha")
    def test_different_sha_with_source_changes_is_stale(
        self, mock_sha: MagicMock, mock_changed: MagicMock,
        mock_project_with_metadata: Path, backend: ClojureNREPLBackend, config: EngineConfig
    ) -> None:
        mock_sha.return_value = "def456"
        # Return a path that matches a namespace in the project
        mock_changed.return_value = ["src/nu/svc/logic/core.clj"]
        analyzer = CodebaseAnalyzer(mock_project_with_metadata, backend, config)
        result = analyzer.check_staleness()
        assert result.status == StalenessStatus.STALE
        assert len(result.changed_namespaces) > 0

    def test_corrupted_metadata_treated_as_no_prior(
        self, mock_project_with_beads: Path, backend: ClojureNREPLBackend, config: EngineConfig
    ) -> None:
        metadata_path = mock_project_with_beads / ".beads" / "analysis_metadata.json"
        metadata_path.write_text("not valid json", encoding="utf-8")
        analyzer = CodebaseAnalyzer(mock_project_with_beads, backend, config)
        result = analyzer.check_staleness()
        assert result.status == StalenessStatus.NO_PRIOR_ANALYSIS


# ---------------------------------------------------------------------------
# Run analysis
# ---------------------------------------------------------------------------


class TestRun:

    @patch.object(CodebaseAnalyzer, "check_staleness")
    def test_skips_fresh_analysis(
        self, mock_staleness: MagicMock, analyzer: CodebaseAnalyzer
    ) -> None:
        mock_staleness.return_value = StalenessResult(
            status=StalenessStatus.FRESH,
            last_sha="abc", current_sha="abc",
            changed_files=[], changed_namespaces=[],
        )
        result = analyzer.run()
        assert result.status == "skipped_fresh"
        assert result.engine_result is None

    @patch.object(CodebaseAnalyzer, "check_staleness")
    @patch.object(EngineRunner, "run")
    def test_force_overrides_fresh(
        self, mock_engine: MagicMock, mock_staleness: MagicMock, analyzer: CodebaseAnalyzer
    ) -> None:
        mock_staleness.return_value = StalenessResult(
            status=StalenessStatus.FRESH,
            last_sha="abc", current_sha="abc",
            changed_files=[], changed_namespaces=[],
        )
        mock_engine.return_value = _make_engine_result()
        result = analyzer.run(force=True)
        assert result.status == "completed"
        mock_engine.assert_called_once()

    @patch.object(CodebaseAnalyzer, "check_staleness")
    @patch.object(EngineRunner, "run")
    def test_runs_on_no_prior_analysis(
        self, mock_engine: MagicMock, mock_staleness: MagicMock, analyzer: CodebaseAnalyzer
    ) -> None:
        mock_staleness.return_value = StalenessResult(
            status=StalenessStatus.NO_PRIOR_ANALYSIS,
            last_sha=None, current_sha="abc",
            changed_files=[], changed_namespaces=[],
        )
        mock_engine.return_value = _make_engine_result()
        result = analyzer.run()
        assert result.status == "completed"

    @patch.object(CodebaseAnalyzer, "check_staleness")
    @patch.object(EngineRunner, "run")
    def test_runs_on_stale(
        self, mock_engine: MagicMock, mock_staleness: MagicMock, analyzer: CodebaseAnalyzer
    ) -> None:
        mock_staleness.return_value = StalenessResult(
            status=StalenessStatus.STALE,
            last_sha="abc", current_sha="def",
            changed_files=["src/core.clj"], changed_namespaces=["nu.svc.logic.core"],
        )
        mock_engine.return_value = _make_engine_result()
        result = analyzer.run()
        assert result.status == "completed"

    @patch.object(CodebaseAnalyzer, "check_staleness")
    @patch.object(EngineRunner, "run")
    def test_captures_namespace_count(
        self, mock_engine: MagicMock, mock_staleness: MagicMock, analyzer: CodebaseAnalyzer
    ) -> None:
        mock_staleness.return_value = StalenessResult(
            status=StalenessStatus.NO_PRIOR_ANALYSIS,
            last_sha=None, current_sha="abc",
            changed_files=[], changed_namespaces=[],
        )
        mock_engine.return_value = _make_engine_result()
        result = analyzer.run()
        assert result.namespace_count == 2  # mock_project has 2 namespaces

    @patch.object(CodebaseAnalyzer, "check_staleness")
    @patch.object(EngineRunner, "run")
    def test_passes_mode_to_prompt(
        self, mock_engine: MagicMock, mock_staleness: MagicMock, analyzer: CodebaseAnalyzer
    ) -> None:
        mock_staleness.return_value = StalenessResult(
            status=StalenessStatus.NO_BEADS,
            last_sha=None, current_sha="abc",
            changed_files=[], changed_namespaces=[],
        )
        mock_engine.return_value = _make_engine_result()
        result = analyzer.run(mode="security")
        # Verify engine was called (prompt building with mode happens internally)
        mock_engine.assert_called_once()
        assert result.status == "completed"


# ---------------------------------------------------------------------------
# Store metadata
# ---------------------------------------------------------------------------


class TestStoreAnalysisMetadata:

    def test_creates_metadata_file(
        self, mock_project: Path, backend: ClojureNREPLBackend, config: EngineConfig
    ) -> None:
        analyzer = CodebaseAnalyzer(mock_project, backend, config)
        analyzer.store_analysis_metadata("sha-123")

        metadata_path = mock_project / ".beads" / "analysis_metadata.json"
        assert metadata_path.exists()

        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert metadata["commit_sha"] == "sha-123"
        assert metadata["backend"] == "clojure-nrepl"

    def test_overwrites_existing_metadata(
        self, mock_project_with_metadata: Path, backend: ClojureNREPLBackend, config: EngineConfig
    ) -> None:
        analyzer = CodebaseAnalyzer(mock_project_with_metadata, backend, config)
        analyzer.store_analysis_metadata("new-sha")

        metadata_path = mock_project_with_metadata / ".beads" / "analysis_metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert metadata["commit_sha"] == "new-sha"

    def test_creates_beads_dir_if_missing(
        self, mock_project: Path, backend: ClojureNREPLBackend, config: EngineConfig
    ) -> None:
        analyzer = CodebaseAnalyzer(mock_project, backend, config)
        analyzer.store_analysis_metadata("sha-456")

        beads_dir = mock_project / ".beads"
        assert beads_dir.exists()


# ---------------------------------------------------------------------------
# Verify graph
# ---------------------------------------------------------------------------


class TestVerifyGraph:

    @patch("recipes.codebase_analysis.orchestrator.subprocess.run")
    def test_returns_true_when_beads_exist(
        self, mock_run: MagicMock,
        mock_project: Path, backend: ClojureNREPLBackend, config: EngineConfig
    ) -> None:
        mock_run.return_value = MagicMock(
            returncode=0, stdout="bead-1\nbead-2\n"
        )
        analyzer = CodebaseAnalyzer(mock_project, backend, config)
        assert analyzer.verify_graph() is True

    @patch("recipes.codebase_analysis.orchestrator.subprocess.run")
    def test_returns_false_when_no_beads(
        self, mock_run: MagicMock,
        mock_project: Path, backend: ClojureNREPLBackend, config: EngineConfig
    ) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        analyzer = CodebaseAnalyzer(mock_project, backend, config)
        assert analyzer.verify_graph() is False

    @patch("recipes.codebase_analysis.orchestrator.subprocess.run")
    def test_returns_false_on_bd_failure(
        self, mock_run: MagicMock,
        mock_project: Path, backend: ClojureNREPLBackend, config: EngineConfig
    ) -> None:
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        analyzer = CodebaseAnalyzer(mock_project, backend, config)
        assert analyzer.verify_graph() is False

    @patch("recipes.codebase_analysis.orchestrator.subprocess.run")
    def test_returns_false_on_timeout(
        self, mock_run: MagicMock,
        mock_project: Path, backend: ClojureNREPLBackend, config: EngineConfig
    ) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="bd", timeout=10)
        analyzer = CodebaseAnalyzer(mock_project, backend, config)
        assert analyzer.verify_graph() is False


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


class TestGetCurrentSha:

    @patch("recipes.codebase_analysis.orchestrator.subprocess.run")
    def test_returns_sha(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="abc123\n")
        assert _get_current_sha(tmp_path) == "abc123"

    @patch("recipes.codebase_analysis.orchestrator.subprocess.run")
    def test_returns_none_on_failure(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        assert _get_current_sha(tmp_path) is None


class TestGetChangedFiles:

    @patch("recipes.codebase_analysis.orchestrator.subprocess.run")
    def test_returns_changed_files(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = MagicMock(
            returncode=0, stdout="src/core.clj\nsrc/model.clj\n"
        )
        result = _get_changed_files(tmp_path, "abc", "def")
        assert result == ["src/core.clj", "src/model.clj"]

    @patch("recipes.codebase_analysis.orchestrator.subprocess.run")
    def test_returns_empty_on_failure(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        assert _get_changed_files(tmp_path, "abc", "def") == []


class TestMapFilesToNamespaces:

    def test_maps_files(self, mock_project: Path, backend: ClojureNREPLBackend) -> None:
        changed = ["src/nu/svc/logic/core.clj"]
        result = _map_files_to_namespaces(changed, mock_project, backend)
        assert "nu.svc.logic.core" in result

    def test_empty_changes(self, mock_project: Path, backend: ClojureNREPLBackend) -> None:
        assert _map_files_to_namespaces([], mock_project, backend) == []

    def test_non_source_files_ignored(self, mock_project: Path, backend: ClojureNREPLBackend) -> None:
        changed = ["README.md", "docs/notes.txt"]
        assert _map_files_to_namespaces(changed, mock_project, backend) == []


# ---------------------------------------------------------------------------
# StalenessResult / AnalysisResult dataclasses
# ---------------------------------------------------------------------------


class TestDataclasses:

    def test_staleness_result_frozen(self) -> None:
        result = StalenessResult(
            status=StalenessStatus.FRESH,
            last_sha="abc", current_sha="abc",
            changed_files=[], changed_namespaces=[],
        )
        with pytest.raises(AttributeError):
            result.status = StalenessStatus.STALE  # type: ignore[misc]

    def test_analysis_result_frozen(self) -> None:
        result = AnalysisResult(
            status="completed",
            engine_result=None,
            staleness=StalenessResult(
                status=StalenessStatus.FRESH,
                last_sha="abc", current_sha="abc",
                changed_files=[], changed_namespaces=[],
            ),
            namespace_count=0,
            commit_sha="abc",
        )
        with pytest.raises(AttributeError):
            result.status = "changed"  # type: ignore[misc]
