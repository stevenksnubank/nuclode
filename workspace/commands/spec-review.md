---
description: "Review a service spec for leakage, redundancy, and structural issues — /spec-review <path>"
---

# Spec Review

Review a service or feature spec for common structural problems: leakage (implementation details in the wrong layer), redundancy (duplicated information that will drift), missing elements, and formatting issues.

## Steps

1. **Read the spec** at the given path.

2. **Check each category** against the spec, citing specific line references:

   ### Leakage
   - Overview section leaking implementation details (endpoint paths, protocols, wire formats)
   - User stories expressing implementation strategies rather than user-observable needs
   - Functional requirements (FRs) without a connecting user story

   ### Redundancy
   - Goals section that restates FRs
   - Subsection headings that restate the FR below them
   - Persistence attributes that restate the field table
   - Test cases that re-enumerate FR-defined values instead of referencing the FR

   ### Missing
   - No success response FR
   - No platform-conformance FR
   - No implementer meta-instruction
   - Validation using SHOULD instead of MUST

   ### Structure
   - Sections out of order (Overview → User stories → Out of scope → FRs → Quality requirements)
   - Separate required/optional field sections instead of one consolidated table
   - Prose validation instead of per-field table
   - "Non-goals" instead of "Out of scope" naming

3. **Report findings** as a prioritized list:

   - **Priority 1 — Leakage**: Information that belongs in FRs appearing in overview, stories, or test requirements
   - **Priority 2 — Missing**: Required elements absent from the spec
   - **Priority 3 — Redundancy**: Duplicated information that will drift
   - **Priority 4 — Structure**: Naming and formatting improvements

   For each finding, state the category, the specific location in the spec (line number or section), and what the fix would be.

4. **Make straightforward fixes** directly — renaming "Non-goals" to "Out of scope", adding missing FR numbers, removing redundant subsection headings. For substantive changes (adding new FRs, rewriting user stories), list as recommendations.

5. **Ship** all changes with `/ship`.

## What counts as straightforward

A fix is straightforward when the correct content is unambiguous — a section rename, removing a heading that duplicates an FR line, or adding an FR cross-reference. Do not defer fixes just because they are numerous.
