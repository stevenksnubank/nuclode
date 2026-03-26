# Core Development Loop

Every non-trivial change follows this loop. The loop is the default — agents enforce it automatically.

```
Research  →  Plan  →  Annotate  →  Implement  →  Review
   ↑            ↑         │             │           │
   │            └─────────┘             │           │
   │          (repeat 1-6x)            │           │
   └───────────────────────────────────┴───────────┘
                    (rework if needed)
```

## Phases

### Phase 1: Research
**Owner:** code-planner
**Artifact:** `research.md` (in working directory or plan thread)

Before designing anything, understand the problem space:
- Deep-read relevant source files (not just signatures — read bodies)
- Map existing patterns, conventions, and dependencies
- Identify blast radius — what else touches this code?
- Surface unknowns and open questions

For complex or unfamiliar codebases, use the knowledge engine:
```bash
nuclode analyze /path/to/project --mode structure
```

### Phase 2: Plan
**Owner:** code-planner
**Artifact:** `plan.md` or inline plan in conversation

Produce a concrete implementation plan:
- Architecture decisions with rationale
- File-level change list (create / modify / delete)
- Data structures and interfaces
- Error handling strategy
- Security considerations
- Testing strategy

**The plan is a contract.** Implementation follows it exactly.

### Phase 3: Annotate
**Owner:** human (with code-planner support)
**Artifact:** annotated plan (inline diff or comments)

The human reviews the plan and marks it up:
- Approve sections as-is
- Request changes with specific notes
- Flag concerns or missing considerations
- Ask questions the planner should address

**Cycle:** The planner processes annotations and produces a revised plan. This repeats 1–6 times until the human approves. Short tasks may need one pass; complex features may need several.

**Complexity scaling:** If the knowledge graph shows high namespace spread (>5 namespaces) or many dependency edges, the planner should proactively suggest deeper research or additional annotation rounds.

### Phase 4: Implement
**Owner:** code-implementer
**Artifact:** working, tested code

Execute the approved plan:
- Follow the plan exactly — no architectural freelancing
- Mark tasks complete as you go
- Run tests after each step
- Stop and escalate if the plan doesn't match reality

**Gate:** Implementation cannot start without an approved plan. The implementer will refuse and redirect to code-planner if no plan exists.

### Phase 5: Review
**Owner:** code-reviewer, active-defender, test-writer
**Artifact:** assessment report

Verify the implementation:
- **code-reviewer**: completeness vs plan, code quality, pattern adherence
- **active-defender**: security testing, vulnerability probing
- **test-writer**: coverage gaps, edge cases, security test scenarios

If review finds **architectural issues**, recommend returning to Phase 3 (annotate) for another cycle. If review finds **implementation issues**, recommend direct fixes in Phase 4.

## Complexity Scaling

Not every change needs the full ceremony. The planner evaluates complexity and recommends process depth:

| Signal | Depth |
|--------|-------|
| Single file, clear fix | Plan inline, minimal annotation |
| 2-5 files, known patterns | Written plan, 1 annotation round |
| 5+ files or new patterns | Research phase, 2-3 annotation rounds |
| Cross-cutting or security-critical | Deep research, full annotation cycle, security review |

The planner uses these signals to suggest depth:
- **Bead count** — more linked tasks = more coordination needed
- **Namespace spread** — changes spanning many namespaces need more research
- **Dependency graph density** — high-centrality nodes need extra care
- **Security surface** — auth, data validation, or external APIs trigger full review

## Artifacts

All artifacts live in the conversation thread or working directory. No special directories required.

| Artifact | Location | Persistence |
|----------|----------|-------------|
| research.md | conversation or working dir | session |
| plan.md | conversation or working dir | session |
| annotations | inline in conversation | session |
| code changes | git working tree | permanent |
| review report | conversation | session |

For plans that span multiple sessions, save `plan.md` to the working directory so it persists.

## Agent-to-Phase Mapping

| Agent | Primary Phase | Secondary |
|-------|--------------|-----------|
| **code-planner** | 1 (Research), 2 (Plan) | 3 (Annotate — processes feedback) |
| **code-implementer** | 4 (Implement) | — |
| **code-reviewer** | 5 (Review) | 3 (Annotate — architectural feedback) |
| **active-defender** | 5 (Review) | — |
| **test-writer** | 5 (Review) | — |

## Quick Reference

```bash
# Full loop
/agents:code-planner Add rate limiting to the API    # → research + plan
# Review and annotate the plan                        # → 1-6 rounds
/agents:code-implementer [approved plan]              # → implement
/agents:code-reviewer Review the rate limiting code   # → review
/agents:active-defender Test rate limiting for bypass  # → security review
/agents:test-writer Add edge case tests               # → test coverage

# Quick fix (minimal loop)
/agents:code-planner Fix the null check in parser.py  # → inline plan
# Approve                                             # → 1 round
/agents:code-implementer [approved plan]              # → implement
```
