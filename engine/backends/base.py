"""Abstract base class for nuclode language backends.

Language backends provide language-specific intelligence to the nuclode engine.
They handle parsing, structure extraction, and (optionally) runtime evaluation
for a particular language ecosystem.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class NamespaceInfo:
    """Structural info about a single namespace/module."""

    path: str
    name: str
    requires: list[str]
    functions: list[str]
    layer: str | None
    has_side_effects: bool
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class StructureResult:
    """Complete structural extraction result for a project."""

    namespaces: list[NamespaceInfo]
    dependency_map: dict[str, list[str]]
    total_source_chars: int
    extraction_method: str


class LanguageBackend(ABC):
    """Abstract interface for language-specific backends."""

    @abstractmethod
    def extract_structure(self, project_dir: Path) -> StructureResult:
        """Extract structural metadata from the project. Should be fast and free (no API calls)."""

    @abstractmethod
    def eval(self, code: str) -> str:
        """Evaluate code in the language runtime. Returns result as string."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this backend's runtime is available."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Backend name for logging/config (e.g., 'clojure-nrepl')."""
