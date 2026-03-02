# Claude Code Agent Workspace

This directory contains your global AI agents for specialized development tasks. These agents follow coding standards and can be invoked in any project.

## Available Agents

| Agent | Command | Model | Purpose |
|-------|---------|-------|---------|
| **Code Planner** | `/agents:code-planner` | Opus 4.6 + Thinking | Architectural planning, implementation design |
| **Code Implementer** | `/agents:code-implementer` | Sonnet 4.5 | Execute approved plans, write code |
| **Code Reviewer** | `/agents:code-reviewer` | Opus 4.6 + Thinking | Code review, quality analysis |
| **Active Defender** | `/agents:active-defender` | Opus 4.6 + Thinking | Offensive security testing |
| **Test Writer** | `/agents:test-writer` | Sonnet 4.5 | Generate comprehensive tests |

## Agent Descriptions

### code-planner (Approval-Based - Opus 4.6 + Thinking)
- Architectural planning and implementation design
- Creates detailed, actionable implementation plans
- Follows coding standards
- Produces plans that require user approval
- Uses Opus 4.6 with extended thinking for deep reasoning
- Outputs feed into code-implementer

### code-reviewer (Approval-Based - Opus 4.6 + Thinking)
- Reviews code for quality, security, and best practices
- Detects anti-patterns and SOLID violations
- Produces assessment review requiring user approval
- Uses Opus 4.6 with extended thinking for thorough analysis
- Does NOT make changes automatically
- User must explicitly approve before actions are taken

### active-defender (Security Testing - Opus 4.6 + Thinking)
- Offensive security testing with Active Defender mindset
- Probes for vulnerabilities and bypasses
- Uses Opus 4.6 with extended thinking for deep security analysis
- Provides vulnerability assessment and attack vector analysis

### code-implementer (Action Agent - Sonnet)
- Executes approved plans from code-planner
- Fast, cost-effective implementation
- Follows plans exactly without deviation
- Uses Sonnet 4.5 for efficient execution
- Writes production-quality code
- Tests and formats automatically

### test-writer (Action Agent - Sonnet)
- Generates comprehensive test suites
- Creates tests for edge cases and security scenarios
- Uses Sonnet 4.5 for fast test generation
- Can write test files directly

## Development Loop

All non-trivial changes follow the core loop defined in `WORKFLOW.md`:

```
Research  →  Plan  →  Annotate  →  Implement  →  Review
(planner)   (planner)  (human+     (implementer)  (reviewer,
                        planner)                    defender,
                                                    test-writer)
```

### Phases

| Phase | Agent | What Happens |
|-------|-------|--------------|
| 1. Research | code-planner | Deep-read code, map dependencies, surface unknowns |
| 2. Plan | code-planner | Design solution, produce implementation plan |
| 3. Annotate | human + code-planner | Human reviews plan, provides feedback (1-6 rounds) |
| 4. Implement | code-implementer | Execute approved plan step-by-step |
| 5. Review | code-reviewer + others | Verify implementation against plan |

### Example: Full Development Cycle

```bash
# Phase 1-2: Research and plan
/agents:code-planner Add user authentication to the API

# Phase 3: Review the plan, annotate with feedback
# (repeat until approved)

# Phase 4: Implement the approved plan
/agents:code-implementer [paste approved plan]

# Phase 5: Review
/agents:code-reviewer Review the authentication implementation
/agents:active-defender Test auth for bypass vulnerabilities
/agents:test-writer Add edge case tests for auth
```

### Quick Fix (Minimal Loop)

```bash
/agents:code-planner Fix the missing import in main.py
# Approve inline plan (1 round)
/agents:code-implementer [paste plan]
/agents:code-reviewer Quick review of the fix
```

### Security-Critical Workflow

```bash
/agents:code-planner Add CSRF protection
# Deep annotation cycle (2-3 rounds)
/agents:active-defender Test design for bypasses before approval
# Approve plan
/agents:code-implementer [paste plan]
/agents:active-defender Test implementation
/agents:code-reviewer Final review
```

## Agent Structure

Each agent directory contains:
```
agent-name/
├── agent.json          # Configuration (model, tools, capabilities)
└── system_prompt.md    # Behavioral instructions
```

## Model Strategy

| Role | Model | Thinking | Rationale |
|------|-------|----------|-----------|
| Planning | Opus 4.6 | Enabled | Deep reasoning for design |
| Review | Opus 4.6 | Enabled | Thorough code analysis |
| Security | Opus 4.6 | Enabled | Critical assessment |
| Implementation | Sonnet 4.5 | Disabled | Fast execution |
| Test Writing | Sonnet 4.5 | Disabled | Efficient generation |

**Principle**: Invest thinking where decisions are made (planning, review, security). Execute efficiently where decisions are already made (implementation, tests).

## Workspace Location

```
~/.claude/
├── CLAUDE.md              # Global standards
├── commands/
│   └── agents/            # Slash commands (invoke agents)
│       ├── code-planner.md
│       ├── code-implementer.md
│       ├── code-reviewer.md
│       ├── active-defender.md
│       └── test-writer.md
├── agents/                # This directory
│   ├── README.md          # This file
│   ├── code-planner/
│   ├── code-implementer/
│   ├── code-reviewer/
│   ├── active-defender/
│   └── test-writer/
├── skills/                # Future: Agent skills
└── hooks/                 # Future: Event hooks
```

## Project Integration

Each project can have its own `CLAUDE.md` that extends global standards:

```markdown
# Project: My App

## Project Overview
[Project-specific context]

## Additional Standards
[Extensions to global standards]

## Critical Files
[Important files in this project]
```

The project's `CLAUDE.md` will be loaded alongside the global `~/.claude/CLAUDE.md`.

## Creating New Agents

1. Create directory: `~/.claude/agents/my-agent/`
2. Add `agent.json` with configuration
3. Add `system_prompt.md` with instructions
4. Create slash command: `~/.claude/commands/agents/my-agent.md`
5. Update this README

### agent.json Template
```json
{
  "name": "agent-name",
  "description": "What this agent does",
  "model": "claude-sonnet-4-5",
  "extended_thinking": false,
  "capabilities": ["code_analysis"],
  "tools": ["Read", "Grep", "Glob"],
  "project_context": true,
  "max_iterations": 10
}
```

### system_prompt.md Template
```markdown
# Agent Role

You are [role description]...

## Capabilities
- Capability 1
- Capability 2

## Guidelines
- Guideline 1
- Guideline 2
```

## Best Practices

1. **Single Responsibility**: Each agent has one clear purpose
2. **Follow Standards**: All agents follow functional programming, immutability, explicit errors
3. **Tool Selection**: Grant only necessary tools
4. **Model Selection**: Opus + Thinking for analysis, Sonnet for action
5. **User Control**: Approval-based workflow for significant changes
