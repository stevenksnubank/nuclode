#!/bin/bash
# sensitive-path-guard.sh — PreToolUse hook for Read, Grep, Glob
#
# Blocks reads of sensitive system and credential files.
# Applies to: /etc/passwd, /etc/shadow, ~/.ssh/ private keys,
# ~/.aws/credentials, ~/.gnupg/ private keys, ~/.netrc, and similar.
#
# Checks both the raw path and the realpath-resolved path so symlink
# indirection (e.g. macOS /etc -> /private/etc) cannot be used to bypass.
#
# Requires: jq

set -uo pipefail

INPUT="$(cat)"
TOOL_NAME="$(echo "$INPUT" | jq -r '.tool_name // empty')"

# Extract the path being accessed depending on tool
case "$TOOL_NAME" in
    Read)
        TARGET="$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')"
        ;;
    Grep)
        TARGET="$(echo "$INPUT" | jq -r '.tool_input.path // empty')"
        ;;
    Glob)
        TARGET="$(echo "$INPUT" | jq -r '.tool_input.path // empty')"
        ;;
    *)
        exit 0
        ;;
esac

[ -z "$TARGET" ] && exit 0

# Expand ~ to home directory
HOME_DIR="$HOME"
TARGET="${TARGET/#\~/$HOME_DIR}"

# Resolve symlinks. Keep both: raw path catches /etc/passwd,
# resolved path catches OS-specific symlink destinations.
RESOLVED="$(realpath -q "$TARGET" 2>/dev/null || echo "$TARGET")"

block() {
    local path="$1"
    local reason="$2"
    printf '{"decision":"block","reason":"SENSITIVE PATH GUARD: Access to %s blocked. %s DO NOT attempt alternative paths or workarounds."}\n' \
        "$path" "$reason"
    exit 0
}

# Returns 0 if either the raw or resolved path matches the pattern
matches_either() {
    local pattern="$1"
    [[ "$TARGET"   =~ $pattern ]] || [[ "$RESOLVED" =~ $pattern ]]
}

# ── Sensitive path patterns ───────────────────────────────────────────────────

# /etc/passwd, /etc/shadow, /etc/sudoers, /etc/master.passwd
# Pattern anchors to /etc/ so it matches regardless of any OS-level prefix
if matches_either '/etc/(passwd|shadow|sudoers|master\.passwd|gshadow)$'; then
    block "$TARGET" "System credential file."
fi

# ~/.ssh/ private keys (id_rsa, id_ed25519, id_ecdsa, etc. — not .pub files)
if matches_either "$HOME_DIR/\.ssh/(id_[^.]+|.*_key)$"; then
    block "$TARGET" "SSH private key."
fi

# ~/.aws/credentials
if matches_either "$HOME_DIR/\.aws/credentials$"; then
    block "$TARGET" "AWS credentials file."
fi

# ~/.gnupg/ private key material
if matches_either "$HOME_DIR/\.gnupg/(private-keys-v1\.d|secring\.gpg|trustdb\.gpg)"; then
    block "$TARGET" "GPG private key material."
fi

# ~/.netrc (plaintext passwords)
if matches_either "$HOME_DIR/\.netrc$"; then
    block "$TARGET" "Plaintext credential file."
fi

# ~/.pgpass (PostgreSQL passwords)
if matches_either "$HOME_DIR/\.pgpass$"; then
    block "$TARGET" "PostgreSQL password file."
fi

# macOS Keychain databases (~/.Library is user-specific, portable via $HOME)
if matches_either "$HOME_DIR/Library/Keychains/"; then
    block "$TARGET" "macOS Keychain database."
fi

exit 0
