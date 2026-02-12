# Nubank Extensions

## Nubank Naming Conventions

Follow Nubank naming patterns: embed relevant terms creatively (e.g., "nu" prefix, hidden tech terms like sellma→LLM, nullm→null+LLM).

## Clojure Development

### Clojure MCP Tools
For Clojure projects, use specialized MCP tools:
- `mcp__clojure__clojure_inspect_project` - Project structure, deps.edn, namespaces
- `mcp__clojure__read_file` - Collapsed view shows function signatures
- `mcp__clojure__grep` / `mcp__clojure__glob_files` - Search Clojure files
- `mcp__clojure__clojure_eval` - REPL evaluation
- `mcp__clojure__clojure_edit` - Structural editing

## Internal Tools

### Glean Enterprise Search
Use Glean MCP tools for internal documentation, policies, and knowledge:
- `mcp__glean_default__search` - Search internal docs
- `mcp__glean_default__chat` - AI-powered analysis of company knowledge
- `mcp__glean_default__read_document` - Full document content retrieval

### Factorio Recipes
Use Nu MCP tools for Factorio recipe management:
- `mcp__nu-mcp__list-recipes` - List available recipes
- `mcp__nu-mcp__invoke-recipe` - Execute recipes
- `mcp__nu-mcp__service-routes` - Get service endpoints

## Terminal Layout (Cursor)
```
Open all 5 agent terminals as split panes:
$ claude-agents

┌─────────────────┬─────────────────┬─────────────────┐
│ code-planner    │ implementer     │ reviewer         │
│     (Blue)      │    (Green)      │    (Yellow)      │
├─────────────────┴────────┬────────┴─────────────────┤
│ active-defender           │ test-writer              │
│       (Red)              │      (Magenta)           │
└──────────────────────────┴──────────────────────────┘
```

## Fintech Security Standards

### Payment Processing
- 100% test coverage required for all payment paths
- PII must never appear in logs
- All financial calculations use Decimal types (never float)
- Audit trails required for all state transitions

### Compliance
- Data residency requirements per jurisdiction
- LGPD/GDPR compliance for personal data handling
- PCI DSS for card data
