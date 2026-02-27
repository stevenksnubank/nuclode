# Customization Guide

## Overview

nuclode is designed as a core framework that you extend with plugins from the [ai-agents-plugins marketplace](https://github.com/nubank/ai-agents-plugins). The customization story is:

1. **Install nuclode** for the core workspace framework
2. **Extend with plugins** from the marketplace
3. **Create your own plugins** to share with your team or company

## Using Marketplace Plugins

### Browse Available Plugins

Visit the [ai-agents-plugins marketplace](https://github.com/nubank/ai-agents-plugins) to see available plugins. Each plugin can provide:

- **CLAUDE.md** - Company/team-specific coding standards
- **settings.json** - Plugin enablement and configuration
- **.mcp.json** - Additional MCP servers
- **Agent overrides** - Extended agent capabilities

### Install a Plugin

```bash
./setup.sh --plugin <plugin-name>
```

The installer deep-merges plugin configuration into your workspace, combining settings, MCP servers, and agent capabilities additively.

## Creating Your Own Plugin

For the full guide on creating and publishing plugins, see the [Contributing Guide](https://github.com/nubank/ai-agents-plugins/blob/main/CONTRIBUTING.md).

### Plugin Structure

A plugin follows this structure:

```
my-plugin/
├── CLAUDE.md           # Additional coding standards (appended to workspace)
├── settings.json       # Plugin settings (deep-merged)
├── .mcp.json           # Additional MCP servers (combined)
└── agents/             # Agent overrides
    └── code-planner-overrides.json
```

### Example: CLAUDE.md

Company-specific coding standards, tool references, or workflow instructions:

```markdown
# MyCompany Extensions

## Internal Tools
- Use `tool-x` for deployment
- Check `internal-wiki` for architecture docs

## Additional Standards
- All PRs require security review
- Use MyCompany logging library
```

### Example: settings.json

Enable company-specific plugins:

```json
{
  "enabledPlugins": {
    "my-plugin@my-marketplace": true
  }
}
```

### Example: .mcp.json

Add company-specific MCP servers:

```json
{
  "mcpServers": {
    "my-tool": {
      "command": "my-mcp-server",
      "args": ["--config", "/path/to/config"]
    }
  }
}
```

### Example: Agent Overrides

Extend agent capabilities with company tools by creating `<agent-name>-overrides.json`:

```json
{
  "additional_tools": [
    "mcp__my-tool__search"
  ],
  "additional_mcp_servers": [
    "my-tool"
  ]
}
```

## Adding a New Agent

### Step 1: Create Agent Directory

```bash
mkdir -p workspace/agents/my-agent
```

### Step 2: Write agent.json

```json
{
  "name": "my-agent",
  "description": "What this agent does",
  "model": "claude-sonnet-4-6",
  "extended_thinking": false,
  "capabilities": ["my_capability"],
  "tools": ["Read", "Grep", "Glob"],
  "mcp_servers": ["ide"],
  "project_context": true,
  "max_iterations": 10
}
```

### Step 3: Write system_prompt.md

```markdown
# My Agent

You are [role description].

## Workflow
1. Step one
2. Step two

## Guidelines
- Guideline 1
- Guideline 2
```

### Step 4: Create Slash Command

Create `workspace/commands/agents/my-agent.md`:

```markdown
---
description: What this agent does
model: claude-sonnet-4-6
allowed-tools: Read, Grep, Glob
argument-hint: [what to provide]
---

# My Agent

[Instructions that reference $ARGUMENTS]

## Your Task

$ARGUMENTS
```

## Modifying Coding Standards

### Global Changes

Edit `workspace/CLAUDE.md` to modify standards that apply everywhere.

### Plugin-Specific Standards

Add standards to your plugin's `CLAUDE.md` -- they'll be appended to the global standards when the plugin is installed.

### Project-Specific Standards

Create a `CLAUDE.md` in the project root -- it's loaded alongside global and plugin standards.

## Model Configuration

### Default Model

Set in `workspace/settings.json`:
```json
{"model": "opus"}
```

### Per-Agent Models

Set in each agent's `agent.json` and corresponding command `.md` frontmatter.

### Model Strategy

| Use Case | Recommended Model |
|----------|-------------------|
| Planning & Review | Opus + Thinking |
| Implementation | Sonnet |
| Security Analysis | Opus + Thinking |
| Test Generation | Sonnet |
| Quick Tasks | Haiku |
