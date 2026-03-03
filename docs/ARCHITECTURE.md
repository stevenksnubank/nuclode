# Architecture

## Overview

nuclode uses a three-layer architecture: a core workspace (installed into `~/.claude/`), a knowledge engine for deterministic codebase analysis, and a plugin system for org-specific extensions via the [ai-agents-plugins marketplace](https://github.com/nubank/ai-agents-plugins).

The `nuclode` CLI installs the workspace and manages project initialization.

## Directory Structure

```
nuclode/
├── workspace/                # Core workspace (installed → ~/.claude/)
│   ├── CLAUDE.md             # Coding standards, agent descriptions
│   ├── AGENTS.md             # Beads workflow instructions
│   ├── WORKFLOW.md           # Core development loop specification
│   ├── settings.json         # Base settings (model selection)
│   ├── agents/               # 5 agent configurations
│   │   ├── README.md
│   │   ├── code-planner/     # agent.json + system_prompt.md
│   │   ├── code-implementer/
│   │   ├── code-reviewer/
│   │   ├── active-defender/
│   │   └── test-writer/
│   ├── commands/agents/      # Slash command definitions
│   ├── skills/               # Agent capabilities
│   ├── hooks/                # Network guardrails
│   └── beads/                # Beads templates and instructions
├── knowledge/                # Deterministic codebase analysis
│   ├── engine/               # Pipeline runner, chunking, schema validation
│   ├── recipes/              # Analysis recipes (codebase_analysis/)
│   └── backends/             # Language-specific extractors
├── templates/                # Per-project templates
├── shell/                    # Shell functions (worktrees, helpers)
├── nuclode                   # CLI (install, update, analyze, init)
├── docs/                     # Documentation
└── tests/                    # Test suite
```

## How Setup Works

When `nuclode install` runs, it:

### 1. Installs Workspace
Copies all `workspace/` files into `~/.claude/` as the base configuration.

### 2. Applies Marketplace Plugins

Plugins from the [ai-agents-plugins marketplace](https://github.com/nubank/ai-agents-plugins) extend the workspace with company or team-specific configuration. Each plugin can provide:

**CLAUDE.md** - Appended to the end of `~/.claude/CLAUDE.md` with a `---` separator:
```
[workspace CLAUDE.md content]
---
[plugin CLAUDE.md content]
```

**settings.json** - Deep-merged using Python:
```json
// workspace
{"model": "opus"}

// + plugin
{"enabledPlugins": {"superpowers@marketplace": true}}

// = result
{"model": "opus", "enabledPlugins": {"superpowers@marketplace": true}}
```

**Agent Overrides** - `*-overrides.json` files extend agent configurations:
```json
// plugin agents/code-planner-overrides.json
{
  "additional_tools": ["mcp__clojure__read_file"],
  "additional_mcp_servers": ["clojure"],
  "additional_capabilities": ["clojure_project_analysis"]
}
```
These arrays are appended to the agent's existing `tools`, `mcp_servers`, and `capabilities` arrays.

### 3. Preserves User Files
After merging, user-specific files are restored from backup:
- `settings.local.json` - Personal settings overrides
- `memory/` - Agent memory (persistent across sessions)

## Knowledge Layer

The `knowledge/` directory contains a deterministic pipeline for codebase analysis. It is separate from the workspace and is not installed into `~/.claude/`.

- **`knowledge/engine/`** - Pipeline runner with flow-group partitioning (union-find), schema validation, and cost tracking.
- **`knowledge/recipes/`** - Analysis recipes that consume the engine. The first recipe is `codebase_analysis/`, which performs structured analysis of codebases.
- **`knowledge/backends/`** - Language-specific extractors. Currently Clojure via `LanguageBackend` interface.

The knowledge layer is installed as a Python package (via `pyproject.toml`) and can be invoked independently of the workspace.

## Design Principles

1. **Workspace is generic** - No company-specific references in `workspace/`
2. **Plugins are additive** - Marketplace plugins extend, never replace the workspace
3. **User files are sacred** - Memory and local settings always preserved
4. **Beads is per-project** - Not global, keeps context focused
5. **Setup is idempotent** - Safe to re-run anytime
6. **Knowledge is independent** - Analysis engine runs separately from workspace config
