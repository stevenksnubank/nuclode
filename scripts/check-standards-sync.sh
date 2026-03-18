#!/bin/bash
# check-standards-sync.sh - Verify coding standards are identical across agents
set -euo pipefail

AGENTS_DIR="${1:-workspace/agents}"
REFERENCE="$AGENTS_DIR/code-planner/system_prompt.md"
ERRORS=0

extract_standards() {
    sed -n '/^## Coding Standards$/,/^## [^C]/{ /^## [^C]/d; p; }' "$1"
}

REF_STANDARDS=$(extract_standards "$REFERENCE")

for agent_dir in "$AGENTS_DIR"/*/; do
    [ ! -f "$agent_dir/system_prompt.md" ] && continue
    AGENT=$(basename "$agent_dir")
    [ "$AGENT" = "_base" ] && continue
    [ "$AGENT" = "includes" ] && continue
    AGENT_STANDARDS=$(extract_standards "$agent_dir/system_prompt.md")
    if [ "$REF_STANDARDS" != "$AGENT_STANDARDS" ]; then
        echo "DRIFT: $AGENT coding standards differ from code-planner"
        diff <(echo "$REF_STANDARDS") <(echo "$AGENT_STANDARDS") || true
        ERRORS=$((ERRORS + 1))
    fi
done

# Also check trust-boundary section sync
extract_trust_boundary() {
    sed -n '/^## Trust Boundaries$/,/^## [^T]/{ /^## [^T]/d; p; }' "$1"
}

REF_TRUST=$(extract_trust_boundary "$REFERENCE")

for agent_dir in "$AGENTS_DIR"/*/; do
    [ ! -f "$agent_dir/system_prompt.md" ] && continue
    AGENT=$(basename "$agent_dir")
    [ "$AGENT" = "_base" ] && continue
    [ "$AGENT" = "includes" ] && continue
    AGENT_TRUST=$(extract_trust_boundary "$agent_dir/system_prompt.md")
    if [ "$REF_TRUST" != "$AGENT_TRUST" ]; then
        echo "DRIFT: $AGENT trust boundary differs from code-planner"
        diff <(echo "$REF_TRUST") <(echo "$AGENT_TRUST") || true
        ERRORS=$((ERRORS + 1))
    fi
done

if [ "$ERRORS" -eq 0 ]; then
    echo "OK: All agents have identical coding standards and trust boundaries"
else
    echo "FAIL: $ERRORS agents have drifted"
    exit 1
fi
