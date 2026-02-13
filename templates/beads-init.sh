#!/bin/bash
# beads-init.sh - Initialize beads in a project directory
# Called by: nuclode init

set -e

PROJECT_DIR="${1:-.}"
PROJECT_NAME=$(basename "$(cd "$PROJECT_DIR" && pwd)")

echo "Initializing beads in: $PROJECT_DIR"

# Check if beads is installed
if ! command -v bd &> /dev/null; then
    echo "Error: beads (bd) is not installed."
    echo "Install with: brew install beads"
    echo "         or: npm install -g @beads/bd"
    echo "         or: curl -fsSL https://raw.githubusercontent.com/steveyegge/beads/main/scripts/install.sh | bash"
    exit 1
fi

# Check if already initialized
if [ -d "$PROJECT_DIR/.beads" ]; then
    echo "Beads already initialized in this project."
    exit 0
fi

# Initialize beads
cd "$PROJECT_DIR"
bd init

# Configure bv post-export hook if bv is available
if command -v bv &>/dev/null; then
    BEADS_CONFIG="$PROJECT_DIR/.beads/config.yaml"
    if [ -f "$BEADS_CONFIG" ]; then
        # Only add hooks if not already configured
        if ! grep -q "post-export-graph" "$BEADS_CONFIG" 2>/dev/null; then
            # Safety newline before appending YAML
            echo "" >> "$BEADS_CONFIG"
            cat >> "$BEADS_CONFIG" << 'HOOKEOF'
# Auto-generate Mermaid dependency graph on export (requires bv)
hooks:
  post-export:
    - command: "core/beads/hooks/post-export-graph.sh"
      description: "Auto-generate Mermaid dependency graph on export"
HOOKEOF
            echo "Configured bv post-export hook for dependency graph generation"
        fi
    fi
fi

# Copy project CLAUDE.md template if no CLAUDE.md exists
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ ! -f "$PROJECT_DIR/CLAUDE.md" ]; then
    if [ -f "$SCRIPT_DIR/project-CLAUDE.md" ]; then
        sed "s/\[PROJECT_NAME\]/$PROJECT_NAME/g" "$SCRIPT_DIR/project-CLAUDE.md" > "$PROJECT_DIR/CLAUDE.md"
        echo "Created CLAUDE.md from template"
    fi
fi

echo ""
echo "Beads initialized! Quick start:"
echo "  bd create \"Your first task\""
echo "  bd list"
echo "  bv                              # Interactive viewer"
