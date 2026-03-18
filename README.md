# nuclode

Secure vibe coding with Claude Code. Describe what you want to build — nuclode handles the security, quality, and workflow automatically.

```
You: "Add a password reset flow"

nuclode: designs the solution → implements it → catches security issues →
         explains what it found → fixes with your approval → runs tests

You: ship it.
```

## What it does

nuclode sits between you and Claude Code as a security and quality layer. You talk naturally. It enforces the guardrails.

**Deterministic security hooks** run on every edit and commit — no LLM decides whether to check:

| Guard | What it catches | Enforcement |
|-------|----------------|-------------|
| Secrets scan | API keys, tokens, passwords in code | **Blocks commit** |
| Security scan | SQL injection, eval(), XSS, shell injection, path traversal, SSRF, insecure crypto | **Blocks commit** (HIGH) / warns (MEDIUM) |
| Network guard | Data exfiltration to unauthorized domains | **Blocks request** |
| Quality gate | Lint errors (ruff, tsc, go vet) | Warns on edit |
| Debug detection | console.log, breakpoint(), print() left in code | Warns on edit |
| Auto-format | Code style (ruff, prettier, gofmt, cljfmt) | Silent auto-fix |

76 security patterns across Python, JavaScript/TypeScript, Go, Ruby, and Clojure. All regex-based, all deterministic.

**Guided workflow** routes your request to the right approach:
- Quick fixes (1-2 files) → implemented directly
- Features (3+ files) → planned first, then implemented
- Security-sensitive changes → automatic security review

**Educational, not punitive.** When a guard catches something, the guide explains what was found, why it matters, proposes a fix, and applies it with your agreement. You learn the pattern.

## Install

```bash
git clone https://github.com/stevenksnubank/nuclode.git ~/dev/nuclode
cd ~/dev/nuclode && ./nuclode install
```

Then:
```bash
cd your-project
claude
# Just describe what you want to build
```

## How it works

```
User describes what they want
    ↓
nuclode-guide (Sonnet) — triages, routes, orchestrates
    ↓
Code gets written/edited
    ↓
DETERMINISTIC HOOKS FIRE (Python, no LLM):
├── sast_patterns.py  — 76 regex patterns (fast, ~50ms)
├── secrets_scan.py   — credential patterns (on commit)
├── sast_gate.py      — blocks HIGH severity (on commit)
├── network_guard.sh  — domain allowlist (on every request)
├── quality_gate.py   — linters (on edit)
└── post_edit_format.py — formatters (on edit)
    ↓
Findings go to guide as context
    ↓
Guide explains → proposes fix → gets agreement → shows what changed
    ↓
User learns. Code ships safely.
```

The LLM explains. The hooks decide. The user approves.

## Agents

Six agents, dispatched automatically by the guide:

| Agent | Model | When |
|-------|-------|------|
| **nuclode-guide** | Sonnet | Always — triages every request |
| **code-planner** | Opus + Thinking | Features needing design |
| **code-implementer** | Sonnet | Executing approved plans |
| **code-reviewer** | Opus + Thinking | Quality review |
| **active-defender** | Opus + Thinking | Security-sensitive code |
| **test-writer** | Sonnet | Test generation |

Models use family aliases (`"opus"`, `"sonnet"`) — auto-upgrade when new versions ship.

## Security coverage

Currently **~50%** of common vibe coding dangers are deterministically caught:

**Blocked at commit:** SQL injection, eval(), shell injection, XSS, hardcoded secrets, insecure crypto (MD5/SHA1/ECB), pickle deserialization, path traversal patterns, logging sensitive data

**Warned on edit:** SSRF indicators, open redirects, unsafe yaml, debug statements, hardcoded internal IPs, lint issues

**Not yet covered:** Missing auth checks, insecure dependencies (CVEs), test coverage enforcement, CSRF, business logic flaws. See `docs/plans/` for the roadmap to 80%.

## Beads

Persistent task and knowledge tracking across sessions.

```bash
nuclode init              # initialize beads in a project
```

The guide auto-injects claimed task context at session start and tracks task IDs across sessions. You don't need to manage beads manually.

## Project structure

```
nuclode/
├── workspace/              # → installs to ~/.claude/
│   ├── agents/             #   6 agents (guide, planner, implementer, reviewer, defender, test-writer)
│   │   └── includes/       #   shared prompt sections
│   ├── commands/           #   slash commands (/guided, /quick-code, /build-fix, etc.)
│   ├── skills/             #   coding-standards, tdd-workflow, security-review, codebase-analysis
│   ├── hooks/              #   17 hooks (3 blocking, 5 visible, 9 silent)
│   │   ├── sast_patterns.py    # 76 security patterns
│   │   ├── secrets_scan.py     # credential detection
│   │   ├── sast_gate.py        # commit-time security gate
│   │   ├── network-guard.sh    # domain allowlist
│   │   └── run_with_profile.py # hook runner with profile controls
│   ├── CLAUDE.md           #   60 lines — "just describe what you want"
│   └── settings.json       #   hook registrations + status line
│
├── knowledge/              # deterministic context engine
├── scripts/                # standards sync verification
├── tests/                  # 49 tests
└── nuclode                 # CLI
```

## For power users

Direct agent access (bypass the guide):
```bash
/agents:code-planner      # Opus + Thinking for architecture
/agents:code-implementer  # Sonnet for execution
/agents:active-defender   # Opus + Thinking for security
```

Hook profiles:
```bash
export NUCLODE_HOOK_PROFILE=minimal    # network guard only
export NUCLODE_HOOK_PROFILE=standard   # default — all guards
export NUCLODE_HOOK_PROFILE=strict     # + compaction suggestions
```

Disable specific hooks:
```bash
export NUCLODE_DISABLED_HOOKS="post:sast-scan,post:console-warn"
```

## CLI

```bash
nuclode install       # first-time setup
nuclode update        # pull latest and re-install
nuclode analyze       # codebase analysis
nuclode init          # initialize beads in a project
nuclode help          # all options
```
