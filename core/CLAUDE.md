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

### Workflow
1. **Plan** with `/agents:code-planner` (Opus + Thinking)
2. **Review plan** and approve
3. **Implement** with `/agents:code-implementer` (Sonnet)
4. **Review code** with `/agents:code-reviewer` (Opus + Thinking)
5. **Security test** with `/agents:active-defender` (Opus + Thinking)
6. **Generate tests** with `/agents:test-writer` (Sonnet)

---

## Collaborative Thinking Standard

**All thinking agents (code-planner, code-reviewer, active-defender) MUST follow the Collaborative Thinking Protocol before producing output.** This ensures the user and AI are aligned before any code is written or decisions are made.

### The Protocol

1. **Brainstorm First** - Understand the problem through dialogue. Ask questions one at a time. Prefer multiple choice. Surface your understanding and verify it matches the user's intent.
2. **Explore Approaches Together** - Propose 2-3 options with trade-offs. Lead with your recommendation. Use sequential thinking (`mcp__sequential-thinking__sequentialthinking`) for complex reasoning so the user can see your thought process.
3. **Validate Incrementally** - Present designs/findings/assessments in small sections (200-300 words). Check after each section. Be ready to revise.
4. **YAGNI Ruthlessly** - Remove unnecessary features and over-engineering from all designs.

### Why This Matters

- No surprises in plans, reviews, or security assessments
- User context and business knowledge shapes every decision
- Sequential thinking makes reasoning transparent and reviewable
- Conformity across all thinking agents - same collaborative process every time

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
├── CLAUDE.md              # This file - global standards
├── commands/
│   └── agents/            # Agent slash commands
├── agents/                # Agent configurations
├── hooks/
│   ├── network-guard.sh   # PreToolUse hook - blocks unapproved domains
│   ├── allowed-domains.txt # Approved domains for network access
│   └── blocked-domains.txt # Always-blocked domains (exfiltration targets)
└── settings.json          # Claude Code settings
```

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
