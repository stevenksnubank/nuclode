"""Tests for flow-group partitioning from dependency graphs."""

from __future__ import annotations

import pytest

from knowledge.backends.base import NamespaceInfo, StructureResult
from knowledge.engine.chunking import FlowGroup, partition_flow_groups


def _ns(name: str, layer: str | None = None, requires: list[str] | None = None) -> NamespaceInfo:
    """Helper to create NamespaceInfo for tests."""
    return NamespaceInfo(
        path=f"src/{name.replace('.', '/')}.clj",
        name=name,
        requires=requires or [],
        functions=["fn-a"],
        layer=layer,
        has_side_effects=False,
    )


def _structure(namespaces: list[NamespaceInfo]) -> StructureResult:
    dep_map = {}
    for ns in namespaces:
        dep_map[ns.name] = ns.requires
    return StructureResult(
        namespaces=namespaces,
        dependency_map=dep_map,
        total_source_chars=1000,
        extraction_method="static_parse",
    )


class TestPartitionFlowGroups:

    def test_single_linear_flow(self) -> None:
        """wire.in -> adapter -> controller -> logic -> datomic forms one group."""
        nss = [
            _ns("svc.wire.in.payment", "wire", ["svc.adapter.payment"]),
            _ns("svc.adapter.payment", "adapter", ["svc.controller.payment"]),
            _ns("svc.controller.payment", "controller", ["svc.logic.payment"]),
            _ns("svc.logic.payment", "logic", []),
            _ns("svc.diplomat.datomic.payment", None, ["svc.adapter.payment"]),
        ]
        groups = partition_flow_groups(_structure(nss))
        assert len(groups) == 1
        assert len(groups[0].namespaces) == 5

    def test_two_independent_flows(self) -> None:
        """Two disconnected flows produce two groups."""
        nss = [
            _ns("svc.logic.payment", "logic", []),
            _ns("svc.controller.payment", "controller", ["svc.logic.payment"]),
            _ns("svc.logic.events", "logic", []),
            _ns("svc.controller.events", "controller", ["svc.logic.events"]),
        ]
        groups = partition_flow_groups(_structure(nss))
        assert len(groups) == 2

    def test_shared_model_grouped_with_consumers(self) -> None:
        """A model namespace used by two flows joins them into one group."""
        nss = [
            _ns("svc.model.customer", "model", []),
            _ns("svc.logic.payment", "logic", ["svc.model.customer"]),
            _ns("svc.logic.events", "logic", ["svc.model.customer"]),
        ]
        groups = partition_flow_groups(_structure(nss))
        assert len(groups) == 1
        names = {ns.name for ns in groups[0].namespaces}
        assert "svc.model.customer" in names

    def test_every_namespace_assigned(self) -> None:
        """Completeness: every namespace must appear in exactly one group."""
        nss = [
            _ns("svc.logic.a", "logic", []),
            _ns("svc.logic.b", "logic", []),
            _ns("svc.model.c", "model", []),
            _ns("svc.controller.d", "controller", ["svc.logic.a", "svc.logic.b"]),
        ]
        groups = partition_flow_groups(_structure(nss))
        all_names = set()
        for g in groups:
            for ns in g.namespaces:
                assert ns.name not in all_names, f"Duplicate: {ns.name}"
                all_names.add(ns.name)
        assert all_names == {ns.name for ns in nss}

    def test_empty_structure(self) -> None:
        groups = partition_flow_groups(_structure([]))
        assert groups == []

    def test_single_namespace(self) -> None:
        nss = [_ns("svc.logic.core", "logic", [])]
        groups = partition_flow_groups(_structure(nss))
        assert len(groups) == 1
        assert len(groups[0].namespaces) == 1

    def test_deterministic_ordering(self) -> None:
        """Same input -> same output, regardless of dict ordering."""
        nss = [
            _ns("svc.logic.b", "logic", []),
            _ns("svc.logic.a", "logic", ["svc.logic.b"]),
            _ns("svc.model.c", "model", []),
        ]
        groups_1 = partition_flow_groups(_structure(nss))
        groups_2 = partition_flow_groups(_structure(list(reversed(nss))))
        names_1 = [sorted(ns.name for ns in g.namespaces) for g in groups_1]
        names_2 = [sorted(ns.name for ns in g.namespaces) for g in groups_2]
        assert names_1 == names_2

    def test_flow_group_has_entry_and_exit_points(self) -> None:
        """Groups identify entry points (no incoming deps) and exit points (no outgoing deps)."""
        nss = [
            _ns("svc.wire.in.pay", "wire", []),
            _ns("svc.adapter.pay", "adapter", ["svc.wire.in.pay"]),
            _ns("svc.logic.pay", "logic", ["svc.adapter.pay"]),
        ]
        groups = partition_flow_groups(_structure(nss))
        g = groups[0]
        assert "svc.wire.in.pay" in g.entry_points
        assert "svc.logic.pay" in g.exit_points


class TestFlowGroupDataclass:

    def test_frozen(self) -> None:
        g = FlowGroup(
            name="test",
            namespaces=[_ns("svc.logic.a", "logic")],
            entry_points=["svc.logic.a"],
            exit_points=["svc.logic.a"],
            internal_deps={},
        )
        with pytest.raises(AttributeError):
            g.name = "changed"  # type: ignore[misc]
