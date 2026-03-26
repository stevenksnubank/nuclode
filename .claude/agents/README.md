# Claude Code Agent Workspace

This directory contains your global AI agents for specialized development tasks. These agents follow coding standards and can be invoked in any project.

## Available Agents

### Development Agents

| Agent | Command | Model | Purpose |
|-------|---------|-------|---------|
| **nuclode Guide** | default / `/agents:nuclode-guide` | Sonnet (latest) | Triage, routing, quick fixes |
| **Code Planner** | `/agents:code-planner` | Opus (latest) + Thinking | Architectural planning, implementation design |
| **Code Implementer** | `/agents:code-implementer` | Sonnet (latest) | Execute approved plans, write code |
| **Code Reviewer** | `/agents:code-reviewer` | Opus (latest) + Thinking | Code review, quality analysis |
| **Active Defender** | `/agents:active-defender` | Opus (latest) + Thinking | Offensive security testing |
| **Test Writer** | `/agents:test-writer` | Sonnet (latest) | Generate comprehensive tests |

### Research & Quality Agents

| Agent | Command | Model | Purpose |
|-------|---------|-------|---------|
| **Research Analyst** | `/agents:research-analyst` | Opus (latest) + Thinking | Deep research with structured output |
| **Claims Auditor** | `/agents:claims-auditor` | Opus (latest) + Thinking | Audit docs for untestable claims |
| **Link Auditor** | `/agents:link-auditor` | Sonnet (latest) | Audit link quality in documents |
| **Glossary Reviewer** | `/agents:glossary-reviewer` | Opus (latest) + Thinking | Review definition quality |
| **Cause Check** | `/agents:cause-check` | Sonnet (latest) | Audit causal language precision |
| **Claude Perf** | `/agents:claude-perf` | Sonnet (latest) | Analyze session performance & costs |

## Model Strategy

| Role | Model | Thinking | Rationale |
|------|-------|----------|-----------|
| Triage/routing | Sonnet (latest) | Disabled | Fast, cheap — routing doesn't need deep reasoning |
| Planning | Opus (latest) | Enabled | Deep reasoning for design decisions |
| Review | Opus (latest) | Enabled | Thorough code analysis |
| Security | Opus (latest) | Enabled | Critical assessment, exploit chaining |
| Implementation | Sonnet (latest) | Disabled | Fast execution from approved plans |
| Test Writing | Sonnet (latest) | Disabled | Efficient pattern-based generation |
| Research | Opus (latest) | Enabled | Deep analysis, source synthesis |
| Claims/Glossary audit | Opus (latest) | Enabled | Precise reasoning about language |
| Link/Cause audit | Sonnet (latest) | Disabled | Pattern matching, fast turnaround |
| Performance analysis | Sonnet (latest) | Disabled | Data parsing, fast aggregation |

**Models use family aliases** (`"opus"`, `"sonnet"`) in agent.json — these auto-resolve to the latest version. When Opus 4.7 or Sonnet 4.7 ships, all agents upgrade automatically.

**Principle**: Invest thinking where decisions are made (planning, review, security). Execute efficiently where decisions are already made (triage, implementation, tests).

## Development Loop

The nuclode-guide agent handles routing automatically. For direct control:

```
Research  →  Plan  →  Annotate  →  Implement  →  Review
(planner)   (planner)  (human+     (implementer)  (reviewer,
                        planner)                    defender,
                                                    test-writer)
```

### Quick Fix
```bash
# Just describe it — guide routes automatically
"Fix the null check in getUserById"
```

### Feature
```bash
# Guide detects multi-file scope, invokes planner
"Add OAuth2 support to the API"
```

### Direct Agent Access
```bash
/agents:code-planner Add user authentication
/agents:code-implementer [paste approved plan]
/agents:code-reviewer Review the auth implementation
/agents:active-defender Test auth for bypass vulnerabilities
/agents:test-writer Add edge case tests for auth
```

## Agent Structure

Each agent directory contains:
```
agent-name/
├── agent.json          # Configuration (model, tools, capabilities)
└── system_prompt.md    # Behavioral instructions
```

## Creating New Agents

1. Create directory: `~/.claude/agents/my-agent/`
2. Add `agent.json` — use `"model": "sonnet"` or `"model": "opus"` (never hardcode versions)
3. Add `system_prompt.md` — reference CLAUDE.md for standards, don't duplicate
4. Create slash command: `~/.claude/commands/agents/my-agent.md`

### agent.json Template
```json
{
  "name": "agent-name",
  "description": "What this agent does",
  "model": "sonnet",
  "extended_thinking": false,
  "capabilities": ["code_analysis"],
  "tools": ["Read", "Grep", "Glob"],
  "project_context": true,
  "max_iterations": 10
}
```
