# Beads Integration

nuclode includes first-class support for [beads](https://github.com/steveyegge/beads) - a git-backed issue tracker designed for AI coding agents.

## Why Beads?

Beads solves the "50 First Dates" problem: agents wake up with no memory of previous sessions. Beads gives them persistent, structured memory that travels with your code in git.

## Setup

Beads is initialized per-project (not globally) to keep context focused:

```bash
# In any project directory
nuclode init
# This runs: bd init + copies project CLAUDE.md template
```

## Viewing Tasks

### For Humans
```bash
bv              # Interactive TUI (kanban, graph, insights)
bd list         # CLI list view
bd ready        # Show unblocked tasks
```

### For Agents
```bash
bv --robot-next       # Single best task recommendation
bv --robot-triage     # Full triage with priorities
bv --robot-insights   # Graph analysis
```

## Best Practices

- Keep active issues under 500 per project (run `bd cleanup` regularly)
- Use `bd doctor` daily for diagnostics
- Terminate agent sessions after completing tasks (beads preserves context)
- File granular issues (anything >2 minutes gets an issue)
