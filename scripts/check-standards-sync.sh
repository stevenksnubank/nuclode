#!/bin/bash
# check-standards-sync.sh - Verify coding standards architecture is consistent
set -euo pipefail

AGENTS_DIR="${1:-workspace/agents}"
ERRORS=0

# 1. Verify canonical sources exist
echo "Checking canonical sources..."

if [ ! -f "workspace/CLAUDE.md" ]; then
    echo "MISSING: workspace/CLAUDE.md (authoritative standards)"
    ERRORS=$((ERRORS + 1))
fi

if [ ! -f "workspace/skills/coding-standards.md" ]; then
    echo "MISSING: workspace/skills/coding-standards.md (detailed examples)"
    ERRORS=$((ERRORS + 1))
fi

if [ ! -f "$AGENTS_DIR/includes/coding-standards.md" ]; then
    echo "MISSING: $AGENTS_DIR/includes/coding-standards.md (reference copy)"
    ERRORS=$((ERRORS + 1))
fi

if [ ! -f "$AGENTS_DIR/includes/trust-boundary.md" ]; then
    echo "MISSING: $AGENTS_DIR/includes/trust-boundary.md (reference copy)"
    ERRORS=$((ERRORS + 1))
fi

# 2. Verify CLAUDE.md has coding standards section
if ! grep -q "^## Coding Standards" workspace/CLAUDE.md; then
    echo "MISSING: ## Coding Standards section in CLAUDE.md"
    ERRORS=$((ERRORS + 1))
fi

# 3. Verify all agents reference standards (not inline them)
echo "Checking agent prompts reference standards..."

for agent_dir in "$AGENTS_DIR"/*/; do
    [ ! -f "$agent_dir/system_prompt.md" ] && continue
    AGENT=$(basename "$agent_dir")
    [ "$AGENT" = "_base" ] && continue
    [ "$AGENT" = "includes" ] && continue

    # Should have the reference section
    if ! grep -q "^## Standards & Trust Boundaries" "$agent_dir/system_prompt.md"; then
        echo "MISSING: $AGENT lacks '## Standards & Trust Boundaries' reference"
        ERRORS=$((ERRORS + 1))
    fi

    # Should NOT have inline coding standards (indicates duplication)
    if grep -q "^## Coding Standards$" "$agent_dir/system_prompt.md"; then
        echo "DRIFT: $AGENT has inline '## Coding Standards' — should reference CLAUDE.md instead"
        ERRORS=$((ERRORS + 1))
    fi

    # Should NOT have inline trust boundaries (indicates duplication)
    if grep -q "^## Trust Boundaries$" "$agent_dir/system_prompt.md"; then
        echo "DRIFT: $AGENT has inline '## Trust Boundaries' — should reference CLAUDE.md instead"
        ERRORS=$((ERRORS + 1))
    fi
done

if [ "$ERRORS" -eq 0 ]; then
    echo "OK: Standards architecture is consistent (CLAUDE.md authoritative, agents reference, skill provides examples)"
else
    echo "FAIL: $ERRORS issues found"
    exit 1
fi
