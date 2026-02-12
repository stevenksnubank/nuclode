# Architecture

## Overview

nuclode uses a layered architecture to separate generic workspace configuration from company/team-specific extensions. The `setup.sh` script merges selected layers into `~/.claude`.

## Directory Structure

```
nuclode/
├── core/                     # Generic workspace (always installed)
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
├── layers/                   # Company/team-specific extensions
│   └── nubank/
│       ├── CLAUDE.md         # Nubank-specific standards
│       ├── settings.json     # Plugins (superpowers, glean)
│       ├── .mcp.json         # Additional MCP servers (clojure)
│       └── agents/           # Agent overrides
├── templates/                # Per-project templates
├── shell/                    # Shell functions (worktrees)
├── setup.sh                  # Interactive installer
└── docs/                     # Documentation
```

## How Merging Works

When `setup.sh` runs, it:

### 1. Installs Core
Copies all `core/` files into `~/.claude/` as the base configuration.

### 2. Applies Layers (in order)

For each selected layer:

**CLAUDE.md** - Appended to the end of `~/.claude/CLAUDE.md` with a `---` separator:
```
[core CLAUDE.md content]
---
[layer CLAUDE.md content]
```

**settings.json** - Deep-merged using Python:
```json
// core
{"model": "opus"}

// + layer
{"enabledPlugins": {"superpowers@marketplace": true}}

// = result
{"model": "opus", "enabledPlugins": {"superpowers@marketplace": true}}
```

**.mcp.json** - MCP servers are combined:
```json
// core: sequential-thinking
// + layer: clojure
// = both servers available
```

**Agent Overrides** - `*-overrides.json` files extend agent configurations:
```json
// layers/nubank/agents/code-planner-overrides.json
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

## Design Principles

1. **Core is generic** - No company-specific references in `core/`
2. **Layers are additive** - Layers extend, never replace core
3. **User files are sacred** - Memory and local settings always preserved
4. **Beads is per-project** - Not global, keeps context focused
5. **Setup is idempotent** - Safe to re-run anytime
