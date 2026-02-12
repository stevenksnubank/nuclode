#!/bin/bash
# nuclode setup - Interactive installer for the nuclode agentic workspace
# Usage: ./setup.sh [--layer nubank] [--no-backup]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$HOME/.claude"
BACKUP_DIR="$HOME/.claude.backup.$(date +%Y%m%d-%H%M%S)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info()  { echo -e "${BLUE}[info]${NC} $1"; }
ok()    { echo -e "${GREEN}[ok]${NC} $1"; }
warn()  { echo -e "${YELLOW}[warn]${NC} $1"; }
error() { echo -e "${RED}[error]${NC} $1"; }

# Parse arguments
LAYERS=()
NO_BACKUP=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --layer)  LAYERS+=("$2"); shift 2 ;;
        --no-backup) NO_BACKUP=true; shift ;;
        *) shift ;;
    esac
done

echo ""
echo "  ╔═══════════════════════════════════════╗"
echo "  ║     nuclode - Agentic Workspace       ║"
echo "  ║   nu + claude + code = nucleotide     ║"
echo "  ╚═══════════════════════════════════════╝"
echo ""

# ─── Step 1: Prerequisites ───────────────────────────────────────────
info "Checking prerequisites..."

# Check Claude Code CLI
if command -v claude &> /dev/null; then
    ok "Claude Code CLI found"
else
    warn "Claude Code CLI not found. Install from: https://claude.ai/claude-code"
fi

# Check beads
if command -v bd &> /dev/null; then
    ok "beads (bd) found: $(bd --version 2>/dev/null || echo 'installed')"
else
    warn "beads (bd) not found"
    read -p "  Install beads? [Y/n] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        if command -v brew &> /dev/null; then
            brew install beads
        elif command -v npm &> /dev/null; then
            npm install -g @beads/bd
        else
            curl -fsSL https://raw.githubusercontent.com/steveyegge/beads/main/scripts/install.sh | bash
        fi
        ok "beads installed"
    fi
fi

# Check beads viewer
if command -v bv &> /dev/null; then
    ok "beads viewer (bv) found"
else
    warn "beads viewer (bv) not found"
    read -p "  Install beads viewer? [Y/n] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        if command -v brew &> /dev/null; then
            brew install dicklesworthstone/tap/bv
        else
            curl -fsSL "https://raw.githubusercontent.com/Dicklesworthstone/beads_viewer/main/install.sh" | bash
        fi
        ok "beads viewer installed"
    fi
fi

# Check jq (required for network-guard hook)
if command -v jq &> /dev/null; then
    ok "jq found"
else
    warn "jq not found (required for network-guard hook)"
    read -p "  Install jq? [Y/n] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        if command -v brew &> /dev/null; then
            brew install jq
        elif command -v apt-get &> /dev/null; then
            sudo apt-get install -y jq
        else
            error "Could not install jq automatically. Please install it manually."
        fi
        ok "jq installed"
    fi
fi

