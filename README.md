# nuclode

A framework that makes AI-assisted development deterministic and reliable.

Nuclode equips engineers with a structured AI workspace: specialized agents, deterministic codebase analysis, and coding guardrails that produce consistent, high-quality code — regardless of project or codebase.

```
┌─────────────────────────────────────────────────────┐
│  Agents                                             │
│  Specialized AI team with structured workflows      │
│  for planning, building, reviewing, and securing    │
├─────────────────────────────────────────────────────┤
│  Knowledge                                          │
│  Recursive chunking & dependency graphing produce   │
│  stable, reproducible context from any codebase     │
├─────────────────────────────────────────────────────┤
│  Workspace                                          │
│  Config, guardrails, and coding standards           │
│  installed directly into Claude Code                │
└─────────────────────────────────────────────────────┘
```

Install once. Every project gets the same team, the same analysis depth, the same quality bar.

## Install

```bash
git clone https://github.com/yourusername/nuclode.git ~/dev/nuclode
cd ~/dev/nuclode && ./nuclode install
```

Installs all dependencies, configures your workspace, and adds the `nuclode` CLI to your PATH.

## How it works

**Knowledge layer** — Codebases are larger than any context window. Nuclode recursively chunks your code into a dependency graph, then programmatically manages what context reaches each agent — the right depth, for the right task, every time.

```bash
nuclode analyze /path/to/project
```

**Agent layer** — Five specialized agents consume the knowledge graph and follow structured workflows. Each operates on the same stable understanding of your code.

| Agent | Command | Role |
|-------|---------|------|
| **Planner** | `/agents:code-planner` | Architecture and design |
| **Implementer** | `/agents:code-implementer` | Write code from plans |
| **Reviewer** | `/agents:code-reviewer` | Quality and correctness |
| **Test Writer** | `/agents:test-writer` | Generate test coverage |
| **Defender** | `/agents:active-defender` | Security testing |

**Workspace layer** — Coding standards, network guardrails, and cost limits run underneath everything, keeping output consistent and safe.

## Beads

Beads is the persistent memory system that stores and surfaces knowledge artifacts. When the engine chunks your codebase, the results are stored as beads — structured, linked, queryable units of context that persist across sessions.

```bash
nuclode init              # initialize beads in a project
bd ready                  # see available work
bd query --filter tag:structure   # query the knowledge graph
bv --robot-graph --fmt mermaid    # visualize dependencies
```

Agents automatically receive relevant beads context at session start — planners see the full architectural graph, implementers see the namespaces they're working in, reviewers see blast radius. The depth is matched to the agent's role.

This means a new team member can clone a repo, run `bd ready`, and have the same codebase understanding that took the previous session hours to build.

See [docs/BEADS_WORKFLOW.md](docs/BEADS_WORKFLOW.md) for details.

## Project structure

```
nuclode/
├── workspace/          # → installs to ~/.claude/
│   ├── agents/         #   5 specialized agents
│   ├── commands/       #   slash commands
│   ├── skills/         #   agent capabilities
│   ├── hooks/          #   network guardrails
│   ├── beads/          #   persistent memory
│   ├── CLAUDE.md       #   coding standards
│   └── settings.json   #   workspace config
│
├── knowledge/          # deterministic context engine
│   ├── engine/         #   recursive chunking + cost guardrails
│   ├── recipes/        #   structured analysis pipelines
│   └── backends/       #   language-specific extractors
│
├── nuclode             # CLI (install, update, analyze, init)
└── tests/
```

## Extending Nuclode

Nuclode provides the framework. Org-specific standards, tools, and integrations are distributed as plugins through the [ai-agents-plugins](https://github.com/nubank/ai-agents-plugins) marketplace.

```bash
/plugin install glean-mcp@nubank-ai-agents-plugins
/plugin install clojure-lsp@nubank-ai-agents-plugins
```

Plugins add skills, MCP servers, slash commands, agents, and hooks. Nuclode's knowledge layer amplifies every plugin — when agents have a stable dependency graph of your codebase, every tool they use gets better context to work with.

See the [marketplace contributing guide](https://github.com/nubank/ai-agents-plugins/blob/main/CONTRIBUTING.md) for publishing your own.

## CLI

```bash
nuclode install       # first-time setup (run as ./nuclode install from repo)
nuclode update        # pull latest and re-install
nuclode analyze       # run codebase analysis on a project
nuclode init          # initialize beads in a project
```

## Shell helpers

```bash
cw                    # create a git worktree and launch Claude Code in it
remove-worktrees      # clean up old worktrees
```

These are added to your shell profile automatically during setup.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Knowledge Engine](docs/KNOWLEDGE.md)
- [Beads Workflow](docs/BEADS_WORKFLOW.md)
- [Customization](docs/CUSTOMIZATION.md)

## License

MIT
