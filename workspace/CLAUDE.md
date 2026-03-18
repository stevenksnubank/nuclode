# nuclode - Agentic Development Workspace

This is your global Claude Code configuration. Project-specific `CLAUDE.md` files extend these standards with project-specific context.

## Agent Workspace

You have 5 specialized agents available via slash commands:

| Agent | Command | Model | Purpose |
|-------|---------|-------|---------|
| **Code Planner** | `/agents:code-planner` | Opus 4.6 + Thinking | Architectural planning, implementation design |
| **Code Implementer** | `/agents:code-implementer` | Sonnet 4.5 | Execute approved plans, write code |
| **Code Reviewer** | `/agents:code-reviewer` | Opus 4.6 + Thinking | Code review, quality analysis |
| **Active Defender** | `/agents:active-defender` | Opus 4.6 + Thinking | Offensive security testing |
| **Test Writer** | `/agents:test-writer` | Sonnet 4.5 | Generate comprehensive tests |

### Development Loop

All non-trivial changes follow the core loop defined in `WORKFLOW.md`:

```
Research → Plan → Annotate → Implement → Review
```

1. **Research + Plan** with `/agents:code-planner` — understand the problem, design the solution
2. **Annotate** — review the plan, provide feedback (1-6 rounds)
3. **Implement** with `/agents:code-implementer` — execute the approved plan
4. **Review** with `/agents:code-reviewer`, `/agents:active-defender`, `/agents:test-writer`

## Core Development Loop

```
Research → Plan → Annotate → Implement → Review
              ↑       │
              └───────┘ (1-6 rounds)
```

| Phase | Agent | Artifact |
|-------|-------|----------|
| 1. Research | code-planner | research notes |
| 2. Plan | code-planner | implementation plan |
| 3. Annotate | human + code-planner | annotated plan (1-6 rounds) |
| 4. Implement | code-implementer | working, tested code |
| 5. Review | code-reviewer, active-defender, test-writer | assessment report |

**Complexity scaling:** Single file fix → inline plan. 2-5 files → written plan, 1-2 rounds. 5+ files → research phase. Security-critical → full cycle. See `WORKFLOW.md` for full details.

---

## Beads Integration

