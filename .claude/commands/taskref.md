---
description: "Produce a task-specific reference from sources — /taskref <task> <sources>"
---

# Taskref

Produce a task-specific reference: a dense reference document covering only the parts of source material relevant to a specific task. The output is organized as reference (specifications, patterns, anti-patterns), not as a tutorial or step-by-step guide.

## Steps

### 1. Determine output directory

Create a directory under `taskrefs/` named after the task (kebab-case, e.g. `taskrefs/auth-middleware-setup/`).

### 2. Gather sources

Interpret the sources argument:

- **Explicit paths/URLs**: Read each directly.
- **Search criteria**: Use WebSearch and WebFetch to discover and retrieve relevant documentation pages. Follow links within official docs to find all task-relevant pages.

Use subagents to read sources in parallel when there are many, to manage context. Each subagent should extract only the parts relevant to the task.

### 3. Write source summaries

Write `{output-dir}/source-summaries.md` containing:

- For each source: a heading with the source title/URL, followed by a summary of the task-relevant content
- An **Annotated Bibliography** section listing each source with a one-line description of what it contributed

When in doubt about whether something is relevant, include it — a slightly larger reference is better than missing something needed.

### 4. Synthesize into task reference

Write `{output-dir}/{task}-ref.md` following the refify reference format:

```markdown
# {Task} Reference

Sources: [source-summaries.md](source-summaries.md)

## Rationale

{2-3 sentences: what task this covers, who needs it, what prerequisites exist}

## {Specification sections}

{Tables, code blocks, type signatures — not prose}

## {Pattern sections}

{Minimal code examples showing the RIGHT way, with expected results}

## Anti-patterns

{WRONG / RIGHT pairs for common mistakes}

## Source Disagreements

{Tensions, contradictions, or version-specific differences found across sources. Omit if none.}
```

Key principles from refify:
- Specifications as tables or code blocks, not prose
- One example per pattern, not three
- Anti-patterns as WRONG/RIGHT pairs — highest value per token
- 3-8K tokens per reference file; split by subtopic if larger
- Extract, don't embellish — no constraints not found in sources
- Source attribution required

### 5. Verify (when possible)

If the task involves a library or tool available in the current project, verify key patterns by running them. Note any corrections discovered during verification.

### 6. Report

- Source count and total tokens consumed
- Output file count, sizes
- Key patterns and anti-patterns extracted
- Any source disagreements found
