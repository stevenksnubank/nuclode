---
description: "Run quality audits on a research document — /research-review <path>"
---

# Research Review

Review a research document for quality issues by running multiple audits and synthesizing a prioritized report.

## Steps

1. **Validate input**: Confirm the file exists and is a markdown file.

2. **Run audits** (in parallel where possible):

   a. **Claims audit**: Scan the document for untestable or unmeasurable claims:
      - Unverifiable absolutes ("No documentation exists")
      - Mind-reading ("The team didn't understand...")
      - Unquantified comparisons ("Significantly more complex")
      - Causation without evidence
      - Absence claims without scope
      - Disguised opinions ("The code is unreadable")
      - Missing or misleading units
      - Agentless assertions (passive voice hiding who did what)

   b. **Link audit**: Check link quality:
      - Imprecise code links (branch names instead of commit hashes)
      - Unlinked first mentions of terms
      - Unlinked table cells (named entities without links to canonical locations)
      - Raw URLs as display text
      - Line numbers or full paths in display text

   c. **Version history check**: Does it have a Version History table with an entry for today?

   d. **Errata check**: Does it have an Errata section? If so, do entries follow the format: what was wrong, the correction, and why the error occurred?

   e. **Bibliography check**: Does it have an annotated Sources/Bibliography section?
      - Every source used in the document appears in the bibliography
      - Each entry describes the source and assesses relevance and quality
      - Known gaps are explicit (sources not accessed and why)
      - Source names are linked to canonical locations

3. **Synthesize report** with findings prioritized:

   - **Priority 1 — Factual concerns**: Untestable claims, mind-reading, causation without evidence
   - **Priority 2 — Navigation concerns**: Imprecise links, unlinked first mentions, unlinked table cells
   - **Priority 3 — Source concerns**: Missing/incomplete bibliography, missing source entries
   - **Priority 4 — Process concerns**: Missing/outdated version history, missing errata

4. **Make straightforward fixes** directly — renaming, adding cross-references, fixing link text. For substantive changes (rewriting claims, adding new sources), list as recommendations.

5. **Create review file** for non-trivial findings: `{basename}_review_run_{n}.md` for human review later.

6. **Ship** all changes with `/ship`.

## What counts as straightforward

A fix is straightforward when the correct content is known — the URL exists elsewhere in the document, the term has a glossary entry, or the correction directly follows from another section. Do not defer fixes just because they are numerous.
