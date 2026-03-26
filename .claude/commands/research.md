---
description: "Research a topic with overlap detection and structured output — /research <topic>"
---

# Research

Launch a research investigation on a topic, with a pre-flight check for existing work.

## Steps

### 1. Pre-flight: search for overlap

Before diving in, search the repository for existing work related to the topic:

- **Glob** for directories and markdown files whose names match keywords from the topic
- **Grep** for the topic keywords in README.md files and document titles across the repo
- Focus on research documents (markdown files with version history, bibliographies, or AI disclaimers) — not code or configuration

If no overlap is found, skip to step 3.

### 2. Present overlap and gate

If existing work is found, present it to the user:

- List each overlapping document with its path and a one-line summary
- Ask the user to choose:
  - **Include**: Build on existing work — read it and extend/update
  - **Exclude**: Acknowledge existing work but don't absorb its conclusions
  - **Stop**: Abort — don't start the research

### 3. Research

Investigate the topic thoroughly:

- **Search broadly first**: Use WebSearch for external context, Grep/Glob for codebase evidence, and any available MCP tools (Glean, Confluence, etc.) for internal sources
- **Read primary sources**: Don't rely on summaries — read the actual code, docs, or discussions
- **Structure checkpoint**: Before writing prose, produce a mental outline showing planned output files, sections, and cross-references
- **Self-consistency**: After every change to a definition, count, or term, grep all output files for the old wording and update

### 4. Output structure

Research output should include:

- **Summary** (1-3 paragraphs at top): Who should read this, why it matters, how to navigate
- **Main content**: Organized by type — reference (by concept), manual (by goal), troubleshooting (by symptom)
- **Sources section**: Annotated bibliography with quality/relevance/currency assessment for each source, ordered by relevance
- **Source Conflicts**: Cross-check claims across sources; state which source is authoritative and why
- **Errata section**: Initially empty — records corrections discovered later
- **Version History**: Dated entries tracking changes

### 5. Writing conventions

- **Active voice with named actors**: "Claude searched...", "The user identified..." — never passive for actions
- **Exact quotes over paraphrasing**: Use blockquotes from sources; AI rewording is unverifiable
- **Code links as permalinks**: Specific commit hash + line range, not branch names
- **First-mention linking**: Link terms to their definition on first use, especially in summaries
- **Absence claims**: "Claude did not find [X] in [sources examined]" — scope the limitation

### 6. Problem ranking (when identifying issues)

Rank problems by audience impact:
1. Regulators / legal / compliance
2. Customers / end users
3. Business leadership
4. Product teams
5. Developers

Problems that create legal or contractual risk rank above developer productivity issues.

### 7. Review

After completing the research:

- Run a self-check: scan every paragraph for domain terms without glossary entries or links
- Verify all code links resolve (no broken permalinks)
- Check that Sources section includes every reference used in the document
- If the output includes a glossary, verify definitions are testable and cross-linked

### 8. Ship

Use `/ship` to stage, commit, and push all research output.

### 9. Report

Summarize what was researched and shipped: files created, key findings, open questions.

## Important

- **Counterarguments**: For each finding, ask: What if we didn't do this? What if it happened differently? How do other ecosystems handle it?
- **Don't accept the framing**: AI research tends to accept the problem framing it's given. Push back on assumptions.
- If the research sprawls beyond scope, suggest splitting into multiple focused investigations.
