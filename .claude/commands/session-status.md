---
description: Show current session state and recent session history
---

# Session Status

Display the current session state and recent session history from `~/.claude/sessions/`.

When invoked:

1. **Current session** - Show:
   - Working directory and git branch
   - Files modified in this session
   - Beads tasks claimed/completed
   - Approximate session duration

2. **Recent history** - Read `~/.claude/sessions/history.jsonl` and display last 5 sessions:
   - Timestamp, branch, summary
   - Whether the session was in the same project

3. **Checkpoints** - List any saved checkpoints from `~/.claude/sessions/checkpoints/`
