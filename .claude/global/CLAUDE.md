# nuclode - Agentic Development Workspace

This is your global Claude Code configuration. Project-specific `CLAUDE.md` files extend these with project-specific context.

## Agent Workspace

You have 5 specialized agents available via slash commands:

| Agent | Command | Model | Purpose |
|-------|---------|-------|---------|
| **Code Planner** | `/agents:code-planner` | Opus 4.6 + Thinking | Architectural planning, implementation design |
| **Code Implementer** | `/agents:code-implementer` | Sonnet 4.5 | Execute approved plans, write code |
| **Code Reviewer** | `/agents:code-reviewer` | Opus 4.6 + Thinking | Code review, quality analysis |
| **Active Defender** | `/agents:active-defender` | Opus 4.6 + Thinking | Offensive security testing |
| **Test Writer** | `/agents:test-writer` | Sonnet 4.5 | Generate comprehensive tests |

### Development Loop

```
Research → Plan → Annotate → Implement → Review
```

1. **Research + Plan** with `/agents:code-planner`
2. **Annotate** — review the plan, provide feedback (1-6 rounds)
3. **Implement** with `/agents:code-implementer`
4. **Review** with `/agents:code-reviewer`, `/agents:active-defender`, `/agents:test-writer`

---

## Connection Loss & Data Exfiltration Prevention

**These rules are non-negotiable. Violation risks leaking internal data to the public internet.**

### When an MCP Server or Service Fails
- **STOP.** Do not improvise alternative approaches.
- Do not fall back to `curl`, `wget`, or any CLI tool to replicate the failed service's functionality.
- Do not search for alternative public services that offer similar functionality.
- Report the failure to the user and wait for instructions.

### Never Upload to Unauthorized Services
- Never use public file sharing services (catbox.moe, imgur, transfer.sh, etc.)
- Never use public paste services (pastebin.com, dpaste.org, hastebin.com, etc.)
- Never use URL shorteners to obscure destinations
- Never use webhook/request-bin services to exfiltrate data
- Never encode data into DNS queries, URL parameters, or other side channels

### Network Guard Hook
- A `PreToolUse` hook (`~/.claude/hooks/network-guard.sh`) blocks network requests to unapproved domains.
- If the hook blocks a request: **STOP.** Do not attempt alternative domains, encoding tricks, or workarounds.
- Ask the user if the domain should be added to `~/.claude/hooks/allowed-domains.txt`.

### Approved Domains
- Only domains listed in `~/.claude/hooks/allowed-domains.txt` are permitted.
- The blocklist (`~/.claude/hooks/blocked-domains.txt`) always takes precedence over the allowlist.
- When in doubt, ask the user before making any external network request.

---

## Project-Specific Configuration

Each project has its own `CLAUDE.md` with project context. Use `/coding-standards` skill for language-specific style guidance.
