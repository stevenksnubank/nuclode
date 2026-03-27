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

## Human-in-the-Loop Checkpoints

Every architecturally significant moment has a named checkpoint. The human is the explicit decision-maker at each one. Agents record decisions in `decisions.md` — an append-only ledger that lets sessions resume reliably.

| # | Checkpoint | Fires when | What the human decides |
|---|---|---|---|
| **CP-0** | Intent confirmation | Intent bead written, before any file reads | Is this the right scope? Files to add/remove? |
| **CP-1** | Plan approval | `plan-handoff.json` written, plan presented | Does this implementation plan match what I want? |
| **CP-2** | Review verdict | QR → SK → RC panel complete, `review-final.md` ready | Approve / reject with notes / flag specific issues |
| **CP-SEC** | Security approval | active-defender assessment complete (optional) | Are identified risks acceptable? Which must be fixed first? |

### decisions.md — The Decision Ledger

`decisions.md` lives in the working directory. Agents append to it at each checkpoint; they read it on session start to reconstruct where a task stands.

**Format:**
```markdown
## CP-0 — Intent: <one-line scope> — <ISO timestamp>
**Decision:** APPROVED | APPROVED_WITH_NOTES | REJECTED
**Notes:** <what the human said>

## CP-1 — Plan: <one-line plan summary> — <ISO timestamp>
**Decision:** APPROVED | APPROVED_WITH_NOTES | REJECTED
**Mode:** full_replay | quick_fix   ← only on REJECTED
**Rejection notes:**
- <specific issue>
**Round:** <N>
```

**Session resume:** On session start, read `decisions.md`, find the last checkpoint block, check its `Decision:` field:
- `APPROVED` / `APPROVED_WITH_NOTES` → proceed from next step
- `REJECTED` with no follow-up block → re-run the producing agent
- Session Notes block present → apply refinements before continuing

**Rollback protocol:**

| Checkpoint rejected | Files to delete | Resume from |
|---|---|---|
| CP-0 (intent) | Rewrite CP-0 block in decisions.md | Re-write intent bead, re-present CP-0 |
| CP-1 (plan), `full_replay` | `plan-handoff.json`, `plan.md` | code-planner re-runs from Step 2 (keeps intent bead) |
| CP-1 (plan), `quick_fix` | `plan-handoff.json` only | code-planner re-runs plan writing step only |
| CP-2 (review), `full_replay` | `review-qr.md`, `review-sk.md`, `review-final.md` | code-reviewer (QR) re-runs from scratch |
| CP-2 (review), `quick_fix` | `review-final.md` only | code-implementer applies fixes, RC re-evaluates |
| CP-SEC | `security-assessment.md` | active-defender re-runs with rejection notes as context |

**Never delete:** `decisions.md`, intent bead (in beads db), or an approved `plan-handoff.json`.

---

## Phases

### Phase 1: Research
**Owner:** code-planner
**Artifact:** `research.md` (in working directory or plan thread)

Before designing anything, follow this order:

**1. Write intent bead** (before any file reads)

Capture the user's request and scope constraints as an intent bead — see `AGENT_INSTRUCTIONS.md` for the template. This is the highest-priority context for every agent in the chain.

**2. Query existing beads** (before reading source files)

```bash
bd query --filter "label:decision" --json 2>/dev/null | head -c 1500
bd query --filter "label:structure" --json 2>/dev/null | head -c 1000
bd query --filter "label:review" --json 2>/dev/null | head -c 800
```

If beads exist for the files/namespaces in scope, read them first. They capture decisions and findings from past sessions — skip re-reading what's already known.

**3. Deep-read source files** (conditional on step 2)

Only read files not already covered by a fresh structure bead:
- Read function bodies, not just signatures
- Map existing patterns, conventions, and dependencies
- Identify blast radius — what else touches this code?
- Surface unknowns and open questions
- After reading 3+ files in a module, write a structure bead

**4. Structure analysis** (optional — Clojure codebases only)

For Clojure projects with no existing structure beads:
```bash
nuclode analyze /path/to/project --mode structure
```
Skip if: fresh structure beads already exist, project is not Clojure, or task is scoped to a well-understood subset.

### Phase 2: Plan
**Owner:** code-planner
**Artifacts:** `plan.md` (prose, for human reading) + `plan-handoff.json` (structured, for implementer gate)

Produce a concrete implementation plan:
- Architecture decisions with rationale
- File-level change list (create / modify / delete)
- Data structures and interfaces
- Error handling strategy
- Security considerations
- Testing strategy

**The plan is a contract.** Implementation follows it exactly. `plan-handoff.json` is the machine-readable form of that contract — see `.claude/schemas/plan-handoff.schema.json` for the schema. The file is written with `"approved": false`; the human sets it to `true` at CP-1.