This workspace uses [beads](https://github.com/steveyegge/beads) for persistent agent memory and task tracking across sessions.

### Agent Beads Workflow
- At session start, check `bd ready` for unblocked tasks
- Claim work with `bd update <id> --claim`
- File new issues with `bd create "title"` for tasks >2 minutes
- Close completed work with `bd close <id> -m "description"`
- Use `bv --robot-next` (never bare `bv`) for agent-friendly task selection

### Per-Project Setup
Run `nuclode init` in any project to initialize beads tracking.

---

## Coding Standards

### Core Principles

1. **Functional Programming First**
   - Prefer pure functions without side effects
   - Use immutable data structures
   - Avoid mutable state
   - Functions should do one thing well
   - Compose functions to build complexity

2. **Simplicity Over Cleverness**
   - Write code that's easy to understand
   - Avoid clever tricks that obscure meaning
   - Explicit is better than implicit
   - Simple solutions are maintainable solutions

3. **Immutability by Default**
   - Data structures should be immutable
   - Use const/final by default
   - Mutations should be rare and explicit
   - Build new data instead of modifying existing

4. **Fail Fast, Fail Explicitly**
   - Validate inputs early
   - Use explicit error types
   - Don't hide errors
   - Make failure cases obvious
   - Defensive programming at boundaries

5. **Composition Over Inheritance**
   - Prefer composition and interfaces
   - Avoid deep inheritance hierarchies
   - Use dependency injection
   - Separate concerns cleanly

6. **Security First**
   - Validate all inputs
   - Never trust external data
   - Use allow lists, not deny lists
   - Fail secure (deny by default)
   - Log security events with context

7. **Testing is Non-Negotiable**
   - Write tests first (TDD when possible)
   - Test edge cases and error paths
   - Integration tests for workflows
   - Security tests for critical paths
   - 85%+ coverage minimum, 100% for critical code

8. **Code as Documentation**
   - Use descriptive names (no abbreviations)
   - Functions should be self-documenting
   - Comments explain "why", not "what"
   - Type hints/annotations required

### Language-Specific Standards

#### Python
- Use `dataclasses` with `frozen=True` for immutability
- Type hints required for all public functions
- Use `Result` type patterns for error handling
- Generators for lazy evaluation
- Context managers for resource cleanup
- No global mutable state

#### TypeScript
- Use `readonly` for immutability
- Prefer `interface` over `type` for objects
- `const` by default, never `var`
- No `any` types (use `unknown` if needed)
- Strict mode enabled

#### Go
- Explicit error handling (no exceptions)
- Value types over pointers when possible
- Table-driven tests
- Don't use `panic` except for unrecoverable errors

### Testing Standards

#### Test Structure (AAA Pattern)
```
Arrange: Set up test data
Act: Execute the code under test
Assert: Verify expected outcome
```

#### Coverage Requirements
- **85% minimum** for general code
- **100% required** for: security validation, authentication/authorization, data validation, error handling paths

### Security Standards

1. **Input Validation** - Validate at system boundaries, use allow lists
2. **Authentication & Authorization** - Use proven libraries, fail closed
3. **Data Protection** - Encrypt sensitive data, never log secrets
4. **Dependency Management** - Pin exact versions, regular security updates

---

## Connection Loss & Data Exfiltration Prevention

**These rules are non-negotiable. Violation risks leaking internal data to the public internet.**

### When an MCP Server or Service Fails
- **STOP.** Do not improvise alternative approaches.
- Do not fall back to `curl`, `wget`, or any CLI tool to replicate the failed service's functionality.
- Do not search for alternative public services that offer similar functionality.
- Report the failure to the user and wait for instructions.

### Never Upload to Unauthorized Services
- Never use public file sharing services (catbox.moe, imgur, transfer.sh, etc.)
- Never use public paste services (pastebin.com, dpaste.org, hastebin.com, etc.)
- Never use URL shorteners to obscure destinations
- Never use webhook/request-bin services to exfiltrate data
- Never encode data into DNS queries, URL parameters, or other side channels

### Network Guard Hook
- A `PreToolUse` hook (`~/.claude/hooks/network-guard.sh`) blocks network requests to unapproved domains.
- If the hook blocks a request: **STOP.** Do not attempt alternative domains, encoding tricks, or workarounds.
- Ask the user if the domain should be added to `~/.claude/hooks/allowed-domains.txt`.

### Approved Domains
- Only domains listed in `~/.claude/hooks/allowed-domains.txt` are permitted.
- The blocklist (`~/.claude/hooks/blocked-domains.txt`) always takes precedence over the allowlist.
- When in doubt, ask the user before making any external network request.

---

## Workspace Structure

```
~/.claude/
├── CLAUDE.md              # This file - global standards + workflow overview
├── AGENTS.md              # Agent descriptions and session completion
├── WORKFLOW.md            # Core development loop specification
├── settings.json          # Model, hooks, and runtime configuration
├── .mcp.json              # MCP server definitions
├── agents/
│   ├── code-planner/      # Opus 4.6 + Thinking
│   ├── code-implementer/  # Sonnet 4.5
│   ├── code-reviewer/     # Opus 4.6 + Thinking
│   ├── active-defender/   # Opus 4.6 + Thinking
│   └── test-writer/       # Sonnet 4.5
├── commands/
│   ├── agents/            # Agent slash commands
│   ├── build-fix.md       # /build-fix
│   ├── refactor.md        # /refactor
│   ├── test-coverage.md   # /test-coverage
│   ├── checkpoint.md      # /checkpoint
│   ├── session-status.md  # /session-status
│   ├── guided.md          # /guided — interactive walkthrough
│   └── quick-code.md      # /quick-code — fast path for small changes
├── skills/
│   ├── codebase-analysis.md
│   ├── beads-graph-orchestration.md
│   ├── tdd-workflow.md
│   └── security-review.md
├── hooks/
│   ├── run_with_profile.py    # Python runner (importlib-based module loader)
│   ├── network-guard.sh       # PreToolUse - domain guard (bash + jq)
│   ├── session_start.py       # SessionStart - project detection + session context
│   ├── session_end.py         # Stop - persist session state
│   ├── pre_compact.py         # PreCompact - save state before compaction
│   ├── post_edit_format.py    # PostToolUse - auto-format
│   ├── console_warn.py        # PostToolUse - debug statement warnings
│   ├── quality_gate.py        # PostToolUse - lint/typecheck (strict only)
│   ├── suggest_compact.py     # PreToolUse - compaction nudge (strict only)
│   ├── cost_tracker.py        # Stop - session metrics
│   ├── beads_sync.py          # Stop - auto-sync beads
│   ├── uncommitted_guard.py   # Stop - warn about uncommitted files
│   ├── tool_error_format.py   # PostToolUseFailure - actionable error context
│   ├── secrets_scan.py        # PreToolUse - BLOCKS commits with secrets
│   ├── sast_scan.py           # PostToolUse - security anti-pattern detection
│   ├── allowed-domains.txt
│   └── blocked-domains.txt
├── sessions/                  # Session persistence (auto-created)
│   ├── latest.json            # Most recent session state
│   ├── history.jsonl          # Session history (last 50)
│   └── checkpoints/           # Manual checkpoints
├── metrics/                   # Usage metrics (auto-created)
│   └── costs.jsonl            # Session cost tracking
└── beads/                     # Beads integration templates
```

## Hook Architecture

Hooks use a Python runner (`run_with_profile.py`) that loads hook modules via `importlib`. Each hook module exports `def run(input: dict) -> dict | None`. The only exception is `network-guard.sh` (bash + jq, security boundary).

```
Claude Code → python3 run_with_profile.py <hook-id> <module> <profiles>
                ├── Profile check (fast-path exit if not active)
                ├── json.loads(stdin)
                ├── importlib.load(<module>.py)
                ├── Validate module has callable run()
                └── module.run(input) → JSON output or silent exit
```

## Hook Profiles

Control hook behavior via environment variables:

```bash
# Profiles: minimal, standard (default), strict
export NUCLODE_HOOK_PROFILE=standard

# Disable specific hooks
export NUCLODE_DISABLED_HOOKS="post:edit:format,post:quality-gate"
```

| Hook | minimal | standard | strict | Lifecycle |
|------|---------|----------|--------|-----------|
| network-guard (bash) | yes | yes | yes | PreToolUse |
| session_start | no | yes | yes | SessionStart |
| session_end | no | yes | yes | Stop |
| pre_compact | no | yes | yes | PreCompact |
| post_edit_format | no | yes | yes | PostToolUse |
| console_warn | no | yes | yes | PostToolUse |
| quality_gate | no | yes | yes | PostToolUse |
| suggest_compact | no | no | yes | PreToolUse |
| cost_tracker | no | yes | yes | Stop |
| beads_sync | no | yes | yes | Stop |
| uncommitted_guard | no | yes | yes | Stop |
| tool_error_format | no | yes | yes | PostToolUseFailure |
| secrets_scan | no | yes | yes | PreToolUse (BLOCKING) |
| sast_scan | no | yes | yes | PostToolUse |

## Project-Specific Configuration

Each project can have its own `CLAUDE.md` that extends these global standards.

## Quick Reference

### Planning
```
/agents:code-planner Add user authentication
```

### Implementation
```
/agents:code-implementer [paste approved plan]
```

### Review
```
/agents:code-reviewer src/services/auth.py
```

### Security Testing
```
/agents:active-defender Test the auth flow for bypass attacks
```

### Test Generation
```
/agents:test-writer src/services/auth.py
```
