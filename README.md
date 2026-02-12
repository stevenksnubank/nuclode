# nuclode

> nu + claude + code = nucleotide

A portable, cloneable agentic development workspace for [Claude Code](https://claude.ai/claude-code). Ships with 5 specialized AI agents, [beads](https://github.com/steveyegge/beads) integration for persistent agent memory, and a layered architecture for team/company customization.

## Quick Start

```bash
# Clone
git clone https://github.com/yourusername/nuclode.git ~/dev/nuclode

# Install (interactive - picks layers, installs tools)
cd ~/dev/nuclode && ./setup.sh

# Start using
claude  # Your workspace is ready
```

## What's Included

### 5 Specialized Agents

| Agent | Model | Purpose |
|-------|-------|---------|
| **code-planner** | Opus 4.6 + Thinking | Architectural planning, implementation design |
| **code-implementer** | Sonnet 4.5 | Execute approved plans, write code |
| **code-reviewer** | Opus 4.6 + Thinking | Code review, quality analysis |
| **active-defender** | Opus 4.6 + Thinking | Offensive security testing |
| **test-writer** | Sonnet 4.5 | Generate comprehensive tests |

### Beads Integration

Persistent agent memory across sessions via git-backed issue tracking:

```bash
nuclode init          # Initialize beads in any project
bd ready              # See available work
bv --robot-next       # Agent-friendly task selection
```

### Layered Architecture

```
nuclode/
├── core/             # Generic workspace (works for anyone)
├── layers/
│   └── nubank/       # Company-specific extensions
└── setup.sh          # Merges core + selected layers → ~/.claude
```

## Layer System

The core provides generic coding standards and agent configurations. Layers add company-specific or domain-specific extensions:

- **Core**: Coding standards, 5 agents, beads templates, security standards
- **Layers**: Company tools (MCP servers), naming conventions, compliance requirements

Layers are applied during `setup.sh` and merged into `~/.claude`:
- `CLAUDE.md` files are concatenated
- `settings.json` files are deep-merged
- `.mcp.json` servers are combined
- Agent overrides extend tool/capability lists

### Creating a Layer

```bash
mkdir -p layers/mycompany
# Add: CLAUDE.md, settings.json, .mcp.json, agents/*-overrides.json
./setup.sh --layer mycompany
```

## Prerequisites

- [Claude Code CLI](https://claude.ai/claude-code)
- [beads](https://github.com/steveyegge/beads) (optional, setup.sh can install)
- [beads viewer](https://github.com/Dicklesworthstone/beads_viewer) (optional)

## Commands

### nuclode CLI

```bash
nuclode init [dir]    # Initialize beads + project template
nuclode update        # Pull latest and re-run setup
nuclode layers        # List available layers
```

### Shell Functions

```bash
cw                    # claude-worktree: worktree + Claude in one command
remove-worktrees      # Clean up worktrees for current repo
```

### Agent Workflow

```bash
/agents:code-planner Add user authentication     # Plan
/agents:code-implementer [paste approved plan]    # Build
/agents:code-reviewer src/auth.py                 # Review
/agents:active-defender Test auth for bypasses    # Security
/agents:test-writer src/auth.py                   # Tests
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) - Layering system and config merging
- [Beads Workflow](docs/BEADS_WORKFLOW.md) - Agent-beads interaction flow
- [Customization](docs/CUSTOMIZATION.md) - Creating layers and adding agents

## License

MIT
