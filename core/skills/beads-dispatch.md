# Beads-Driven Agent Dispatch

Graph-driven parallel agent dispatch using the beads dependency graph. Reads the graph, identifies unblocked work, and dispatches agents in waves with user confirmation between each wave.

## When to Use

- You have a beads graph with tasks that can be parallelized
- You want agents dispatched based on bead labels
- You need wave-based execution (parallel within wave, sequential between waves)

## Prerequisites

- `bd` and `bv` are installed (`command -v bd && command -v bv`)
- Beads exist for the project (`bv --repo <project> --robot-plan`)

## Dispatch Flow

### 1. Read the Execution Plan

```bash
bv --repo <project> --robot-plan
```

Returns tracks showing what's unblocked vs blocked:

```
Track 1 (unblocked): bead-abc "Add auth middleware", bead-def "Add user model"
Track 2 (blocked):   bead-ghi "Wire auth to routes" ← waits for abc+def
Track 3 (blocked):   bead-jkl "Review" ← waits for all implementation
```

### 2. Map Labels to Agents

| Bead Label | Agent to Dispatch |
|------------|-------------------|
| `design` | `/agents:code-planner` |
| `implementation` | `/agents:code-implementer` |
| `review` | `/agents:code-reviewer` |
| `security` | `/agents:active-defender` |
| `test` | `/agents:test-writer` |

### 3. Present Wave to User

```
Wave 1 (parallel):
  - [implementer] bead-abc "Add auth middleware"
  - [implementer] bead-def "Add user model"

Ready to dispatch these agents?
```

**Always get user confirmation before dispatching.**

### 4. Dispatch Agents in Parallel

Use the Task tool to dispatch agents concurrently. Each agent receives:
- The bead ID and description
- The repo scope
- Instructions to mark the bead in-progress then closed when done

```
Task(subagent_type: "general-purpose", prompt: "You are code-implementer. Bead: bead-abc. Repo: <project>. Run: bd update bead-abc --status in_progress. Implement the task. Then: bd update bead-abc --status closed.")
```

### 5. After Wave Completes

```bash
bv --repo <project> --robot-plan
```

Check what's now unblocked. Present the next wave to the user.

### 6. Repeat Until Graph Complete

Continue dispatching waves until all beads are closed.

## Wave Execution Pattern

```
Wave 1: [implementer: bead-abc] [implementer: bead-def]  ← parallel
Wave 2: [implementer: bead-ghi]                           ← unblocked after wave 1
Wave 3: [reviewer: bead-jkl] [defender: bead-mno]         ← parallel review + security
Wave 4: [implementer: bead-pqr]                           ← fixes from review/security
```

## Important Rules

- **Always confirm** before dispatching each wave
- **Revalidate** the graph after each wave (`bv --repo <project> --robot-plan`)
- **Never skip** blocked beads
- Each agent receives: bead ID, description, repo scope, and status update instructions

## Relationship to beads-graph-orchestration

This skill extends `beads-graph-orchestration` with agent-aware dispatch. The older skill dispatches generic tasks; this skill maps bead labels to the correct agent type.
