# Customization Guide

## Creating a New Layer

Layers extend the core workspace with company or team-specific configuration.

### Step 1: Create Layer Directory

```bash
mkdir -p layers/mycompany
```

### Step 2: Add CLAUDE.md (Optional)

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

### Step 3: Add settings.json (Optional)

Enable company-specific plugins:

```json
{
  "enabledPlugins": {
    "my-plugin@my-marketplace": true
  }
}
```

### Step 4: Add .mcp.json (Optional)

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

### Step 5: Add Agent Overrides (Optional)

Extend agent capabilities with company tools:

```bash
mkdir -p layers/mycompany/agents
```

Create `code-planner-overrides.json`:
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

### Step 6: Install

```bash
./setup.sh --layer mycompany
```

## Adding a New Agent

### Step 1: Create Agent Directory

```bash
mkdir -p core/agents/my-agent
```

### Step 2: Write agent.json

```json
{
  "name": "my-agent",
  "description": "What this agent does",
  "model": "claude-sonnet-4-5-20250929",
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

Create `core/commands/agents/my-agent.md`:

```markdown
---
description: What this agent does
model: claude-sonnet-4-5-20250929
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

Edit `core/CLAUDE.md` to modify standards that apply everywhere.

### Layer-Specific Standards

Add standards to `layers/mycompany/CLAUDE.md` - they'll be appended to the global standards.

### Project-Specific Standards

Create a `CLAUDE.md` in the project root - it's loaded alongside global and layer standards.

## Model Configuration

### Default Model

Set in `core/settings.json`:
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
