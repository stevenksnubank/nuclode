"""Tests for the codebase analysis context loader."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from engine.backends.clojure_nrepl import ClojureNREPLBackend
from recipes.codebase_analysis.context_loader import (
    CodebaseContext,
    load_codebase_context,
    load_source_for_namespace,
)


@pytest.fixture
def mock_project(tmp_path: Path) -> Path:
    """Create a mock Clojure project."""
    logic_dir = tmp_path / "src" / "nu" / "svc" / "logic"
    logic_dir.mkdir(parents=True)
    model_dir = tmp_path / "src" / "nu" / "svc" / "model"
    model_dir.mkdir(parents=True)

    (logic_dir / "core.clj").write_text(textwrap.dedent("""\
        (ns nu.svc.logic.core
          (:require [nu.svc.model.data :as data]
                    [nu.libs.datomic.api :as db]))
        (defn process [x] (db/transact (data/->tx x)))
    """), encoding="utf-8")

    (model_dir / "data.clj").write_text(textwrap.dedent("""\
        (ns nu.svc.model.data)
        (defn ->tx [x] {:tx-data [[:db/add x]]})
    """), encoding="utf-8")

    return tmp_path


@pytest.fixture
def backend() -> ClojureNREPLBackend:
    return ClojureNREPLBackend(nrepl_port=None)


class TestLoadCodebaseContext:

    def test_loads_context(self, mock_project: Path, backend: ClojureNREPLBackend) -> None:
        ctx = load_codebase_context(mock_project, backend)
        assert isinstance(ctx, CodebaseContext)
        assert ctx.project_name == mock_project.name
        assert ctx.project_dir == mock_project

    def test_structure_populated(self, mock_project: Path, backend: ClojureNREPLBackend) -> None:
        ctx = load_codebase_context(mock_project, backend)
        assert len(ctx.structure.namespaces) == 2

    def test_source_index_populated(self, mock_project: Path, backend: ClojureNREPLBackend) -> None:
        ctx = load_codebase_context(mock_project, backend)
        assert len(ctx.source_index) > 0

    def test_structure_summary_has_keys(self, mock_project: Path, backend: ClojureNREPLBackend) -> None:
        ctx = load_codebase_context(mock_project, backend)
        summary = ctx.structure_summary
        assert "namespace_count" in summary
        assert "total_source_chars" in summary
        assert "namespaces" in summary
        assert "dependency_map" in summary
        assert summary["namespace_count"] == 2

    def test_summary_namespaces_have_fields(self, mock_project: Path, backend: ClojureNREPLBackend) -> None:
        ctx = load_codebase_context(mock_project, backend)
        ns = ctx.structure_summary["namespaces"][0]
        assert "name" in ns
        assert "layer" in ns
        assert "requires" in ns
        assert "functions" in ns
        assert "has_side_effects" in ns

    def test_summary_paths_are_relative(self, mock_project: Path, backend: ClojureNREPLBackend) -> None:
        ctx = load_codebase_context(mock_project, backend)
        for ns in ctx.structure_summary["namespaces"]:
            assert not ns["path"].startswith("/"), f"Path should be relative: {ns['path']}"

    def test_nonexistent_dir_raises(self, backend: ClojureNREPLBackend) -> None:
        with pytest.raises(FileNotFoundError):
            load_codebase_context(Path("/nonexistent"), backend)

    def test_empty_dir_raises(self, tmp_path: Path, backend: ClojureNREPLBackend) -> None:
        with pytest.raises(ValueError, match="No Clojure source files"):
            load_codebase_context(tmp_path, backend)

    def test_frozen_dataclass(self, mock_project: Path, backend: ClojureNREPLBackend) -> None:
        ctx = load_codebase_context(mock_project, backend)
        with pytest.raises(AttributeError):
            ctx.project_name = "changed"  # type: ignore[misc]


class TestLoadSourceForNamespace:

    def test_loads_existing_file(self, mock_project: Path) -> None:
        path = str(mock_project / "src" / "nu" / "svc" / "logic" / "core.clj")
        source = load_source_for_namespace(path)
        assert "ns nu.svc.logic.core" in source

    def test_nonexistent_file_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_source_for_namespace("/nonexistent/file.clj")
