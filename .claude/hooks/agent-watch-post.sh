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

# Read phase and bead snapshot from state file
PHASE="$(jq -r '.phase // empty' "$STATE_FILE")"
SNAP_INTENT="$(jq -r '.bead_snapshot.intent // 0' "$STATE_FILE")"
SNAP_DECISION="$(jq -r '.bead_snapshot.decision // 0' "$STATE_FILE")"
SNAP_REVIEW="$(jq -r '.bead_snapshot.review // 0' "$STATE_FILE")"

# Update state file: set status=stopped, add stopped_time
TMP="$(mktemp)"
jq --argjson stopped_time "$STOPPED_TIME" \
  '.status = "stopped" | .stopped_time = $stopped_time' \
  "$STATE_FILE" > "$TMP" && mv "$TMP" "$STATE_FILE"

# ── Bead gate checks ─────────────────────────────────────────────────────────
# Compare current bead counts against pre-agent snapshots.
# If a required bead type wasn't written, emit an additionalContext warning
# so the main session surfaces it immediately.

WARNINGS=()

if command -v bd &>/dev/null; then
    NOW_INTENT="$(bd query --filter "label:intent"   2>/dev/null | grep -c . || echo 0)"
    NOW_DECISION="$(bd query --filter "label:decision" 2>/dev/null | grep -c . || echo 0)"
    NOW_REVIEW="$(bd query --filter "label:review"   2>/dev/null | grep -c . || echo 0)"

    case "$PHASE" in
        planning)
            if [ "$NOW_INTENT" -le "$SNAP_INTENT" ]; then
                WARNINGS+=("intent bead (scope + constraints) — run: bd create \"Intent: <goal>\" -l intent --ephemeral --silent")
            fi
            if [ "$NOW_DECISION" -le "$SNAP_DECISION" ]; then
                WARNINGS+=("decision bead (approach chosen + alternatives rejected) — run: bd create \"Decision: <what>\" --type decision -l decision --silent")
            fi
            ;;
        reviewing)
            if [ "$NOW_REVIEW" -le "$SNAP_REVIEW" ]; then
                WARNINGS+=("review bead (findings + rejected patterns) — run: bd create \"Review: <what>\" -l review,<severity> --silent")
            fi
            ;;
        "security review")
            if [ "$NOW_REVIEW" -le "$SNAP_REVIEW" ]; then
                WARNINGS+=("security review bead (vulnerabilities + mitigations) — run: bd create \"Review: security — <what>\" -l review,security,<severity> --silent")
            fi
            ;;
    esac
fi

if [ "${#WARNINGS[@]}" -gt 0 ]; then
    MSG="⚠️ BEAD GATE — ${DESCRIPTION} finished without writing required beads:"
    for W in "${WARNINGS[@]}"; do
        MSG="$MSG\n  • Missing: $W"
    done
    MSG="$MSG\nWrite the missing beads before moving to the next phase."
    printf '{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"%s"}}' \
        "$(echo -e "$MSG" | sed 's/"/\\"/g' | tr '\n' ' ')"
fi

exit 0
