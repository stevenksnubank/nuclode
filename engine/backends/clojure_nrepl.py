"""Clojure nREPL backend for extracting structure from Clojure codebases.

When nREPL is available: uses nREPL eval for rich structural extraction.
When nREPL is NOT available: falls back to static file parsing.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from engine.backends.base import LanguageBackend, NamespaceInfo, StructureResult

logger = logging.getLogger(__name__)

_DIPLOMAT_LAYERS: frozenset[str] = frozenset({
    "adapter", "controller", "logic", "model", "wire",
})

_SIDE_EFFECT_MARKERS: frozenset[str] = frozenset({
    "datomic", "kafka", "http-client", "http-kit", "http.client",
    "s3", "redis", "sqs", "sns", "dynamodb", "jdbc", "db",
    "mongo", "elasticsearch", "grpc",
})

_NS_FORM_RE = re.compile(
    r"\(ns\s+([\w.*+!\-'?<>=/.]+)",
    re.DOTALL,
)

_REQUIRE_BLOCK_RE = re.compile(
    r"\(:require\s+(.*?)\)",
    re.DOTALL,
)

_DEFN_RE = re.compile(r"\(defn-?\s+([\w.*+!\-'?<>=/.]+)")

_DEFMETHOD_RE = re.compile(
    r"\(defmethod\s+([\w.*+!\-'?<>=/.]+)\s+([\w.:*+!\-'?<>=/.]+|\[.*?\])"
)

_DEFPROTOCOL_RE = re.compile(r"\(defprotocol\s+([\w.*+!\-'?<>=/.]+)")
_DEFMULTI_RE = re.compile(r"\(defmulti\s+([\w.*+!\-'?<>=/.]+)")

_CLJ_EXTENSIONS: frozenset[str] = frozenset({".clj", ".cljc"})


class ClojureNREPLBackend(LanguageBackend):
    """Clojure nREPL backend with static-parse fallback."""

    def __init__(self, nrepl_port: int | None = None) -> None:
        self._nrepl_port: int | None = nrepl_port

    @property
    def name(self) -> str:
        return "clojure-nrepl"

    def is_available(self) -> bool:
        if self._nrepl_port is None:
            return False
        try:
            import socket
            with socket.create_connection(("127.0.0.1", self._nrepl_port), timeout=2):
                return True
        except (ConnectionRefusedError, OSError, TimeoutError):
            return False

    def eval(self, code: str) -> str:
        raise NotImplementedError(
            "nREPL eval integration pending. "
            "Use extract_structure() which falls back to static parsing."
        )

    def extract_structure(self, project_dir: Path) -> StructureResult:
        project_dir = Path(project_dir)
        if not project_dir.exists():
            raise FileNotFoundError(f"Project directory does not exist: {project_dir}")

        if self._nrepl_port is None:
            self._nrepl_port = _detect_nrepl_port(project_dir)

        if self.is_available():
            try:
                return self._extract_via_nrepl(project_dir)
            except NotImplementedError:
                logger.info("nREPL extraction not yet implemented, falling back to static parse")
            except Exception:
                logger.warning("nREPL extraction failed, falling back to static parse", exc_info=True)

        return self._extract_via_static_parse(project_dir)

    def _extract_via_nrepl(self, project_dir: Path) -> StructureResult:
        raise NotImplementedError("nREPL-based structure extraction pending.")

    def _extract_via_static_parse(self, project_dir: Path) -> StructureResult:
        source_files = _glob_clojure_files(project_dir)
        if not source_files:
            raise ValueError(f"No Clojure source files (.clj, .cljc) found in: {project_dir}")

        namespaces: list[NamespaceInfo] = []
        dependency_map: dict[str, list[str]] = {}
        total_chars = 0

        for file_path in source_files:
            try:
                source = file_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                logger.warning("Skipping unreadable file %s: %s", file_path, exc)
                continue

            total_chars += len(source)
            ns_name, requires = self._parse_ns_form(source)
            if ns_name is None:
                continue

            functions = _extract_functions(source)
            layer = self._classify_diplomat_layer(ns_name, str(file_path))
            has_side_effects = self._detect_side_effects(source)

            metadata: dict = {}
            protocols = _DEFPROTOCOL_RE.findall(source)
            if protocols:
                metadata["protocols"] = protocols
            multimethods = _DEFMULTI_RE.findall(source)
            if multimethods:
                metadata["multimethods"] = multimethods

            ns_info = NamespaceInfo(
                path=str(file_path),
                name=ns_name,
                requires=requires,
                functions=functions,
                layer=layer,
                has_side_effects=has_side_effects,
                metadata=metadata,
            )
            namespaces.append(ns_info)
            dependency_map[ns_name] = requires

        if not namespaces:
            raise ValueError(
                f"Found {len(source_files)} Clojure files but none contained "
                f"a valid (ns ...) form in: {project_dir}"
            )

        return StructureResult(
            namespaces=namespaces,
            dependency_map=dependency_map,
            total_source_chars=total_chars,
            extraction_method="static_parse",
        )

    def _parse_ns_form(self, source: str) -> tuple[str | None, list[str]]:
        ns_match = _NS_FORM_RE.search(source)
        if ns_match is None:
            return None, []

        ns_name = ns_match.group(1)
        ns_region = _extract_ns_region(source)
        requires = _parse_requires(ns_region)
        return ns_name, requires

    def _classify_diplomat_layer(self, namespace_name: str, file_path: str) -> str | None:
        for segment in namespace_name.split("."):
            if segment in _DIPLOMAT_LAYERS:
                return segment
        for part in Path(file_path).parts:
            if part in _DIPLOMAT_LAYERS:
                return part
        return None

    def _detect_side_effects(self, source: str) -> bool:
        source_lower = source.lower()
        return any(marker in source_lower for marker in _SIDE_EFFECT_MARKERS)


def _detect_nrepl_port(project_dir: Path) -> int | None:
    search_dir = project_dir
    for _ in range(4):
        port_file = search_dir / ".nrepl-port"
        if port_file.is_file():
            try:
                port = int(port_file.read_text(encoding="utf-8").strip())
                if 1 <= port <= 65535:
                    return port
            except (ValueError, OSError):
                pass
        parent = search_dir.parent
        if parent == search_dir:
            break
        search_dir = parent
    return None


def _glob_clojure_files(project_dir: Path) -> list[Path]:
    excluded_dirs = {
        "target", ".git", "node_modules", ".cpcache", ".clj-kondo",
        ".lsp", ".shadow-cljs", "classes", "out",
    }
    results: list[Path] = []
    for ext in _CLJ_EXTENSIONS:
        for path in project_dir.rglob(f"*{ext}"):
            if any(excluded in path.parts for excluded in excluded_dirs):
                continue
            results.append(path)
    return sorted(results)


def _extract_ns_region(source: str) -> str:
    idx = source.find("(ns ")
    if idx == -1:
        idx = source.find("(ns\n")
    if idx == -1:
        return ""

    depth = 0
    for i in range(idx, len(source)):
        if source[i] == "(":
            depth += 1
        elif source[i] == ")":
            depth -= 1
            if depth == 0:
                return source[idx:i + 1]
    return source[idx:]


def _parse_requires(ns_region: str) -> list[str]:
    require_match = _REQUIRE_BLOCK_RE.search(ns_region)
    if require_match is None:
        return []

    require_body = require_match.group(1)
    requires: list[str] = []

    bracket_re = re.compile(r"\[\s*([\w.*+!\-'?<>=/.]+)")
    for match in bracket_re.finditer(require_body):
        ns = match.group(1)
        if ns and not ns.startswith(":"):
            requires.append(ns)

    bare_re = re.compile(r"(?<!\[)\b([\w]+(?:\.[\w.*+!\-'?<>=]+)+)\b")
    for match in bare_re.finditer(require_body):
        ns = match.group(1)
        if ns not in requires:
            requires.append(ns)

    return sorted(set(requires))


def _extract_functions(source: str) -> list[str]:
    functions: list[str] = []
    for match in _DEFN_RE.finditer(source):
        functions.append(match.group(1))
    for match in _DEFMETHOD_RE.finditer(source):
        functions.append(f"{match.group(1)} {match.group(2).strip()}")
    return functions
