#!/bin/bash
# network-guard.sh - PreToolUse hook to block network requests to unapproved domains
#
# Prevents AI agents from exfiltrating data to unauthorized external services.
# Works as a Claude Code PreToolUse hook for Bash and WebFetch tool calls.
#
# Requires: jq
#
# Domain resolution order:
#   1. blocked-domains.txt - always denied (checked first)
#   2. allowed-domains.txt - explicitly permitted
#   3. Everything else - denied by default (fail-secure)

set -euo pipefail

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ALLOWED_DOMAINS_FILE="$HOOK_DIR/allowed-domains.txt"
BLOCKED_DOMAINS_FILE="$HOOK_DIR/blocked-domains.txt"

# Network command patterns that indicate outbound requests
NETWORK_COMMANDS='curl|wget|nc|ncat|netcat|ssh|scp|sftp|rsync|ftp|telnet|nmap|socat|httpie|http|xh'

# Read stdin (hook receives JSON on stdin)
INPUT="$(cat)"

TOOL_NAME="$(echo "$INPUT" | jq -r '.tool_name // empty')"
TOOL_INPUT="$(echo "$INPUT" | jq -r '.tool_input // empty')"

# Load domain lists, stripping comments and blank lines
load_domains() {
    local file="$1"
    if [ -f "$file" ]; then
        grep -v '^\s*#' "$file" | grep -v '^\s*$' | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]'
    fi
}

# Extract domain from a URL using Python's urllib for robust parsing.
# Falls back to conservative bash parsing if python3 unavailable.
extract_domain() {
    local url="$1"

    # Primary: use Python's urllib.parse for correct URL parsing
    # This handles: embedded credentials, IPv6, punycode, edge cases
    if command -v python3 &>/dev/null; then
        local result
        result="$(python3 -c "
import sys
from urllib.parse import urlparse

url = sys.argv[1]
# Ensure URL has a scheme for urlparse to work correctly
if '://' not in url and not url.startswith('//'):
    url = 'https://' + url
parsed = urlparse(url)
hostname = parsed.hostname or ''
# hostname already strips brackets from IPv6 and lowercases
print(hostname)
" "$url" 2>/dev/null)"
        if [ -n "$result" ]; then
            echo "$result"
            return
        fi
    fi

    # Fallback: conservative bash parsing (deny if ambiguous)
    local domain="${url#*://}"
    domain="${domain%%/*}"
    domain="${domain%%\?*}"
    domain="${domain%%#*}"
    # If domain contains @, it has userinfo - extract host after last @
    if [[ "$domain" == *@* ]]; then
        domain="${domain##*@}"
    fi
    # Remove port (but handle IPv6 brackets first)
    if [[ "$domain" == \[* ]]; then
        # IPv6: extract between brackets
        domain="${domain#\[}"
        domain="${domain%%\]*}"
    else
        domain="${domain%%:*}"
    fi
    echo "$domain" | tr '[:upper:]' '[:lower:]'
}

# Check if a domain matches any entry in a domain list file.
# Supports exact match and subdomain matching (e.g., "catbox.moe" matches "api.catbox.moe").
domain_in_list() {
    local domain="$1"
    local list_file="$2"

    if [ ! -f "$list_file" ]; then
        return 1
    fi

    while IFS= read -r entry; do
        # Skip comments and blank lines
        [[ -z "$entry" || "$entry" =~ ^[[:space:]]*# ]] && continue
        entry="$(echo "$entry" | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]')"
        [ -z "$entry" ] && continue

        # Exact match
        if [ "$domain" = "$entry" ]; then
            return 0
        fi
        # Subdomain match: domain ends with .entry
        if [[ "$domain" == *".$entry" ]]; then
            return 0
        fi
    done < "$list_file"

    return 1
}

# Deny with a clear message
deny() {
    local domain="$1"
    local reason="$2"
    cat <<EOF
{"decision":"block","reason":"NETWORK GUARD: Request to '$domain' blocked. $reason. DO NOT attempt alternative domains, workarounds, or retries. Ask the user for guidance."}
EOF
    exit 0
}

# Allow (exit silently with 0)
allow() {
    exit 0
}

# Extract URLs from a bash command string
extract_urls_from_command() {
    local cmd="$1"
    # Match http(s):// URLs and bare domain patterns after network commands
    echo "$cmd" | grep -oE 'https?://[^ "'"'"'|;&)}>]+' 2>/dev/null || true
}

# ─── Main Logic ──────────────────────────────────────────────────────────────

case "$TOOL_NAME" in
    Bash)
        COMMAND="$(echo "$TOOL_INPUT" | jq -r '.command // empty')"
        [ -z "$COMMAND" ] && allow

        # Check if this is a network command
        if ! echo "$COMMAND" | grep -qE "\b($NETWORK_COMMANDS)\b"; then
            allow
        fi

        # Extract URLs from the command
        URLS="$(extract_urls_from_command "$COMMAND")"
        [ -z "$URLS" ] && allow

        # Check each URL's domain
        while IFS= read -r url; do
            [ -z "$url" ] && continue
            DOMAIN="$(extract_domain "$url")"
            [ -z "$DOMAIN" ] && continue

            # 1. Check blocklist first (always denied)
            if domain_in_list "$DOMAIN" "$BLOCKED_DOMAINS_FILE"; then
                deny "$DOMAIN" "Domain is on the blocklist (known data exfiltration target)"
            fi

            # 2. Check allowlist (must be explicitly permitted)
            if ! domain_in_list "$DOMAIN" "$ALLOWED_DOMAINS_FILE"; then
                deny "$DOMAIN" "Domain is not on the approved allowlist"
            fi
        done <<< "$URLS"

        # All URLs passed checks
        allow
        ;;

    WebFetch)
        URL="$(echo "$TOOL_INPUT" | jq -r '.url // empty')"
        [ -z "$URL" ] && allow

        DOMAIN="$(extract_domain "$URL")"
        [ -z "$DOMAIN" ] && allow

        # 1. Check blocklist first
        if domain_in_list "$DOMAIN" "$BLOCKED_DOMAINS_FILE"; then
            deny "$DOMAIN" "Domain is on the blocklist (known data exfiltration target)"
        fi

        # 2. Check allowlist
        if ! domain_in_list "$DOMAIN" "$ALLOWED_DOMAINS_FILE"; then
            deny "$DOMAIN" "Domain is not on the approved allowlist"
        fi

        allow
        ;;

    *)
        # Not a network tool, allow
        allow
        ;;
esac
