# Beads Graph Orchestration

## Overview

Graph-driven parallel task dispatch using beads_viewer's dependency resolution. This skill plans parallel execution tracks from the task DAG and dispatches agents per track with human confirmation.

**This skill is opt-in.** It is never auto-loaded. Invoke it explicitly when you want graph-aware parallel task orchestration.

## Prerequisites

- `bv` is installed (`command -v bv`)
- Project has beads data (`.beads/beads.jsonl` or `.beads/issues.jsonl`)
- Tasks exist with dependency relationships

## Flow

### 1. Generate Execution Plan

Run:
```bash
bv --robot-plan
```

This returns JSON with parallel execution tracks based on the task dependency graph.

### 2. Present Tracks Visually

Show the user the execution plan in a readable format:

```
Track 1 (parallel): Task #3 "Add auth middleware", Task #7 "Create DB schema"
Track 2 (parallel): Task #4 "Auth endpoints" (blocked by #3), Task #8 "Seed data" (blocked by #7)
Track 3 (sequential): Task #12 "Integration tests" (blocked by #4, #8)
```

### 3. Graph Embedding (3+ Dependency Nodes)

If the task DAG has 3 or more nodes with dependencies, include a Mermaid diagram:

```bash
bv --robot-graph --fmt mermaid
```

Embed the output inline in the plan. Skip the diagram for simple linear task lists (fewer than 3 dependency nodes).

### 4. Confirm Before Dispatch

Ask: **"Ready to dispatch these tracks?"**

Do NOT dispatch agents without explicit user confirmation. This is a plan-first, confirm-dispatch model.

### 5. Dispatch Parallel Agents Per Track

On confirmation, use the `dispatching-parallel-agents` pattern:
- One agent per independent task in the current track
- Each agent gets focused scope (one task)
- Agents work concurrently within a track
- Tracks execute sequentially (track 2 waits for track 1)

### 6. Revalidate After Each Track

After each track completes:
```bash
bv --robot-next
```

Revalidate the graph - dependencies may have changed. Present updated state before dispatching next track.

## When to Use

- You have 3+ tasks with dependency relationships
- Tasks can be parallelized (independent within a track)
- You want graph-aware execution ordering
- Complex multi-step implementations

## When NOT to Use

- Simple linear task lists (just execute sequentially)
- Single task with no dependencies
- Tasks that share state or edit the same files
- Exploratory/research work where the task graph is unclear

## Important

- **Never auto-load** this skill. Wait for explicit invocation.
- **Always confirm** before dispatching agents.
- **Revalidate** the graph between tracks.
- **Respect dependencies** - never skip blocked tasks.
