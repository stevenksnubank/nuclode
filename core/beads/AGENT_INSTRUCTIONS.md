# Beads Agent Instructions

This project uses **bd** (beads) for issue tracking and persistent agent memory.

## Session Start Checklist

1. Run `bd ready` to see unblocked tasks
2. If tasks exist, claim one with `bd update <id> --claim`
3. If no tasks, proceed with user's request

## During Work

- File issues for anything taking >2 minutes: `bd create "Title" -p <priority>`
- Update task progress: `bd update <id> --status in_progress`
- Add sub-issues for discovered work: `bd create "Sub-task" --parent <parent-id>`
- Add comments to track decisions: `bd comment <id> "Decision made because..."`

## Session End Checklist

1. Close completed tasks: `bd close <id> -m "Summary of what was done"`
2. Update in-progress tasks with context for next session
3. File issues for remaining work
4. Run `bd sync` to persist to git

## Beads Viewer (for agents)

IMPORTANT: Never run bare `bv` - it launches an interactive TUI that blocks execution.

Use robot mode flags:
- `bv --robot-next` - Get the single best task to work on next
- `bv --robot-triage` - Comprehensive triage with recommendations
- `bv --robot-insights` - Graph metrics and bottleneck analysis
- `bv --robot-plan` - Parallel execution tracks
- `bv --robot-graph` - Dependency graph export

## Priority Levels

- **P0**: Critical - blocking other work or urgent
- **P1**: High - important, do soon
- **P2**: Medium - normal priority
- **P3**: Low - nice to have
