"""Analysis system prompts and layer-specific sub-LM prompts."""

from __future__ import annotations

CODEBASE_ANALYSIS_PROMPT = """\
You are analyzing a codebase to produce a structural knowledge graph as beads.

## Available Tools

In this REPL environment, you have access to:
- `llm_query(prompt, tier="high")` — call a sub-LM. tier="high" for Sonnet (judgment tasks), tier="low" for Haiku (mechanical tasks)
- `llm_query_batched(prompts, tier)` — parallel sub-LM calls (list of prompts)
- `nrepl_eval(code)` — evaluate code in the language backend (if available)
- `create_bead(title, body, tags)` — create a bead in the graph
- `link_beads(from_id, to_id, rel_type)` — link two beads ("depends-on", "relates-to", "blocks")
- `tag_bead(bead_id, tags)` — add tags to a bead
- `print()` — output feedback to yourself
- `FINAL()` — signal completion

## Your Task

You have received structural metadata about the project "{project_name}". The metadata includes:
- Namespace names and file paths
- Dependency maps (:require declarations)
- Function signatures
- Diplomat layer classifications (adapter/controller/logic/model/wire)
- Side-effect markers (db, kafka, http, etc.)

### Steps

1. **Review the structure** — examine the namespace list, dependency map, and layer classifications.
2. **Group by analysis tier:**
   - Logic + Model namespaces → deep analysis (tier="high", Sonnet sub-LMs)
   - Controller namespaces → medium analysis (tier="high", Sonnet sub-LMs)
   - Adapter + Wire namespaces → light analysis (tier="low", Haiku sub-LMs)
3. **Fan out analysis** — write Python code that calls `llm_query_batched()` per group.
   Each sub-LM prompt should ask for: purpose, key functions, external dependencies, security surface.
4. **Create beads** — for each namespace, call `create_bead()` with:
   - Title: the namespace name
   - Body: dual-format markdown (see format below)
   - Tags: from the tag taxonomy
5. **Link beads** — based on the dependency map, call `link_beads()`:
   - Same-service deps → "depends-on"
   - External libs/cross-service → "relates-to"
6. **Call FINAL()** when all beads are created and linked.

## Tag Taxonomy

- Layer: `diplomat-adapter`, `diplomat-controller`, `diplomat-logic`, `diplomat-model`, `diplomat-wire`
- Side effects: `has-side-effects`, `pure`
- Infrastructure: `has-db`, `has-kafka`, `has-http`, `has-grpc`
- Security: `has-auth`, `has-validation`, `needs-validation`, `handles-pii`
- Structure: `structure` (all structure beads), `entry-point`, `utility`

## Bead Body Format

```
## Purpose
[What this namespace does — 1-2 sentences]

## Key Functions
- `function-name [args]` — description

## External Dependencies
- **DB (Datomic):** what it reads/writes
- **Kafka:** topics it produces/consumes
- **HTTP:** services it calls

## Security Surface
- [Security observations]

## Diplomat Layer
[Layer name] (layer N of 5)

## Requires
- [list of required namespaces]
```

## Structure Data

{structure_json}
"""

LAYER_PROMPTS: dict[str, str] = {
    "logic": (
        "Analyze this Clojure namespace deeply. Focus on:\n"
        "- Business rules and domain logic\n"
        "- Data transformations and validation\n"
        "- State transitions and side effects\n"
        "- Error handling patterns\n"
        "- Security surface (input validation, auth checks)\n\n"
        "Namespace: {namespace}\n"
        "Source:\n```clojure\n{source}\n```\n\n"
        "Return a structured analysis with: purpose, key functions, "
        "external dependencies, and security observations."
    ),
    "model": (
        "Analyze this Clojure namespace deeply. Focus on:\n"
        "- Data shapes and schemas\n"
        "- Entity relationships\n"
        "- Validation rules and specs\n"
        "- Immutability patterns\n\n"
        "Namespace: {namespace}\n"
        "Source:\n```clojure\n{source}\n```\n\n"
        "Return a structured analysis with: purpose, key data structures, "
        "schemas, and entity relationships."
    ),
    "controller": (
        "Analyze this Clojure namespace at medium depth. Focus on:\n"
        "- Request routing and dispatch\n"
        "- Authentication and authorization checks\n"
        "- Error handling and response formatting\n"
        "- Input validation at boundary\n\n"
        "Namespace: {namespace}\n"
        "Source:\n```clojure\n{source}\n```\n\n"
        "Return a structured analysis with: purpose, key endpoints/handlers, "
        "auth checks, and error handling."
    ),
    "adapter": (
        "Analyze this Clojure namespace lightly. Focus on:\n"
        "- Serialization and deserialization\n"
        "- Protocol mapping and data transformation\n"
        "- External system integration points\n\n"
        "Namespace: {namespace}\n"
        "Source:\n```clojure\n{source}\n```\n\n"
        "Return a brief analysis with: purpose, transformation pattern, "
        "and external system it adapts."
    ),
    "wire": (
        "Analyze this Clojure namespace lightly. Focus on:\n"
        "- Wire format schemas (in/out)\n"
        "- Data shape transformations\n"
        "- Serialization format\n\n"
        "Namespace: {namespace}\n"
        "Source:\n```clojure\n{source}\n```\n\n"
        "Return a brief analysis with: purpose, wire format, and "
        "key schema definitions."
    ),
}

_GENERIC_LAYER_PROMPT = (
    "Analyze this Clojure namespace. Focus on:\n"
    "- Purpose and responsibility\n"
    "- Key functions and their roles\n"
    "- Dependencies and side effects\n\n"
    "Namespace: {namespace}\n"
    "Source:\n```clojure\n{source}\n```\n\n"
    "Return a structured analysis with: purpose, key functions, "
    "dependencies, and any security observations."
)


def build_analysis_prompt(
    project_name: str,
    structure_summary: dict,
    mode: str = "structure",
) -> str:
    """Build the complete analysis prompt for the root LM.

    Args:
        project_name: Name of the project being analyzed.
        structure_summary: Structural metadata from language backend.
        mode: "structure" (default) or "security" (all Sonnet sub-LMs).

    Returns:
        Complete system prompt string.
    """
    import json

    structure_json = json.dumps(structure_summary, indent=2, default=str)

    prompt = CODEBASE_ANALYSIS_PROMPT.format(
        project_name=project_name,
        structure_json=structure_json,
    )

    if mode == "security":
        prompt += (
            "\n\n## Security Mode\n"
            "All sub-LM calls should use tier='high' (Sonnet) regardless of layer. "
            "Focus analysis on security surface, attack vectors, and vulnerability patterns."
        )

    return prompt


def get_layer_prompt(layer: str) -> str:
    """Get the sub-LM prompt template for a Diplomat layer.

    Falls back to a generic prompt if layer is unknown.
    """
    return LAYER_PROMPTS.get(layer, _GENERIC_LAYER_PROMPT)
