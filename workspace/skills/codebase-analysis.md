---
name: codebase-analysis
description: Analyze a codebase to produce a persistent structure graph as beads. Uses the nuclode RLM-inspired engine with language-specific backends.
argument-hint: "[--security] [--force] [project-dir]"
---

# Codebase Analysis

Produces a **persistent codebase structure graph** as beads — one bead per namespace with dependency edges, Diplomat layer tags, and dual-format bodies (human-readable markdown + machine-queryable tags).

## When to Use

- First time working in a codebase (no existing structure beads)
- After significant code changes (staleness detected automatically)
- Before planning features (planner uses the graph to understand architecture)
- Before security review (defender uses the graph to map attack surfaces)

## Modes

```
/codebase-analysis                    # Structure analysis (default)
/codebase-analysis --security         # Security-focused analysis (all Sonnet sub-LMs)
/codebase-analysis --force            # Force full re-analysis (skip staleness check)
/codebase-analysis /path/to/project   # Analyze a specific project directory
```

## What It Produces

### Structure Beads
One bead per namespace containing:
- **Purpose** — what the namespace does
- **Key Functions** — function signatures and descriptions
- **External Dependencies** — DB, Kafka, HTTP services used
- **Security Surface** — auth checks, validation gaps, PII handling
- **Diplomat Layer** — adapter/controller/logic/model/wire classification
- **Requires** — direct dependencies

### Dependency Edges
- `depends-on` — direct `:require` within the same service
- `relates-to` — external libraries or cross-service dependencies

### Tags (queryable)
- Layer: `diplomat-adapter`, `diplomat-controller`, `diplomat-logic`, `diplomat-model`, `diplomat-wire`
- Side effects: `has-side-effects`, `pure`
- Infrastructure: `has-db`, `has-kafka`, `has-http`, `has-grpc`
- Security: `has-auth`, `has-validation`, `needs-validation`, `handles-pii`
- All structure beads: `structure`

## Pre-conditions

- Source files exist in the project (`.clj`, `.cljc`, or other supported languages)
- `bd` (beads CLI) is installed
- For Clojure projects: Clojure nREPL enhances analysis but is not required (falls back to static parsing)

## Post-conditions

- `.beads/` directory populated with structure beads and dependency edges
- `.beads/analysis_metadata.json` stores the commit SHA for staleness detection
- Beads viewable via `bd query --filter tag:structure`
- Graph viewable via `bv --robot-graph --fmt mermaid`

## How It Works

```
1. Language backend extracts structure (free, local)
   └── Clojure nREPL or static parse: namespaces, requires, functions, layers

2. Two-stage decision gate
   ├── Stage 1: Token threshold (~50K) → direct or fan-out
   └── Stage 2: Opus reviews structure → can override

3. Engine runs (Opus + extended thinking)
   ├── Below threshold: single Opus call analyzes everything
   └── Above threshold: REPL loop
       ├── Root LM (Opus) writes Python code
       ├── Code fans out llm_query_batched() to sub-LMs
       │   ├── Logic/Model → Sonnet (deep analysis)
       │   ├── Controller → Sonnet (medium analysis)
       │   └── Adapter/Wire → Haiku (light analysis)
       ├── Results create beads via bd CLI
       └── FINAL() when complete

4. Metadata stored for incremental updates
   └── Next run only re-analyzes changed namespaces
```

## Staleness Detection

Runs automatically before analysis:
1. Checks `.beads/analysis_metadata.json` for last analysis SHA
2. Runs `git diff --name-only <sha>..HEAD`
3. Maps changed files to affected namespaces
4. If no source files changed → skips (graph is fresh)
5. If source files changed → re-analyzes only those namespaces

Use `--force` to bypass staleness and run full analysis.

## Cost Estimates

| Service Size | Namespaces | First Run | Incremental |
|-------------|-----------|-----------|-------------|
| Small       | ~20       | $2-5      | $1-2        |
| Medium      | ~35       | $2-5      | $1-3        |
| Large BFF   | ~200      | $6-15     | $2-5        |
| Monolith    | ~400+     | $12-27    | $3-7        |

Cost guardrails are config-driven. Default: warn at $30, stop at $50.

## Integration with Agents

After analysis, the structure graph feeds into existing agent tiers:

- **Planner (Tier 3):** Full graph via `bv --robot-insights` — plans against the map
- **Defender (Tier 3):** Full graph — maps attack surfaces via `bd query --filter tag:has-side-effects`
- **Reviewer (Tier 2):** Relevant subgraph for blast radius assessment
- **Implementer (Tier 1):** Task beads linked to structure beads

## Example Usage

```bash
# Planner analyzes codebase before planning a feature
/codebase-analysis

# After analysis, planner can query the graph
bd query --filter tag:diplomat-logic    # all business logic namespaces
bd query --filter tag:has-kafka         # all Kafka-connected namespaces
bv --robot-graph --fmt mermaid          # dependency graph

# Defender runs security-focused analysis
/codebase-analysis --security

# Query security surface
bd query --filter tag:needs-validation  # namespaces missing validation
bd query --filter tag:handles-pii      # PII-handling namespaces
```
