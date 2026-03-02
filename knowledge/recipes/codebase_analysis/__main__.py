"""CLI entry point for the codebase analysis recipe.

Usage:
    python -m knowledge.recipes.codebase_analysis /path/to/project
    python -m knowledge.recipes.codebase_analysis ~/dev/nu/financial-calculator --mode security
    python -m knowledge.recipes.codebase_analysis ~/dev/nu/espetinho --force --nrepl-port 7888
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Any

from knowledge.backends.clojure_nrepl import ClojureNREPLBackend
from knowledge.engine.config import load_config
from knowledge.recipes.codebase_analysis.orchestrator import CodebaseAnalyzer


def _load_dotenv() -> None:
    """Load .env file from the nuclode project root if it exists."""
    # Walk up from this file to find the project root containing .env
    current = Path(__file__).resolve()
    for parent in [current.parent, *current.parents]:
        env_file = parent / ".env"
        if env_file.is_file():
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    key, _, value = line.partition("=")
                    key, value = key.strip(), value.strip()
                    if key and key not in os.environ:
                        os.environ[key] = value
            break


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m knowledge.recipes.codebase_analysis",
        description="Analyze a codebase and store results as beads.",
    )
    parser.add_argument(
        "project_dir",
        type=Path,
        help="Path to the target project (read-only).",
    )
    parser.add_argument(
        "--mode",
        choices=["structure", "security"],
        default="structure",
        help="Analysis mode (default: structure).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip staleness check and run full analysis.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Where to write beads and metadata (default: nuclode/.beads/).",
    )
    parser.add_argument(
        "--nrepl-port",
        type=int,
        default=None,
        help="nREPL port for richer extraction (falls back to static parsing).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load context and show flow groups — no API calls, no cost.",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    _load_dotenv()
    args = _build_parser().parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    project_dir = args.project_dir.expanduser().resolve()
    if not project_dir.is_dir():
        print(f"Error: {project_dir} is not a directory", file=sys.stderr)
        return 1

    backend = ClojureNREPLBackend(nrepl_port=args.nrepl_port)
    config = load_config()

    analyzer = CodebaseAnalyzer(
        project_dir=project_dir,
        backend=backend,
        config=config,
        output_dir=args.output_dir,
    )

    # Staleness check (always runs, free)
    staleness = analyzer.check_staleness()
    print(f"Project:    {project_dir.name}")
    print(f"Staleness:  {staleness.status.value}")
    if staleness.current_sha:
        print(f"HEAD:       {staleness.current_sha[:12]}")
    if staleness.last_sha:
        print(f"Last SHA:   {staleness.last_sha[:12]}")
    if staleness.changed_namespaces:
        print(f"Changed:    {len(staleness.changed_namespaces)} namespace(s)")
        for ns in staleness.changed_namespaces:
            print(f"  - {ns}")

    if args.dry_run:
        from knowledge.engine.chunking import partition_flow_groups
        from knowledge.recipes.codebase_analysis.context_loader import load_codebase_context

        ctx = load_codebase_context(project_dir, backend)
        groups = partition_flow_groups(ctx.structure)
        print(f"Namespaces: {len(ctx.structure.namespaces)}")
        print(f"Flow groups: {len(groups)}")
        for g in groups:
            layers = sorted({ns.layer or "unknown" for ns in g.namespaces})
            print(f"  - {g.name} ({len(g.namespaces)} ns, layers: {', '.join(layers)})")
            if g.entry_points:
                print(f"    entry: {', '.join(g.entry_points)}")
            if g.exit_points:
                print(f"    exit:  {', '.join(g.exit_points)}")
        print("\nDry run complete — no API calls made.")
        return 0

    # Full analysis
    result = analyzer.run(force=args.force, mode=args.mode)

    print(f"\nResult:     {result.status}")
    print(f"Namespaces: {result.namespace_count}")

    if result.pipeline_result:
        pr = result.pipeline_result
        print(f"Groups:     {pr.groups_succeeded}/{pr.groups_total} succeeded")
        cost = pr.cost_summary.get("total_cost_usd", "unknown")
        print(f"Cost:       ${cost}")
        if pr.validation_errors:
            print(f"Errors:     {len(pr.validation_errors)}")
            for name, err in pr.validation_errors:
                print(f"  - {name}: {err}")

    if result.status == "completed":
        verified = analyzer.verify_graph()
        print(f"Graph OK:   {verified}")

        if result.pipeline_result and result.pipeline_result.analyses:
            _print_summary(result.pipeline_result.analyses, project_dir.name, result, pr)
            _open_graph_viewer(analyzer)

    return 0 if result.status in ("completed", "skipped_fresh") else 1


def _print_summary(analyses: list[dict], project_name: str, result: Any, pr: Any) -> None:
    """Print clean stats + actionable highlights after a successful run."""
    # --- Stats ---
    layer_counts: dict[str, int] = {}
    effect_counts: dict[str, int] = {}
    all_bottlenecks: list[str] = []
    all_security: list[tuple[str, str]] = []  # (group, finding)
    all_coupling: list[tuple[str, str]] = []

    for analysis in analyses:
        group_name = analysis["flow_name"]
        for ns in analysis.get("namespaces", []):
            layer = ns.get("layer", "unknown")
            layer_counts[layer] = layer_counts.get(layer, 0) + 1
            for e in ns.get("side_effects", []):
                effect_counts[e] = effect_counts.get(e, 0) + 1
        for b in analysis.get("bottlenecks", []):
            if b:
                all_bottlenecks.append(b)
        for s in analysis.get("security_findings", []):
            if s:
                all_security.append((group_name, s))
        for c in analysis.get("coupling_issues", []):
            if c:
                all_coupling.append((group_name, c))

    cost = pr.cost_summary.get("total_cost_usd", 0) if pr else 0

    print(f"\n{'=' * 64}")
    print(f"  nuclode analyze complete")
    print(f"{'=' * 64}")
    print(f"  {project_name} | {result.namespace_count} namespaces | {pr.groups_total} groups | ${cost:.2f}")
    print()

    # Layers
    layer_parts = [f"{l}({c})" for l, c in sorted(layer_counts.items(), key=lambda x: -x[1])]
    print(f"  Layers:   {' '.join(layer_parts)}")

    # Effects
    if effect_counts:
        effect_parts = [f"{e}({c})" for e, c in sorted(effect_counts.items(), key=lambda x: -x[1])]
        print(f"  Effects:  {' '.join(effect_parts)}")
    else:
        print(f"  Effects:  pure")

    # Security count
    if all_security:
        print(f"  Security: {len(all_security)} finding(s) across {len({s[0] for s in all_security})} group(s)")
    else:
        print(f"  Security: no findings")

    # --- Highlights ---
    if all_bottlenecks or all_security or all_coupling:
        print(f"\n{'-' * 64}")
        print(f"  HIGHLIGHTS")
        print(f"{'-' * 64}")

    if all_bottlenecks:
        print()
        print(f"  Bottlenecks:")
        for b in all_bottlenecks[:5]:
            print(f"    - {b[:80]}")
        if len(all_bottlenecks) > 5:
            print(f"    ... and {len(all_bottlenecks) - 5} more")

    if all_security:
        print()
        print(f"  Security Findings:")
        for group, finding in all_security[:5]:
            print(f"    - [{group}] {finding[:70]}")
        if len(all_security) > 5:
            print(f"    ... and {len(all_security) - 5} more")

    if all_coupling:
        print()
        print(f"  Coupling Issues:")
        for group, issue in all_coupling[:5]:
            print(f"    - [{group}] {issue[:70]}")
        if len(all_coupling) > 5:
            print(f"    ... and {len(all_coupling) - 5} more")

    print(f"\n{'=' * 64}\n")


def _open_graph_viewer(analyzer: Any) -> None:
    """Export interactive HTML graph and open in browser."""
    import subprocess
    import webbrowser

    project_output = analyzer._project_output_dir
    graph_path = project_output / "graph.html"

    try:
        result = subprocess.run(
            ["bv", "--export-graph", str(graph_path)],
            capture_output=True,
            text=True,
            cwd=str(project_output),
            timeout=30,
        )
        if result.returncode == 0 and graph_path.exists():
            url = f"file://{graph_path}"
            print(f"  Graph: {url}")
            print(f"  Opening in browser...")
            webbrowser.open(url)
        else:
            print(f"  Graph export failed: {result.stderr.strip()}")
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        print(f"  Could not export graph: {exc}")


if __name__ == "__main__":
    sys.exit(main())
