# Network Guard Security Notes

## Coverage

The network guard hook (`network-guard.sh`) intercepts the following Claude Code tools:

| Tool | Coverage | Notes |
|------|----------|-------|
| **Bash** | Full | Scans commands for network tools (curl, wget, etc.) and validates destination domains |
| **WebFetch** | Full | Validates the target URL domain against allow/block lists |
| **WebSearch** | Partial | Checks for blocked domains in search queries; search results themselves are not filtered |

## Known Limitations

### MCP Tools Are Not Covered

MCP (Model Context Protocol) server tools that make HTTP requests directly (e.g., `mcp__*` tools) are **not intercepted** by the network guard. This is because:

1. MCP tools execute in their own process/server and don't go through the Bash or WebFetch code paths
2. The Claude Code hook system currently only supports matching on tool names, not on the underlying network calls
3. Adding a wildcard matcher (`*`) would require the hook to handle all tool types, adding latency to every tool call

### Mitigation Strategies

For environments requiring comprehensive network protection:

1. **OS-level firewall rules**: Use `iptables`, `pf`, or similar to restrict outbound connections at the OS level
2. **HTTP proxy**: Route all traffic through a proxy that enforces domain allowlists
3. **Network namespace isolation**: Run Claude Code sessions in a restricted network namespace
4. **MCP server auditing**: Review MCP server configurations to ensure they only connect to approved endpoints

### Tool-Specific Gaps

- **WebSearch**: Search queries are checked for blocked domains, but the search engine's response (which may contain links to any domain) is not filtered. This is a read-only risk (information gathering, not exfiltration).
- **Future tools**: Any new tools added to Claude Code that make network requests will need to be added to the matcher in `settings.json`.

## Configuration

- **Allowlist**: `allowed-domains.txt` - domains that are explicitly permitted
- **Blocklist**: `blocked-domains.txt` - domains that are always denied (checked first, overrides allowlist)
- **Default policy**: Deny (fail-secure) - any domain not in the allowlist is blocked

## Maintenance

When adding new tools or MCP servers to your Claude Code configuration:

1. Check if the tool makes network requests
2. If yes, add its name to the matcher in `settings.json`
3. Add a corresponding case in `network-guard.sh` to handle its specific input format
4. Test with both allowed and blocked domains