# ─── Step 2: Layer Selection ─────────────────────────────────────────
if [ ${#LAYERS[@]} -eq 0 ]; then
    info "Available layers:"
    echo ""
    # List layers dynamically
    for layer_dir in "$SCRIPT_DIR"/layers/*/; do
        if [ -d "$layer_dir" ]; then
            layer_name=$(basename "$layer_dir")
            echo "  - $layer_name"
        fi
    done
    echo ""

    # Ask about each layer
    for layer_dir in "$SCRIPT_DIR"/layers/*/; do
        if [ -d "$layer_dir" ]; then
            layer_name=$(basename "$layer_dir")
            read -p "  Enable $layer_name layer? [y/N] " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                LAYERS+=("$layer_name")
            fi
        fi
    done
fi

echo ""
info "Selected layers: core${LAYERS[*]:+ + ${LAYERS[*]}}"

# ─── Step 3: Backup ──────────────────────────────────────────────────
if [ -d "$CLAUDE_DIR" ] && [ "$NO_BACKUP" = false ]; then
    info "Backing up existing ~/.claude to $BACKUP_DIR"

    # Create backup
    cp -r "$CLAUDE_DIR" "$BACKUP_DIR"
    ok "Backup created at $BACKUP_DIR"

    # Preserve user-specific files
    PRESERVED_FILES=()
    if [ -f "$CLAUDE_DIR/settings.local.json" ]; then
        PRESERVED_FILES+=("settings.local.json")
    fi
    if [ -d "$CLAUDE_DIR/memory" ]; then
        PRESERVED_FILES+=("memory/")
    fi
    if [ ${#PRESERVED_FILES[@]} -gt 0 ]; then
        info "Will preserve: ${PRESERVED_FILES[*]}"
    fi
fi

# ─── Step 4: Install Core ────────────────────────────────────────────
info "Installing core workspace..."

# Create base directory structure
mkdir -p "$CLAUDE_DIR"/{agents,commands/agents,hooks,skills,beads}

# Copy core files
cp "$SCRIPT_DIR/core/CLAUDE.md" "$CLAUDE_DIR/CLAUDE.md"
cp "$SCRIPT_DIR/core/AGENTS.md" "$CLAUDE_DIR/AGENTS.md"
cp "$SCRIPT_DIR/core/agents/README.md" "$CLAUDE_DIR/agents/README.md"

# Copy agent configs
for agent_dir in "$SCRIPT_DIR"/core/agents/*/; do
    if [ -d "$agent_dir" ]; then
        agent_name=$(basename "$agent_dir")
        mkdir -p "$CLAUDE_DIR/agents/$agent_name"
        cp "$agent_dir"/* "$CLAUDE_DIR/agents/$agent_name/"
    fi
done

# Copy commands
cp "$SCRIPT_DIR"/core/commands/agents/*.md "$CLAUDE_DIR/commands/agents/"
for cmd_file in "$SCRIPT_DIR"/core/commands/*.md; do
    if [ -f "$cmd_file" ]; then
        cp "$cmd_file" "$CLAUDE_DIR/commands/"
    fi
done

# Copy beads templates
cp "$SCRIPT_DIR"/core/beads/* "$CLAUDE_DIR/beads/"

# Copy hooks (network-guard and domain lists)
if [ -d "$SCRIPT_DIR/core/hooks" ]; then
    cp "$SCRIPT_DIR"/core/hooks/* "$CLAUDE_DIR/hooks/"
    chmod +x "$CLAUDE_DIR/hooks/"*.sh 2>/dev/null || true
    ok "Network guard hooks installed"
fi

# Install settings.json and .mcp.json
cp "$SCRIPT_DIR/core/settings.json" "$CLAUDE_DIR/settings.json"
cp "$SCRIPT_DIR/core/.mcp.json" "$CLAUDE_DIR/.mcp.json"

ok "Core workspace installed"

# ─── Step 5: Install Layers ──────────────────────────────────────────
for layer in "${LAYERS[@]}"; do
    layer_dir="$SCRIPT_DIR/layers/$layer"

    if [ ! -d "$layer_dir" ]; then
        warn "Layer '$layer' not found, skipping"
        continue
    fi

    info "Installing layer: $layer"

    # Append layer CLAUDE.md to main CLAUDE.md
    if [ -f "$layer_dir/CLAUDE.md" ]; then
        echo "" >> "$CLAUDE_DIR/CLAUDE.md"
        echo "---" >> "$CLAUDE_DIR/CLAUDE.md"
        echo "" >> "$CLAUDE_DIR/CLAUDE.md"
        cat "$layer_dir/CLAUDE.md" >> "$CLAUDE_DIR/CLAUDE.md"
        ok "  Merged $layer CLAUDE.md"
    fi

    # Deep-merge settings.json (append enabledPlugins)
    if [ -f "$layer_dir/settings.json" ]; then
        if command -v python3 &> /dev/null; then
            python3 - "$CLAUDE_DIR/settings.json" "$layer_dir/settings.json" << 'PYEOF'
import json
import sys

with open(sys.argv[1]) as f:
    base = json.load(f)

with open(sys.argv[2]) as f:
    overlay = json.load(f)

# Deep merge
for key, value in overlay.items():
    if key in base and isinstance(base[key], dict) and isinstance(value, dict):
        base[key].update(value)
    else:
        base[key] = value

with open(sys.argv[1], 'w') as f:
    json.dump(base, f, indent=2)
PYEOF
            ok "  Merged $layer settings.json"
        else
            warn "  Python3 not found, skipping settings merge for $layer"
        fi
    fi

    # Merge .mcp.json (add servers)
    if [ -f "$layer_dir/.mcp.json" ]; then
        if command -v python3 &> /dev/null; then
            python3 - "$CLAUDE_DIR/.mcp.json" "$layer_dir/.mcp.json" << 'PYEOF'
import json
import sys

with open(sys.argv[1]) as f:
    base = json.load(f)

with open(sys.argv[2]) as f:
    overlay = json.load(f)

base.setdefault('mcpServers', {}).update(overlay.get('mcpServers', {}))

with open(sys.argv[1], 'w') as f:
    json.dump(base, f, indent=2)
PYEOF
            ok "  Merged $layer .mcp.json"
        fi
    fi

    # Apply agent overrides
    if [ -d "$layer_dir/agents" ]; then
        for override_file in "$layer_dir"/agents/*-overrides.json; do
            if [ -f "$override_file" ]; then
                agent_name=$(basename "$override_file" | sed 's/-overrides.json//')
                if command -v python3 &> /dev/null; then
                    python3 - "$CLAUDE_DIR/agents/$agent_name/agent.json" "$override_file" << 'PYEOF'
import json
import sys

with open(sys.argv[1]) as f:
    agent = json.load(f)

with open(sys.argv[2]) as f:
    overrides = json.load(f)

# Append to arrays
for key in ['additional_tools', 'additional_mcp_servers', 'additional_capabilities']:
    target_key = key.replace('additional_', '')
    if key in overrides:
        agent.setdefault(target_key, []).extend(overrides[key])

with open(sys.argv[1], 'w') as f:
    json.dump(agent, f, indent=2)
PYEOF
                    ok "  Applied $agent_name overrides"
                fi
            fi
        done
    fi

    # Merge layer-specific domain lists (append to core lists)
    if [ -d "$layer_dir/hooks" ]; then
        if [ -f "$layer_dir/hooks/allowed-domains.txt" ]; then
            echo "" >> "$CLAUDE_DIR/hooks/allowed-domains.txt"
            echo "# ─── Layer: $layer ────────────────────────────────────────────────────" >> "$CLAUDE_DIR/hooks/allowed-domains.txt"
            cat "$layer_dir/hooks/allowed-domains.txt" >> "$CLAUDE_DIR/hooks/allowed-domains.txt"
            ok "  Merged $layer allowed-domains.txt"
        fi
        if [ -f "$layer_dir/hooks/blocked-domains.txt" ]; then
            echo "" >> "$CLAUDE_DIR/hooks/blocked-domains.txt"
            echo "# ─── Layer: $layer ────────────────────────────────────────────────────" >> "$CLAUDE_DIR/hooks/blocked-domains.txt"
            cat "$layer_dir/hooks/blocked-domains.txt" >> "$CLAUDE_DIR/hooks/blocked-domains.txt"
            ok "  Merged $layer blocked-domains.txt"
        fi
    fi

    # Copy layer scripts
    if [ -d "$layer_dir/scripts" ]; then
        mkdir -p "$CLAUDE_DIR/scripts"
        cp -r "$layer_dir/scripts/"* "$CLAUDE_DIR/scripts/" 2>/dev/null || true
        ok "  Copied $layer scripts"
    fi

    ok "Layer '$layer' installed"
done

# ─── Step 6: Restore Preserved Files ─────────────────────────────────
if [ -d "$BACKUP_DIR" ]; then
    if [ -f "$BACKUP_DIR/settings.local.json" ]; then
        cp "$BACKUP_DIR/settings.local.json" "$CLAUDE_DIR/settings.local.json"
        ok "Restored settings.local.json"
    fi
    if [ -d "$BACKUP_DIR/memory" ]; then
        cp -r "$BACKUP_DIR/memory" "$CLAUDE_DIR/memory"
        ok "Restored memory/"
    fi
fi

# ─── Step 7: Install Shell Functions ──────────────────────────────────
if [ -f "$SCRIPT_DIR/shell/nuclode.sh" ]; then
    mkdir -p "$CLAUDE_DIR/shell"
    cp "$SCRIPT_DIR/shell/nuclode.sh" "$CLAUDE_DIR/shell/nuclode.sh"

    # Detect shell profile and add source line
    SHELL_PROFILE=""
    if [ -f "$HOME/.zshrc" ]; then
        SHELL_PROFILE="$HOME/.zshrc"
    elif [ -f "$HOME/.bashrc" ]; then
        SHELL_PROFILE="$HOME/.bashrc"
    elif [ -f "$HOME/.bash_profile" ]; then
        SHELL_PROFILE="$HOME/.bash_profile"
    fi

    if [ -n "$SHELL_PROFILE" ]; then
        SOURCE_LINE="source $CLAUDE_DIR/shell/nuclode.sh"
        if ! grep -qF "$SOURCE_LINE" "$SHELL_PROFILE" 2>/dev/null; then
            echo "" >> "$SHELL_PROFILE"
            echo "# nuclode shell functions" >> "$SHELL_PROFILE"
            echo "$SOURCE_LINE" >> "$SHELL_PROFILE"
            ok "Added shell functions to $(basename "$SHELL_PROFILE")"
            info "Available: claude-worktree (cw), remove-worktrees"
        else
            ok "Shell functions already sourced in $(basename "$SHELL_PROFILE")"
        fi
    else
        warn "Could not detect shell profile. Add manually:"
        echo "  source $CLAUDE_DIR/shell/nuclode.sh"
    fi
fi

# ─── Step 8: Install nuclode CLI ─────────────────────────────────────
info "Installing nuclode CLI..."

NUCLODE_BIN="$HOME/.local/bin/nuclode"
mkdir -p "$HOME/.local/bin"

cat > "$NUCLODE_BIN" << 'NUCLODE_EOF'
#!/bin/bash
# nuclode - Agentic workspace CLI
# Usage: nuclode <command> [args]

set -e

NUCLODE_DIR="$(cat "$HOME/.claude/.nuclode-source" 2>/dev/null || echo "$HOME/dev/nuclode")"
TEMPLATES_DIR="$NUCLODE_DIR/templates"

case "${1:-help}" in
    init)
        # Initialize beads in current project
        if [ -f "$TEMPLATES_DIR/beads-init.sh" ]; then
            bash "$TEMPLATES_DIR/beads-init.sh" "${2:-.}"
        else
            echo "Error: nuclode templates not found at $TEMPLATES_DIR"
            exit 1
        fi
        ;;

    update)
        # Pull latest and re-run setup
        echo "Updating nuclode from: $NUCLODE_DIR"
        cd "$NUCLODE_DIR"
        git pull
        exec "$NUCLODE_DIR/setup.sh" "$@"
        ;;

    layers)
        # List available and active layers
        echo "Available layers:"
        for layer_dir in "$NUCLODE_DIR"/layers/*/; do
            if [ -d "$layer_dir" ]; then
                echo "  - $(basename "$layer_dir")"
            fi
        done
        ;;

    help|--help|-h)
        echo "nuclode - Agentic workspace CLI"
        echo ""
        echo "Commands:"
        echo "  init [dir]     Initialize beads + project template in directory"
        echo "  update         Pull latest nuclode and re-run setup"
        echo "  layers         List available layers"
        echo "  help           Show this help"
        echo ""
        echo "Source: $NUCLODE_DIR"
        ;;

    *)
        echo "Unknown command: $1"
        echo "Run 'nuclode help' for usage"
        exit 1
        ;;
esac
NUCLODE_EOF

chmod +x "$NUCLODE_BIN"

# Store the source directory reference
echo "$SCRIPT_DIR" > "$CLAUDE_DIR/.nuclode-source"

ok "nuclode CLI installed to $NUCLODE_BIN"

# Check if ~/.local/bin is in PATH
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    warn "$HOME/.local/bin is not in your PATH"
    echo "  Add to your shell profile:"
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

# ─── Done! ────────────────────────────────────────────────────────────
echo ""
echo "  ╔═══════════════════════════════════════╗"
echo "  ║      nuclode installed!               ║"
echo "  ╚═══════════════════════════════════════╝"
echo ""
echo "  Workspace: $CLAUDE_DIR"
echo "  Layers:    core${LAYERS[*]:+ + ${LAYERS[*]}}"
echo "  CLI:       $NUCLODE_BIN"
if [ -d "$BACKUP_DIR" ]; then
    echo "  Backup:    $BACKUP_DIR"
fi
echo ""
echo "  Next steps:"
echo "    1. Start a Claude Code session"
echo "    2. Run 'nuclode init' in any project for beads"
echo "    3. Use /agents:code-planner to plan features"
echo ""
