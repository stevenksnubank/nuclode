"""CLI entry point for the codebase analysis recipe.

Usage:
    python -m recipes.codebase_analysis /path/to/project
    python -m recipes.codebase_analysis ~/dev/nu/financial-calculator --mode security
    python -m recipes.codebase_analysis ~/dev/nu/espetinho --force --nrepl-port 7888
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from knowledge.backends.clojure_nrepl import ClojureNREPLBackend
from knowledge.engine.config import load_config
from knowledge.recipes.codebase_analysis.orchestrator import CodebaseAnalyzer


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m recipes.codebase_analysis",
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
        help="Load context and check staleness only — no engine invocation, no API cost.",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
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
        # Load context to show what would be analyzed
        from knowledge.recipes.codebase_analysis.context_loader import load_codebase_context

        ctx = load_codebase_context(project_dir, backend)
        print(f"Namespaces: {len(ctx.structure.namespaces)}")
        for ns in ctx.structure.namespaces:
            print(f"  - {ns.name} ({ns.layer or 'unknown'})")
        print("\nDry run complete — no API calls made.")
        return 0

    # Full analysis
    result = analyzer.run(force=args.force, mode=args.mode)

    print(f"\nResult:     {result.status}")
    print(f"Namespaces: {result.namespace_count}")
    if result.engine_result:
        print(f"Iterations: {result.engine_result.iterations}")
        cost = result.engine_result.cost_summary.get("total_cost_usd", "unknown")
        print(f"Cost:       ${cost}")

    if result.status == "completed":
        verified = analyzer.verify_graph()
        print(f"Graph OK:   {verified}")

    return 0 if result.status in ("completed", "skipped_fresh") else 1


if __name__ == "__main__":
    sys.exit(main())
