"""Context loader for the codebase analysis recipe.

Loads a codebase into the engine context format using a language backend
for structural extraction and direct file reading for source content.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from engine.backends.base import LanguageBackend, StructureResult


@dataclass(frozen=True)
class CodebaseContext:
    """Complete codebase context ready for the engine.

    Attributes:
        project_name: Name of the project (derived from directory name).
        project_dir: Absolute path to the project root.
        structure: Structural metadata from the language backend.
        source_index: Mapping of namespace name to file path (for on-demand source loading).
        structure_summary: Dict representation of structure for prompt injection.
    """

    project_name: str
    project_dir: Path
    structure: StructureResult
    source_index: dict[str, str]
    structure_summary: dict


def load_codebase_context(
    project_dir: Path,
    backend: LanguageBackend,
) -> CodebaseContext:
    """Load a codebase into the engine context format.

    Uses the language backend to extract structural metadata, then builds
    a context object ready for the engine's REPL loop.

    Args:
        project_dir: Root directory of the project to analyze.
        backend: Language backend for structural extraction.

    Returns:
        CodebaseContext with structure and source index.

    Raises:
        FileNotFoundError: If project_dir does not exist.
        ValueError: If no source files are found.
    """
    project_dir = Path(project_dir).resolve()
    if not project_dir.exists():
        raise FileNotFoundError(f"Project directory does not exist: {project_dir}")

    structure = backend.extract_structure(project_dir)

    # Build source index: namespace name -> file path
    source_index = {ns.path: ns.name for ns in structure.namespaces}

    # Build structure summary for prompt injection
    structure_summary = _build_structure_summary(structure, project_dir)

    return CodebaseContext(
        project_name=project_dir.name,
        project_dir=project_dir,
        structure=structure,
        source_index=source_index,
        structure_summary=structure_summary,
    )


def load_source_for_namespace(namespace_path: str) -> str:
    """Load the source code for a specific namespace file.

    Called on-demand by the REPL loop when the root LM needs source
    for a specific namespace.

    Args:
        namespace_path: Path to the source file.

    Returns:
        Source code as string.

    Raises:
        FileNotFoundError: If the file doesn't exist.
    """
    path = Path(namespace_path)
    if not path.exists():
        raise FileNotFoundError(f"Source file not found: {namespace_path}")
    return path.read_text(encoding="utf-8")


def _build_structure_summary(structure: StructureResult, project_dir: Path) -> dict:
    """Build a dict summary of the structure for prompt injection.

    Produces a compact representation suitable for JSON serialization
    and inclusion in the root LM's system prompt.
    """
    namespaces_summary = []
    for ns in structure.namespaces:
        # Make path relative to project dir for readability
        try:
            rel_path = str(Path(ns.path).relative_to(project_dir))
        except ValueError:
            rel_path = ns.path

        ns_dict = {
            "name": ns.name,
            "path": rel_path,
            "layer": ns.layer,
            "requires": ns.requires,
            "functions": ns.functions,
            "has_side_effects": ns.has_side_effects,
        }
        if ns.metadata:
            ns_dict["metadata"] = ns.metadata
        namespaces_summary.append(ns_dict)

    return {
        "namespace_count": len(structure.namespaces),
        "total_source_chars": structure.total_source_chars,
        "extraction_method": structure.extraction_method,
        "dependency_map": structure.dependency_map,
        "namespaces": namespaces_summary,
    }
