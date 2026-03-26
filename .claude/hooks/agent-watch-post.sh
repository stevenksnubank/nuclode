#!/bin/bash
# agent-watch-post.sh — PostToolUse hook for the Agent tool
#
# Marks an agent as stopped in ~/.claude/sessions/agents/ when the
# Agent tool completes, so nuclode-watch can fade it out cleanly.
#
# Requires: jq

set -uo pipefail

AGENTS_DIR="$HOME/.claude/sessions/agents"

INPUT="$(cat)"

TOOL_NAME="$(echo "$INPUT" | jq -r '.tool_name // empty')"
[ "$TOOL_NAME" != "Agent" ] && exit 0

DESCRIPTION="$(echo "$INPUT" | jq -r '.tool_input.description // empty')"
[ -z "$DESCRIPTION" ] && exit 0

# Derive same key used in pre hook
KEY="$(echo "$DESCRIPTION" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-' | sed 's/^-//;s/-$//' | cut -c1-48)"
[ -z "$KEY" ] && exit 0

STATE_FILE="$AGENTS_DIR/$KEY.json"
[ ! -f "$STATE_FILE" ] && exit 0

STOPPED_TIME="$(date +%s)"

# Update state file: set status=stopped, add stopped_time
TMP="$(mktemp)"
jq --argjson stopped_time "$STOPPED_TIME" \
  '.status = "stopped" | .stopped_time = $stopped_time' \
  "$STATE_FILE" > "$TMP" && mv "$TMP" "$STATE_FILE"

exit 0
