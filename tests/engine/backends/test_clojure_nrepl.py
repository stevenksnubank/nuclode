"""Tests for the Clojure nREPL backend."""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from engine.backends.base import NamespaceInfo, StructureResult
from engine.backends.clojure_nrepl import (
    ClojureNREPLBackend,
    _detect_nrepl_port,
    _extract_functions,
    _extract_ns_region,
    _glob_clojure_files,
    _parse_requires,
)


@pytest.fixture
def backend() -> ClojureNREPLBackend:
    return ClojureNREPLBackend(nrepl_port=None)


@pytest.fixture
def sample_clj_source() -> str:
    return textwrap.dedent("""\
        (ns nu.customer.logic.payment
          (:require
            [nu.customer.model.payment :as model]
            [nu.customer.wire.payment :as wire]
            [nu.libs.kafka.producer :as kafka]
            [nu.libs.datomic.api :as datomic]
            [clojure.string :as str]))

        (defn validate-amount [amount]
          (when (<= amount 0)
            (throw (ex-info "Amount must be positive" {:amount amount}))))

        (defn process-payment [request]
          (let [amount (:amount request)]
            (validate-amount amount)
            (datomic/transact (model/->transaction request))
            (kafka/publish :payment-events (wire/->event request))))

        (defn- internal-helper [x] (* x 2))
    """)


@pytest.fixture
def mock_project(tmp_path: Path, sample_clj_source: str) -> Path:
    logic_dir = tmp_path / "src" / "nu" / "customer" / "logic"
    logic_dir.mkdir(parents=True)
    adapter_dir = tmp_path / "src" / "nu" / "customer" / "adapter"
    adapter_dir.mkdir(parents=True)
    model_dir = tmp_path / "src" / "nu" / "customer" / "model"
    model_dir.mkdir(parents=True)
    wire_dir = tmp_path / "src" / "nu" / "customer" / "wire"
    wire_dir.mkdir(parents=True)

    (logic_dir / "payment.clj").write_text(sample_clj_source, encoding="utf-8")
    (adapter_dir / "payment_http.clj").write_text(textwrap.dedent("""\
        (ns nu.customer.adapter.payment-http
          (:require [nu.customer.controller.payment :as controller]))
        (defn handle-request [req] (controller/process req))
    """), encoding="utf-8")
    (model_dir / "payment.clj").write_text(textwrap.dedent("""\
        (ns nu.customer.model.payment)
        (defn ->transaction [request] {:tx-data []})
    """), encoding="utf-8")
    (wire_dir / "payment.clj").write_text(textwrap.dedent("""\
        (ns nu.customer.wire.payment
          (:require [cheshire.core :as json]))
        (defn ->event [request] (json/generate-string request))
    """), encoding="utf-8")

    # target dir should be excluded
    target_dir = tmp_path / "target" / "classes"
    target_dir.mkdir(parents=True)
    (target_dir / "compiled.clj").write_text("(ns compiled.stuff)", encoding="utf-8")

    return tmp_path


class TestBackendProperties:

    def test_name(self, backend: ClojureNREPLBackend) -> None:
        assert backend.name == "clojure-nrepl"

    def test_is_available_no_port(self, backend: ClojureNREPLBackend) -> None:
        assert backend.is_available() is False

    def test_eval_raises_not_implemented(self, backend: ClojureNREPLBackend) -> None:
        with pytest.raises(NotImplementedError, match="nREPL eval integration pending"):
            backend.eval("(+ 1 2)")


class TestParseNsForm:

    def test_basic_ns_with_requires(self, backend: ClojureNREPLBackend, sample_clj_source: str) -> None:
        ns_name, requires = backend._parse_ns_form(sample_clj_source)
        assert ns_name == "nu.customer.logic.payment"
        assert "nu.customer.model.payment" in requires
        assert "nu.libs.kafka.producer" in requires
        assert "clojure.string" in requires

    def test_ns_without_requires(self, backend: ClojureNREPLBackend) -> None:
        source = "(ns my.simple.namespace)\n(defn foo [x] x)"
        ns_name, requires = backend._parse_ns_form(source)
        assert ns_name == "my.simple.namespace"
        assert requires == []

    def test_no_ns_form(self, backend: ClojureNREPLBackend) -> None:
        ns_name, requires = backend._parse_ns_form("(defn foo [] 1)")
        assert ns_name is None
        assert requires == []


class TestClassifyDiplomatLayer:

    def test_logic_layer(self, backend: ClojureNREPLBackend) -> None:
        assert backend._classify_diplomat_layer("nu.customer.logic.payment", "") == "logic"

    def test_adapter_layer(self, backend: ClojureNREPLBackend) -> None:
        assert backend._classify_diplomat_layer("nu.customer.adapter.http", "") == "adapter"

    def test_controller_layer(self, backend: ClojureNREPLBackend) -> None:
        assert backend._classify_diplomat_layer("nu.customer.controller.payment", "") == "controller"

    def test_model_layer(self, backend: ClojureNREPLBackend) -> None:
        assert backend._classify_diplomat_layer("nu.customer.model.payment", "") == "model"

    def test_wire_layer(self, backend: ClojureNREPLBackend) -> None:
        assert backend._classify_diplomat_layer("nu.customer.wire.payment", "") == "wire"

    def test_unknown_layer(self, backend: ClojureNREPLBackend) -> None:
        assert backend._classify_diplomat_layer("nu.libs.kafka.producer", "") is None

    def test_layer_from_path_fallback(self, backend: ClojureNREPLBackend) -> None:
        assert backend._classify_diplomat_layer(
            "nu.customer.utils", "/src/nu/customer/logic/utils.clj"
        ) == "logic"


