#!/bin/bash
# nuclode status line — shows branch, file status, and active phase
# Runs periodically by Claude Code to update the status bar

PARTS="nuclode"

# Only show profile if non-default (strict is notable)
PROFILE="${NUCLODE_HOOK_PROFILE:-standard}"
if [ "$PROFILE" = "strict" ]; then
    PARTS="$PARTS [strict]"
fi

# Git branch (fast, no network)
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
if [ -n "$BRANCH" ]; then
    PARTS="$PARTS | $BRANCH"
fi

# Changed file count
CHANGED=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
if [ "$CHANGED" != "0" ]; then
    PARTS="$PARTS | ${CHANGED} changed"
fi

# Active task (if beads is set up)
if command -v bd &>/dev/null && [ -d .beads ]; then
    TASK=$(bd current 2>/dev/null | head -1 | cut -d' ' -f1)
    if [ -n "$TASK" ]; then
        PARTS="$PARTS | task:${TASK}"
    fi
fi

# Active agent phase (written by agent_tracker.py)
PHASE_FILE="$HOME/.claude/sessions/active-phase"
if [ -f "$PHASE_FILE" ]; then
    PHASE=$(cat "$PHASE_FILE" 2>/dev/null | tr -d '\n')
    if [ -n "$PHASE" ]; then
        PARTS="$PARTS | ${PHASE}..."
    fi
fi

echo "$PARTS"
