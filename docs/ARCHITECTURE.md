# Architecture

## Overview

nuclode uses a modular architecture with a core workspace and an optional knowledge layer for AI-powered codebase analysis. Customization is handled through plugins from the [ai-agents-plugins marketplace](https://github.com/nubank/ai-agents-plugins), rather than local layer directories.

The `setup.sh` script installs the workspace into `~/.claude` and configures any selected marketplace plugins.

## Directory Structure

```
nuclode/
├── workspace/                # Core workspace (always installed → ~/.claude/)
│   ├── CLAUDE.md             # Coding standards, agent descriptions
│   ├── AGENTS.md             # Beads workflow instructions
│   ├── settings.json         # Base settings (model selection)
│   ├── .mcp.json             # Base MCP servers (sequential-thinking)
│   ├── agents/               # 5 agent configurations
│   │   ├── README.md
│   │   ├── code-planner/     # agent.json + system_prompt.md
│   │   ├── code-implementer/
│   │   ├── code-reviewer/
│   │   ├── active-defender/
│   │   └── test-writer/
│   ├── commands/agents/      # Slash command definitions
│   └── beads/                # Beads templates and instructions
├── knowledge/                # AI-powered codebase analysis
│   ├── engine/               # RLM-inspired analysis engine
│   │   ├── config.py         # Engine configuration
│   │   ├── runner.py         # Orchestration runner
│   │   └── cost_tracker.py   # Token/cost tracking
│   └── recipes/              # Analysis recipes
│       └── codebase_analysis/ # First recipe: codebase analysis
├── templates/                # Per-project templates
├── shell/                    # Shell functions (worktrees)
├── setup.sh                  # Interactive installer
└── docs/                     # Documentation
```

## How Setup Works

When `setup.sh` runs, it:

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

**.mcp.json** - MCP servers are combined:
```json
// workspace: sequential-thinking
// + plugin: clojure
// = both servers available
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

The `knowledge/` directory contains an RLM-inspired engine for AI-powered codebase analysis. It is separate from the workspace and is not installed into `~/.claude/`.

- **`knowledge/engine/`** - The general-purpose analysis engine with configurable LM routing, cost tracking, and a decision gate for managing large-context analysis.
- **`knowledge/recipes/`** - Specific analysis recipes that consume the engine. The first recipe is `codebase_analysis/`, which performs structured analysis of codebases.

The knowledge layer is installed as a Python package (via `pyproject.toml`) and can be invoked independently of the workspace.

## Design Principles

1. **Workspace is generic** - No company-specific references in `workspace/`
2. **Plugins are additive** - Marketplace plugins extend, never replace the workspace
3. **User files are sacred** - Memory and local settings always preserved
4. **Beads is per-project** - Not global, keeps context focused
5. **Setup is idempotent** - Safe to re-run anytime
6. **Knowledge is independent** - Analysis engine runs separately from workspace config