### Phase 3: Annotate (CP-1 — Plan Approval)
**Owner:** human (with code-planner support)
**Artifact:** annotated plan + `decisions.md` CP-1 block

The human reviews the plan and marks it up:
- Approve sections as-is
- Request changes with specific notes
- Flag concerns or missing considerations
- Ask questions the planner should address

**Cycle:** The planner processes annotations and produces a revised plan. This repeats 1–6 times until the human approves. Short tasks may need one pass; complex features may need several.

**Complexity scaling:** If the knowledge graph shows high namespace spread (>5 namespaces) or many dependency edges, the planner should proactively suggest deeper research or additional annotation rounds.

**Escalation:** If the plan is rejected 3+ times, the planner appends `⚠ ESCALATED` to `decisions.md` and stops. The human must revise scope or add context before continuing.

**On approval:** code-planner writes `plan-handoff.json`, sets `"approved": false`, and appends CP-1 APPROVED block to `decisions.md`. Human (or code-planner on explicit instruction) sets `"approved": true` in the JSON.

### Phase 4: Implement
**Owner:** code-implementer
**Artifact:** working, tested code

Execute the approved plan:
- Follow the plan exactly — no architectural freelancing
- Mark tasks complete in `plan-handoff.json` `changes[]` as you go
- Run tests after each step
- Run all commands in `verification.commands` before marking done
- Stop and escalate if the plan doesn't match reality

**Gate:** Implementation cannot start without an approved plan. If `plan-handoff.json` is present and `"approved": false`, the implementer stops immediately and redirects to CP-1. If no `plan-handoff.json` exists, the implementer requires a verbal approval signal from the user.

### Phase 5: Review (CP-2 — Review Verdict)
**Owner:** code-reviewer (QR), code-skeptic (SK), code-reconciler (RC), active-defender, test-writer
**Artifacts:** `review-qr.md`, `review-sk.md`, `review-final.md`

The review panel uses adversarial separation to catch what a single reviewer misses:

```
implementation complete
  ↓
→ code-reviewer [QR] → writes review-qr.md
  (completeness vs plan, code quality, pattern adherence)
  ↓
→ code-skeptic [SK] — reads review-qr.md → writes review-sk.md
  (challenges QR's APPROVED conclusions specifically — not re-running QR's checks)
  ↓
→ code-reconciler [RC] — reads both → writes review-final.md
  (verdict table: ACCEPTED / OVERRULED / DEFERRED per disputed item)
  ↓
Human sees review-final.md at CP-2
```

**Panel rules:**
- SK reads QR's output, not the raw code — its value is challenging approved conclusions, not duplicating QR's completeness check
- RC never invents findings — it only resolves conflicts between QR and SK
- RC is short: a verdict table, not paragraphs
- If SK raises 3+ upheld issues, RC escalates to human rather than flagging all as blockers

**Escalation:** If CP-2 is rejected 2+ times, append `⚠ ESCALATED` to `decisions.md` and stop. The panel does not run a third cycle — it surfaces the unresolved conflict with all review history.

**Also available (parallel to QR/SK/RC):**
- **active-defender**: security testing, vulnerability probing → triggers CP-SEC if scope warrants it
- **test-writer**: coverage gaps, edge cases, missing security test scenarios

If review finds **architectural issues**, recommend returning to Phase 3 (annotate). If review finds **implementation issues**, recommend direct fixes in Phase 4.

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
| research.md | working dir | session |
| plan.md | working dir | session |
| plan-handoff.json | working dir | permanent (gate for implementer) |
| decisions.md | working dir | permanent (append-only ledger) |
| annotations | inline in conversation | session |
| code changes | git working tree | permanent |
| review-qr.md | working dir | session |
| review-sk.md | working dir | session |
| review-final.md | working dir | session |

For plans that span multiple sessions, save `plan.md` and `plan-handoff.json` to the working directory. `decisions.md` always stays — it is the session resume anchor.

## Agent-to-Phase Mapping

| Agent | Primary Phase | Secondary | Review role |
|-------|--------------|-----------|-------------|
| **code-planner** | 1 (Research), 2 (Plan) | 3 (Annotate — processes feedback) | — |
| **code-implementer** | 4 (Implement) | — | — |
| **code-reviewer** | 5 (Review) | 3 (Annotate — architectural feedback) | QR — completeness + quality |
| **code-skeptic** | 5 (Review) | — | SK — adversarial challenge of QR |
| **code-reconciler** | 5 (Review) | — | RC — verdict table, dispute resolution |
| **active-defender** | 5 (Review / CP-SEC) | — | Security probe |
| **test-writer** | 5 (Review) | — | Coverage gaps |

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
