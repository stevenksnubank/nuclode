#!/bin/bash
# nuclode status line — project, branch, agent activity, current tool
# Runs periodically by Claude Code to update the status bar

PARTS=""

# Current project name from git root
PROJECT=$(basename "$(git rev-parse --show-toplevel 2>/dev/null)" 2>/dev/null)
PARTS="${PROJECT:-claude}"

# Profile (only shown if strict)
PROFILE="${NUCLODE_HOOK_PROFILE:-standard}"
if [ "$PROFILE" = "strict" ]; then
    PARTS="$PARTS [strict]"
fi

# Git branch
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
if [ -n "$BRANCH" ]; then
    PARTS="$PARTS | $BRANCH"
fi

# Changed file count
CHANGED=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
if [ "$CHANGED" != "0" ]; then
    PARTS="$PARTS | ${CHANGED}~"
fi

# Active agents — count active + show phases from agents dir
AGENTS_DIR="$HOME/.claude/sessions/agents"
if [ -d "$AGENTS_DIR" ]; then
    AGENT_COUNT=0
    PHASES=""
    for f in "$AGENTS_DIR"/*.json; do
        [ -f "$f" ] || continue
        [[ "$f" == *"-activity.json" ]] && continue
        STATUS=$(python3 -c "import json,sys; d=json.load(open('$f')); print(d.get('status',''))" 2>/dev/null)
        if [ "$STATUS" = "active" ]; then
            AGENT_COUNT=$((AGENT_COUNT + 1))
            PHASE=$(python3 -c "import json,sys; d=json.load(open('$f')); print(d.get('phase',''))" 2>/dev/null)
            if [ -n "$PHASE" ] && [ -z "$PHASES" ]; then
                PHASES="$PHASE"  # show first active phase only (space-constrained)
            fi
        fi
    done
    if [ "$AGENT_COUNT" -gt 0 ]; then
        if [ "$AGENT_COUNT" -eq 1 ]; then
            PARTS="$PARTS | ${PHASES}..."
        else
            PARTS="$PARTS | ${AGENT_COUNT} agents: ${PHASES}..."
        fi
    fi
fi

# Last skill invoked
SKILL_FILE="$HOME/.claude/sessions/last-skill.txt"
if [ -f "$SKILL_FILE" ]; then
    SKILL=$(cat "$SKILL_FILE" 2>/dev/null | tr -d '\n')
    if [ -n "$SKILL" ]; then
        PARTS="$PARTS | /$SKILL"
    fi
fi

# Beads task
if command -v bd &>/dev/null && [ -d .beads ]; then
    TASK=$(bd current 2>/dev/null | head -1 | cut -d' ' -f1)
    if [ -n "$TASK" ]; then
        PARTS="$PARTS | task:${TASK}"
    fi
fi

echo "$PARTS"
