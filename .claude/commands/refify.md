---
description: "Compile a document into dense AI-optimized reference format — /refify <source> [output]"
---

# Refify

Compile a source document into one or more dense reference files optimized for AI coding context. The reference format maximizes information density per token by extracting specifications, constraints, and anti-patterns while dropping narrative, motivation, and redundant examples.

## Steps

1. **Read the source document** in full. Note its size.

2. **Classify the source format**: reference (already dense), guide (step-by-step with rationale), tutorial (walkthrough with examples), FAQ (question-answer pairs), or narrative (discussion/opinion). References need little work; guides and tutorials have the most to compress.

3. **Identify distinct topics**. If the source covers multiple independent topics (e.g., layer dependencies AND error handling AND adapter patterns), plan separate reference files — one per topic. Each reference should be self-contained.

4. **For each reference file, extract**:

   a. **Rationale** (2-3 sentences): What problem does this technology/topic solve? Who is the audience? Why does it exist?

   b. **Specifications**: Function signatures, valid values, constraints, required formats, dependency rules. Present as tables or code blocks, not prose.

   c. **Patterns**: The "RIGHT way" to do things — minimal code examples showing signature and return value. One example per pattern, not three.

   d. **Anti-patterns**: Common mistakes as "WRONG" / "RIGHT" pairs. These are the highest-value-per-token content.

   e. **Organize into sections**: Start with Rationale, then topic-appropriate sections. Use tables for enumerations, code blocks for examples, bullet lists for constraints.

5. **Check size**: Each reference should be 3-8K tokens (~1.5-4K words). If a single reference exceeds ~8K tokens, split further by subtopic. If under 1K tokens, the topic may not warrant a standalone file — consider merging with a related reference.

6. **Write the compiled reference(s)**:
   - Title: `# {Topic} Reference`
   - Source line: link to the original document
   - Rationale section
   - Topic sections
   - Anti-pattern sections with WRONG/RIGHT code pairs

7. **Report results**:
   - Source: filename, size, format classification
   - Output: file count, filenames, sizes
   - Compression ratio (source tokens / total output tokens)
   - What was extracted (topics, pattern count, anti-pattern count)
   - What was dropped and why (narrative, redundant examples, WIP sections)

## Reference format model

```markdown
# {Topic} Reference

Source: {link to original}

## Rationale

{2-3 sentences: what, who, why}

## {Specification section}

| Column | Column |
|--------|--------|

## {Pattern section}

```language
// RIGHT
functionCall(arg1, arg2)
// => expected-result
```

## Anti-patterns

```language
// WRONG — {why it's wrong}
badPattern(...)

// RIGHT — {what to do instead}
goodPattern(...)
```
```

## Important

- Source attribution is required — every reference must link to its origin.
- Do not invent constraints not present in the source. Extract, don't embellish.
- When the source contains WIP or untranslated sections, note them as dropped in the report.
- If the source is already in reference format and under 8K tokens, say so and skip compilation.
