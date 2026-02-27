"""Flow-group partitioning from dependency graphs.

Partitions a StructureResult's namespaces into flow groups — connected
subgraphs that represent complete data paths through the codebase.
Deterministic: same input → same groups.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from knowledge.backends.base import NamespaceInfo, StructureResult


@dataclass(frozen=True)
class FlowGroup:
    """A connected subgraph of namespaces forming a data flow.

    Attributes:
        name: Deterministic name derived from the group's namespaces.
        namespaces: All namespaces in this group.
        entry_points: Namespace names with no incoming deps within the group.
        exit_points: Namespace names with no outgoing deps within the group.
        internal_deps: Dependency edges within the group (from → [to]).
    """

    name: str
    namespaces: list[NamespaceInfo]
    entry_points: list[str]
    exit_points: list[str]
    internal_deps: dict[str, list[str]]


def partition_flow_groups(structure: StructureResult) -> list[FlowGroup]:
    """Partition namespaces into connected flow groups.

    Uses union-find on the undirected dependency graph to find connected
    components. Each component becomes a FlowGroup.

    Deterministic: namespaces are sorted by name before processing,
    and groups are sorted by their first namespace name.

    Args:
        structure: The extracted project structure with dependency map.

    Returns:
        Sorted list of FlowGroups covering all namespaces.
    """
    if not structure.namespaces:
        return []

    ns_by_name: dict[str, NamespaceInfo] = {ns.name: ns for ns in structure.namespaces}
    all_names = sorted(ns_by_name.keys())

    # Union-Find for connected components
    parent: dict[str, str] = {n: n for n in all_names}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            # Deterministic: smaller name becomes root
            if ra > rb:
                ra, rb = rb, ra
            parent[rb] = ra

    # Build undirected edges from dependency map
    for ns_name in all_names:
        for dep in structure.dependency_map.get(ns_name, []):
            if dep in ns_by_name:
                union(ns_name, dep)

    # Group by component root
    components: dict[str, list[str]] = {}
    for name in all_names:
        root = find(name)
        components.setdefault(root, []).append(name)

    # Build FlowGroups
    groups: list[FlowGroup] = []
    for root in sorted(components.keys()):
        members = components[root]
        member_set = set(members)

        # Internal deps: only edges within this group
        internal_deps: dict[str, list[str]] = {}
        for name in members:
            deps_in_group = [
                d for d in structure.dependency_map.get(name, []) if d in member_set
            ]
            if deps_in_group:
                internal_deps[name] = sorted(deps_in_group)

        # Entry points: don't require any other member (data flow starts here)
        # In Clojure :require, "A requires B" means data flows FROM B TO A.
        # So entry points are namespaces that don't depend on anything in the group.
        entry_points = sorted(n for n in members if n not in internal_deps)

        # Exit points: not required by any other member (data flow ends here)
        required_by_others = set()
        for deps in internal_deps.values():
            required_by_others.update(deps)
        exit_points = sorted(n for n in members if n not in required_by_others)

        # Deterministic group name from first member
        group_name = f"flow-{members[0].split('.')[-1]}" if members else "flow-unknown"

        groups.append(FlowGroup(
            name=group_name,
            namespaces=[ns_by_name[n] for n in members],
            entry_points=entry_points,
            exit_points=exit_points,
            internal_deps=internal_deps,
        ))

    return groups
