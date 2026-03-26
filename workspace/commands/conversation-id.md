---
description: Find the session ID for the current Claude Code conversation
---

# Conversation ID

Find the session ID for the current Claude Code conversation.

## How it works

1. Derive the project directory name from `$PWD` by replacing `/` and `.` with `-`
2. Look under `~/.claude/projects/{derived-dir}/` for `.jsonl` log files
3. Find the most recently modified `.jsonl` file (the active conversation)
4. Report the session ID (the filename without `.jsonl`)

## Steps

Run this bash pipeline to find the conversation ID:

```bash
# Derive the project directory
PROJ_DIR="$HOME/.claude/projects/$(echo "$PWD" | tr '/.' '-')"

# Find the most recently modified .jsonl file
LATEST=$(ls -t "$PROJ_DIR"/*.jsonl 2>/dev/null | head -1)

if [ -z "$LATEST" ]; then
  echo "No conversation logs found in $PROJ_DIR"
  exit 1
fi

# Extract session ID from filename
SESSION_ID=$(basename "$LATEST" .jsonl)
echo "$SESSION_ID"
```

If multiple conversations are active in the same project, verify by grepping for a known unique string from this session (e.g., a recent commit hash or the last user message).

## Output

The session ID (a UUID), e.g.:
```
e43df49e-196c-4ac5-b9ae-0065fe7e0412
```

The full log file path is:
```
~/.claude/projects/{derived-dir}/{session-id}.jsonl
```
