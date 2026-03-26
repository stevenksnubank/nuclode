#!/bin/bash
# agent-watch-pre.sh — PreToolUse hook for the Agent tool
#
# Writes a state file to ~/.claude/sessions/agents/ so nuclode-watch
# can display background agents as they are launched.
#
# Requires: jq

set -uo pipefail

AGENTS_DIR="$HOME/.claude/sessions/agents"
mkdir -p "$AGENTS_DIR"

INPUT="$(cat)"

TOOL_NAME="$(echo "$INPUT" | jq -r '.tool_name // empty')"
[ "$TOOL_NAME" != "Agent" ] && exit 0

DESCRIPTION="$(echo "$INPUT" | jq -r '.tool_input.description // empty')"
SUBAGENT_TYPE="$(echo "$INPUT" | jq -r '.tool_input.subagent_type // empty')"

[ -z "$DESCRIPTION" ] && exit 0

# Generate a stable key from the description (slug, lowercase, max 48 chars)
KEY="$(echo "$DESCRIPTION" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-' | sed 's/^-//;s/-$//' | cut -c1-48)"
[ -z "$KEY" ] && KEY="agent-$$"

# Derive phase from subagent_type
case "$SUBAGENT_TYPE" in
    *code-planner*|*plan*)        PHASE="planning" ;;
    *code-implementer*|*implement*) PHASE="implementing" ;;
    *code-reviewer*|*review*)     PHASE="reviewing" ;;
    *active-defender*|*security*) PHASE="security review" ;;
    *test-writer*|*test*)         PHASE="writing tests" ;;
    *research*)                   PHASE="researching" ;;
    *)                            PHASE="routing" ;;
esac

START_TIME="$(date +%s)"

# Write state file
jq -n \
  --arg key "$KEY" \
  --arg name "$DESCRIPTION" \
  --arg phase "$PHASE" \
  --argjson start_time "$START_TIME" \
  '{key: $key, name: $name, phase: $phase, status: "active", start_time: $start_time}' \
  > "$AGENTS_DIR/$KEY.json"

# Write activity file
jq -n \
  --arg summary "$SUBAGENT_TYPE" \
  '{tool: "Agent", summary: $summary}' \
  > "$AGENTS_DIR/$KEY-activity.json"

exit 0
