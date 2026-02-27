"""Orchestrator for the codebase analysis recipe.

Ties together context loading, staleness detection, engine invocation,
and output verification. This is the entry point for running a codebase analysis.

All artifacts (beads database, metadata) are written to output_dir — the target
project directory is treated as read-only.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from knowledge.backends.base import LanguageBackend
from knowledge.engine.config import EngineConfig, load_config
from knowledge.engine.runner import EngineResult, EngineRunner
from knowledge.recipes.codebase_analysis.beads_tools import get_custom_tools
from knowledge.recipes.codebase_analysis.context_loader import load_codebase_context
from knowledge.recipes.codebase_analysis.prompts import build_analysis_prompt

logger = logging.getLogger(__name__)

# Default output directory: nuclode/.beads/
_DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / ".beads"


class StalenessStatus(Enum):
    FRESH = "fresh"
    STALE = "stale"
    NO_PRIOR_ANALYSIS = "no_prior_analysis"
    NO_BEADS = "no_beads"


@dataclass(frozen=True)
class StalenessResult:
    """Result of staleness check.

    Attributes:
        status: Whether the existing analysis is fresh, stale, or missing.
        last_sha: Git SHA of the last analysis, or None.
        current_sha: Current HEAD SHA, or None.
        changed_files: List of files changed since last analysis.
        changed_namespaces: Namespace names affected by changes.
    """

    status: StalenessStatus
    last_sha: str | None
    current_sha: str | None
    changed_files: list[str]
    changed_namespaces: list[str]


@dataclass(frozen=True)
class AnalysisResult:
    """Result of a codebase analysis run.

    Attributes:
        status: "completed", "skipped_fresh", "budget_exceeded", "error".
        engine_result: The raw engine result, if engine was invoked.
        staleness: The staleness check result.
        namespace_count: Number of namespaces analyzed.
        commit_sha: Git SHA stored as metadata after analysis.
    """

    status: str
    engine_result: EngineResult | None
    staleness: StalenessResult
    namespace_count: int
    commit_sha: str | None


class CodebaseAnalyzer:
    """Orchestrates codebase analysis from start to finish.

    Handles: staleness detection, context loading, engine invocation,
    metadata storage, and graph verification.

    The target project_dir is read-only — all artifacts are written to output_dir.
    """

    def __init__(
        self,
        project_dir: Path,
        backend: LanguageBackend,
        config: EngineConfig | None = None,
        output_dir: Path | None = None,
    ) -> None:
        self._project_dir = Path(project_dir).resolve()
        self._backend = backend
        self._config = config or load_config()
        self._output_dir = Path(output_dir) if output_dir else _DEFAULT_OUTPUT_DIR

    @property
    def _db_path(self) -> Path:
        """Path to the shared beads database."""
        return self._output_dir / "beads.db"

    @property
    def _metadata_path(self) -> Path:
        """Path to per-project analysis metadata."""
        return self._output_dir / "projects" / self._project_dir.name / "analysis_metadata.json"

    def check_staleness(self) -> StalenessResult:
        """Check whether the existing analysis is stale.

        Compares the stored analysis SHA against current HEAD.
        Maps changed files to affected namespaces.

        Returns:
            StalenessResult with status and change details.
        """
        # Check if output directory exists (replaces checking project_dir/.beads)
        if not self._output_dir.exists():
            return StalenessResult(
                status=StalenessStatus.NO_BEADS,
                last_sha=None,
                current_sha=_get_current_sha(self._project_dir),
                changed_files=[],
                changed_namespaces=[],
            )

        # Check for prior analysis metadata
        if not self._metadata_path.exists():
            return StalenessResult(
                status=StalenessStatus.NO_PRIOR_ANALYSIS,
                last_sha=None,
                current_sha=_get_current_sha(self._project_dir),
                changed_files=[],
                changed_namespaces=[],
            )

        # Load last analysis SHA
        try:
            metadata = json.loads(self._metadata_path.read_text(encoding="utf-8"))
            last_sha = metadata.get("commit_sha")
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read analysis metadata: %s", exc)
            return StalenessResult(
                status=StalenessStatus.NO_PRIOR_ANALYSIS,
                last_sha=None,
                current_sha=_get_current_sha(self._project_dir),
                changed_files=[],
                changed_namespaces=[],
            )

        if not last_sha:
            return StalenessResult(
                status=StalenessStatus.NO_PRIOR_ANALYSIS,
                last_sha=None,
                current_sha=_get_current_sha(self._project_dir),
                changed_files=[],
                changed_namespaces=[],
            )

        current_sha = _get_current_sha(self._project_dir)

        if last_sha == current_sha:
            return StalenessResult(
                status=StalenessStatus.FRESH,
                last_sha=last_sha,
                current_sha=current_sha,
                changed_files=[],
                changed_namespaces=[],
            )

        # Get changed files (reads from target project — read-only)
        changed_files = _get_changed_files(self._project_dir, last_sha, current_sha)

        # Map to namespaces using the backend
        changed_namespaces = _map_files_to_namespaces(
            changed_files, self._project_dir, self._backend
        )

        status = StalenessStatus.STALE if changed_namespaces else StalenessStatus.FRESH

        return StalenessResult(
            status=status,
            last_sha=last_sha,
            current_sha=current_sha,
            changed_files=changed_files,
            changed_namespaces=changed_namespaces,
        )

    def run(
        self,
        force: bool = False,
        mode: str = "structure",
    ) -> AnalysisResult:
        """Run codebase analysis.

        Args:
            force: If True, skip staleness check and run full analysis.
            mode: "structure" (default) or "security".

        Returns:
            AnalysisResult with status and details.
        """
        logger.info("Checking staleness for %s", self._project_dir.name)
        staleness = self.check_staleness()
        logger.info("Staleness: %s", staleness.status.value)

        # Skip if fresh (unless forced)
        if not force and staleness.status == StalenessStatus.FRESH:
            logger.info("Analysis is fresh, skipping (use --force to override)")
            return AnalysisResult(
                status="skipped_fresh",
                engine_result=None,
                staleness=staleness,
                namespace_count=0,
                commit_sha=staleness.current_sha,
            )

        # Load context (reads from target project — read-only)
        logger.info("Loading codebase context from %s", self._project_dir)
        try:
            context = load_codebase_context(self._project_dir, self._backend)
        except (FileNotFoundError, ValueError) as exc:
            logger.error("Failed to load codebase context: %s", exc)
            return AnalysisResult(
                status="error",
                engine_result=None,
                staleness=staleness,
                namespace_count=0,
                commit_sha=None,
            )

        logger.info(
            "Context loaded: %d namespaces, project=%s",
            len(context.structure.namespaces),
            context.project_name,
        )

        # Build prompt
        logger.info("Building analysis prompt (mode=%s)", mode)
        prompt = build_analysis_prompt(
            project_name=context.project_name,
            structure_summary=context.structure_summary,
            mode=mode,
        )

        # Get beads tools (writes to output_dir via db_path)
        try:
            custom_tools = get_custom_tools(self._db_path)
        except (TypeError, ValueError):
            logger.warning("Beads tools unavailable, running without them")
            custom_tools = {}

        # Run engine
        logger.info(
            "Starting engine: root=%s, sub_high=%s, sub_low=%s",
            self._config.root_model,
            self._config.sub_lm_high_model,
            self._config.sub_lm_low_model,
        )
        runner = EngineRunner(self._config)
        engine_result = runner.run(
            context=context.structure_summary,
            custom_tools=custom_tools,
            system_prompt=prompt,
            structure_summary=context.structure_summary,
        )

        logger.info("Engine finished: status=%s, iterations=%d", engine_result.status, engine_result.iterations)

        # Store metadata on success (writes to output_dir)
        commit_sha = staleness.current_sha
        if engine_result.status == "completed" and commit_sha:
            self.store_analysis_metadata(commit_sha)

        return AnalysisResult(
            status=engine_result.status,
            engine_result=engine_result,
            staleness=staleness,
            namespace_count=len(context.structure.namespaces),
            commit_sha=commit_sha,
        )

    def run_incremental(
        self,
        changed_namespaces: list[str],
        mode: str = "structure",
    ) -> AnalysisResult:
        """Re-analyze only changed namespaces.

        Args:
            changed_namespaces: List of namespace names to re-analyze.
            mode: "structure" or "security".

        Returns:
            AnalysisResult with incremental analysis details.
        """
        staleness = self.check_staleness()

        # Load full context but filter to changed namespaces
        context = load_codebase_context(self._project_dir, self._backend)

        # Filter structure summary to only changed namespaces
        filtered_summary = dict(context.structure_summary)
        filtered_summary["namespaces"] = [
            ns for ns in filtered_summary.get("namespaces", [])
            if ns.get("name") in changed_namespaces
        ]
        filtered_summary["namespace_count"] = len(filtered_summary["namespaces"])
        filtered_summary["incremental"] = True
        filtered_summary["changed_namespaces"] = changed_namespaces

        prompt = build_analysis_prompt(
            project_name=context.project_name,
            structure_summary=filtered_summary,
            mode=mode,
        )

        try:
            custom_tools = get_custom_tools(self._db_path)
        except (TypeError, ValueError):
            custom_tools = {}

        runner = EngineRunner(self._config)
        engine_result = runner.run(
            context=filtered_summary,
            custom_tools=custom_tools,
            system_prompt=prompt,
            structure_summary=filtered_summary,
        )

        commit_sha = staleness.current_sha
        if engine_result.status == "completed" and commit_sha:
            self.store_analysis_metadata(commit_sha)

        return AnalysisResult(
            status=engine_result.status,
            engine_result=engine_result,
            staleness=staleness,
            namespace_count=len(changed_namespaces),
            commit_sha=commit_sha,
        )

    def verify_graph(self) -> bool:
        """Verify the beads graph has structure beads.

        Checks that bd query --tag structure returns results.
        Uses --db flag to point at the output_dir database.

        Returns:
            True if structure beads exist.
        """
        try:
            result = subprocess.run(
                ["bd", "--db", str(self._db_path), "query", "--filter", "tag:structure"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0 and bool(result.stdout.strip())
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def store_analysis_metadata(self, commit_sha: str) -> None:
        """Store the commit SHA and analysis metadata for staleness detection.

        Writes to output_dir/projects/<project_name>/analysis_metadata.json.

        Args:
            commit_sha: The git SHA to record.
        """
        self._metadata_path.parent.mkdir(parents=True, exist_ok=True)

        metadata = {
            "commit_sha": commit_sha,
            "backend": self._backend.name,
        }

        self._metadata_path.write_text(
            json.dumps(metadata, indent=2),
            encoding="utf-8",
        )
        logger.info("Stored analysis metadata: SHA=%s", commit_sha)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _get_current_sha(project_dir: Path) -> str | None:
    """Get the current HEAD SHA for the project."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def _get_changed_files(
    project_dir: Path, from_sha: str, to_sha: str | None
) -> list[str]:
    """Get files changed between two commits."""
    to_ref = to_sha or "HEAD"
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{from_sha}..{to_ref}"],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
            timeout=10,
        )
        if result.returncode == 0:
            return [f for f in result.stdout.strip().splitlines() if f]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return []


def _map_files_to_namespaces(
    changed_files: list[str],
    project_dir: Path,
    backend: LanguageBackend,
) -> list[str]:
    """Map changed file paths to namespace names.

    Uses the backend to extract structure, then matches changed files
    against known namespace paths.
    """
    if not changed_files:
        return []

    # Only consider source files the backend would process
    source_extensions = {".clj", ".cljc", ".cljs"}
    source_changes = [
        f for f in changed_files
        if Path(f).suffix in source_extensions
    ]

    if not source_changes:
        return []

    try:
        structure = backend.extract_structure(project_dir)
    except (FileNotFoundError, ValueError):
        return []

    # Match changed files against namespace paths
    changed_namespaces: list[str] = []
    for ns in structure.namespaces:
        # Compare using relative paths
        try:
            ns_rel = str(Path(ns.path).relative_to(project_dir))
        except ValueError:
            ns_rel = ns.path

        if ns_rel in source_changes or ns.path in source_changes:
            changed_namespaces.append(ns.name)

    return changed_namespaces
