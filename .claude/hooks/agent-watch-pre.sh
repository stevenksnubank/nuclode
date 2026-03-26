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

# Snapshot bead counts for phases that have required bead writes.
# Stored in state file so post-hook can diff and warn if nothing was written.
BEAD_SNAPSHOT_INTENT=0
BEAD_SNAPSHOT_DECISION=0
BEAD_SNAPSHOT_REVIEW=0

if command -v bd &>/dev/null; then
    case "$PHASE" in
        planning)
            BEAD_SNAPSHOT_INTENT="$(bd query --filter "label:intent"  2>/dev/null | grep -c . || echo 0)"
            BEAD_SNAPSHOT_DECISION="$(bd query --filter "label:decision" 2>/dev/null | grep -c . || echo 0)"
            ;;
        reviewing|"security review")
            BEAD_SNAPSHOT_REVIEW="$(bd query --filter "label:review" 2>/dev/null | grep -c . || echo 0)"
            ;;
    esac
fi

# Write state file (includes bead snapshot for post-hook diffing)
jq -n \
  --arg key "$KEY" \
  --arg name "$DESCRIPTION" \
  --arg phase "$PHASE" \
  --argjson start_time "$START_TIME" \
  --argjson snap_intent "$BEAD_SNAPSHOT_INTENT" \
  --argjson snap_decision "$BEAD_SNAPSHOT_DECISION" \
  --argjson snap_review "$BEAD_SNAPSHOT_REVIEW" \
  '{key: $key, name: $name, phase: $phase, status: "active", start_time: $start_time,
    bead_snapshot: {intent: $snap_intent, decision: $snap_decision, review: $snap_review}}' \
  > "$AGENTS_DIR/$KEY.json"

# Write activity file
jq -n \
  --arg summary "$SUBAGENT_TYPE" \
  '{tool: "Agent", summary: $summary}' \
  > "$AGENTS_DIR/$KEY-activity.json"

exit 0
