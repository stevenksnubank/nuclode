---
description: Save a named checkpoint of the current session state
---

# Checkpoint

Save a manual checkpoint of the current session. Use this before risky operations, at natural milestones, or when you want to mark a resumption point.

When invoked:

1. **Gather context** - Collect:
   - Current working directory and git branch
   - Modified files (git status)
   - Beads status (if active)
   - Brief summary of what was accomplished

2. **Save checkpoint** - Write to `~/.claude/sessions/checkpoints/`:
   ```json
   {
     "name": "<user-provided or auto-generated>",
     "timestamp": "2026-03-18T14:30:00Z",
     "cwd": "/path/to/project",
     "branch": "feature-branch",
     "modified_files": ["file1.py", "file2.ts"],
     "beads_ready": 3,
     "summary": "Completed auth middleware, tests passing"
   }
   ```

3. **Confirm** - Report the checkpoint name and what was saved

## Usage
```
/checkpoint                     # Auto-named checkpoint
/checkpoint pre-refactor        # Named checkpoint
```
