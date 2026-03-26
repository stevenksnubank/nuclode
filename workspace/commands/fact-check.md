---
description: "Extract and verify claims from a document — /fact-check <path> <section|all>"
---

# Fact Check

Extract atomic claims from a section of a research document and verify each against primary sources (code, docs, web).

## Steps

1. **Read the document** and locate the target section. If the section is not found, list available headings and ask the user to pick one.

2. **Extract atomic claims**: Break the section into individual, testable claims. Each claim should be a single assertion that can be independently verified. Skip:
   - Hedged statements that already acknowledge uncertainty
   - Definitions (conventions, not claims)
   - Recommendations (opinions, not facts)

3. **Classify each claim** by verification method:
   - **Code claims**: Assertions about what code does, where it lives, how it's structured. Verify with Glob, Grep, and Read tools.
   - **Organizational claims**: Assertions about team practices, decisions, or history. Verify with available search tools (Glean, Confluence, web search).
   - **Quantitative claims**: Counts, percentages, metrics. Verify by reproducing the count from primary sources.
   - **Temporal claims**: Present-tense assertions about current state (e.g., "the service handles 10K req/s", "the default deletes after 30 days"). Verify that each is qualified with a date or version. If not, flag as **needs time qualifier** — unqualified observations decay silently into falsehoods.

4. **Verify claims in parallel** where possible:
   - For code claims: search the codebase for confirming or contradicting evidence.
   - For organizational claims: use available search tools to find confirming or contradicting evidence.
   - For quantitative claims: attempt to reproduce the number from primary sources.

5. **Report findings**: For each claim, report:
   - The claim text
   - Verdict: **Confirmed**, **Contradicted**, **Unverifiable**, or **Partially confirmed**
   - Evidence: what you found that supports or contradicts the claim, with links
   - If contradicted: what the correct statement should be
