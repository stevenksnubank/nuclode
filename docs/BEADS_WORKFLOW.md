# Beads Workflow

## Overview

[Beads](https://github.com/steveyegge/beads) is a git-backed issue tracker designed for AI coding agents. It solves the "50 First Dates" problem: agents wake up with no memory of previous sessions.

## Per-Project Setup

Beads is initialized per-project (not globally):

```bash
cd my-project
nuclode init
# Creates .beads/ directory and project CLAUDE.md
```

## Agent Session Lifecycle

### Session Start
```bash
bd ready              # Check for unblocked tasks
bd show <id>          # Read task details
bd update <id> --claim  # Claim work
```

### During Work
```bash
bd create "Bug: login fails with special chars" -p P1  # File issues
bd update <id> --status in_progress                      # Track progress
bd comment <id> "Decided to use JWT because..."          # Document decisions
bd create "Sub: Add rate limiting" --parent <id>         # Sub-tasks
```

### Session End
```bash
bd close <id> -m "Implemented JWT auth with refresh"  # Close completed
bd update <id> -m "Context: waiting on API key"        # Update in-progress
bd sync                                                 # Persist to git
git push                                                # Push to remote
```

## Beads Viewer (bv)

### For Humans
```bash
bv              # Interactive TUI - kanban board, graph view, insights
```

### For Agents (Robot Mode)
```bash
bv --robot-next       # Single best task to work on
bv --robot-triage     # Full triage with priority recommendations
bv --robot-insights   # Graph metrics, bottleneck analysis
bv --robot-plan       # Parallel execution tracks
bv --robot-graph      # Dependency graph export
```

**IMPORTANT**: Agents must NEVER run bare `bv` - it launches an interactive TUI that blocks execution. Always use `--robot-*` flags.

## Priority Levels

| Priority | Meaning | Agent Behavior |
|----------|---------|----------------|
| P0 | Critical - blocking | Work on immediately |
| P1 | High - important | Work on soon |
| P2 | Medium - normal | Standard priority |
| P3 | Low - nice to have | Work on when free |

## Best Practices

1. **File granular issues** - Anything taking >2 minutes gets its own issue
2. **Keep active issues under 500** - Run `bd cleanup` regularly
3. **Use `bd doctor` daily** - Diagnostics catch sync issues early
4. **Always `bd sync` before ending** - Don't leave work unsynced
5. **Document decisions in comments** - Future sessions need context
6. **Close completed work promptly** - Don't let done items pile up