class TestDetectSideEffects:

    def test_detects_datomic(self, backend: ClojureNREPLBackend) -> None:
        assert backend._detect_side_effects("(:require [nu.libs.datomic.api])") is True

    def test_detects_kafka(self, backend: ClojureNREPLBackend) -> None:
        assert backend._detect_side_effects("(:require [nu.libs.kafka.producer])") is True

    def test_no_side_effects(self, backend: ClojureNREPLBackend) -> None:
        assert backend._detect_side_effects("(ns pure.ns (:require [clojure.string]))") is False


class TestExtractFunctions:

    def test_defn_extraction(self, sample_clj_source: str) -> None:
        functions = _extract_functions(sample_clj_source)
        assert "validate-amount" in functions
        assert "process-payment" in functions
        assert "internal-helper" in functions

    def test_defmethod_extraction(self) -> None:
        source = "(defmulti area :shape)\n(defmethod area :circle [{:keys [r]}] (* Math/PI r r))"
        functions = _extract_functions(source)
        assert "area :circle" in functions


class TestGlobClojureFiles:

    def test_finds_clj_files(self, mock_project: Path) -> None:
        files = _glob_clojure_files(mock_project)
        names = [f.name for f in files]
        assert "payment.clj" in names

    def test_excludes_target(self, mock_project: Path) -> None:
        files = _glob_clojure_files(mock_project)
        for f in files:
            assert "target" not in f.parts


class TestDetectNreplPort:

    def test_detects_port(self, tmp_path: Path) -> None:
        (tmp_path / ".nrepl-port").write_text("7888", encoding="utf-8")
        assert _detect_nrepl_port(tmp_path) == 7888

    def test_returns_none_when_missing(self, tmp_path: Path) -> None:
        assert _detect_nrepl_port(tmp_path) is None

    def test_rejects_invalid(self, tmp_path: Path) -> None:
        (tmp_path / ".nrepl-port").write_text("not-a-number", encoding="utf-8")
        assert _detect_nrepl_port(tmp_path) is None


class TestExtractStructure:

    def test_extracts_all_namespaces(self, backend: ClojureNREPLBackend, mock_project: Path) -> None:
        result = backend.extract_structure(mock_project)
        ns_names = [ns.name for ns in result.namespaces]
        assert "nu.customer.logic.payment" in ns_names
        assert "nu.customer.adapter.payment-http" in ns_names
        assert "nu.customer.model.payment" in ns_names
        assert "nu.customer.wire.payment" in ns_names

    def test_extraction_method(self, backend: ClojureNREPLBackend, mock_project: Path) -> None:
        result = backend.extract_structure(mock_project)
        assert result.extraction_method == "static_parse"

    def test_dependency_map(self, backend: ClojureNREPLBackend, mock_project: Path) -> None:
        result = backend.extract_structure(mock_project)
        deps = result.dependency_map["nu.customer.logic.payment"]
        assert "nu.customer.model.payment" in deps

    def test_diplomat_layers(self, backend: ClojureNREPLBackend, mock_project: Path) -> None:
        result = backend.extract_structure(mock_project)
        layers = {ns.name: ns.layer for ns in result.namespaces}
        assert layers["nu.customer.logic.payment"] == "logic"
        assert layers["nu.customer.adapter.payment-http"] == "adapter"

    def test_side_effects(self, backend: ClojureNREPLBackend, mock_project: Path) -> None:
        result = backend.extract_structure(mock_project)
        effects = {ns.name: ns.has_side_effects for ns in result.namespaces}
        assert effects["nu.customer.logic.payment"] is True
        assert effects["nu.customer.model.payment"] is False

    def test_excludes_target_files(self, backend: ClojureNREPLBackend, mock_project: Path) -> None:
        result = backend.extract_structure(mock_project)
        ns_names = [ns.name for ns in result.namespaces]
        assert "compiled.stuff" not in ns_names

    def test_nonexistent_dir_raises(self, backend: ClojureNREPLBackend) -> None:
        with pytest.raises(FileNotFoundError):
            backend.extract_structure(Path("/nonexistent"))

    def test_empty_dir_raises(self, backend: ClojureNREPLBackend, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="No Clojure source files"):
            backend.extract_structure(tmp_path)

    def test_nrepl_fallback(self, mock_project: Path) -> None:
        backend = ClojureNREPLBackend(nrepl_port=None)
        with patch.object(backend, "is_available", return_value=True):
            result = backend.extract_structure(mock_project)
        assert result.extraction_method == "static_parse"
        assert len(result.namespaces) > 0
