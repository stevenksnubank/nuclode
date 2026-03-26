---
description: "Create or update a structured issue report — /issue <title>, /issue update <file>, /issue analyze <file>"
---

# Issue

Create, update, or analyze a structured issue report. Issue reports have two distinct phases:

1. **Observation** (create/update): Record what was seen — exact outputs, screenshots, timestamps, contrasts between expected and actual. No interpretation.
2. **Analysis** (analyze): Establish the custody chain, then reason from observations about where it broke. No extrapolation beyond the evidence.

## Steps

### 1. Determine mode

Parse the argument:

- If it starts with `analyze `, extract the filename and enter **analyze mode**
- If it starts with `update `, extract the filename and enter **update mode**
- Otherwise, treat the entire argument as a title and enter **create mode**

### 2a. Create mode

1. **Generate slug**: Convert the title to a kebab-case filename slug (lowercase, spaces/punctuation to hyphens, strip articles). Example: "Auth middleware drops session tokens" → `auth-middleware-session-tokens.md`

2. **Create the issue file** at `issues/{slug}` using this structure:

   ```markdown
   # Issue: {Title}

   ## Summary
   One sentence: what was observed and where.

   ## Observations
   Exact evidence, each item numbered. Include:
   - Exact tool output, API responses, or error messages (in code blocks)
   - Screenshots or links to screenshots
   - Timestamps and who observed it
   - The expected result contrasted with the actual result
   - Commit hashes, URLs, or other locators so the reader can reproduce

   ## Analysis
   _Not yet performed. Run `/issue analyze {slug}` after observations are complete._

   ## Version History
   | Date | Change |
   |------|--------|
   | {today} | Initial observations |
   ```

   Populate the Observations section from the current conversation context. Include **only concrete evidence** — exact outputs, exact quotes, exact contrasts. Do not interpret, hypothesize, or assess severity.

3. **Report**: Show the filename created.

### 2b. Update mode

1. **Read the existing issue** at `issues/{filename}` (add `.md` if not present).
2. **Add observations**: Append new numbered items to the Observations section. Same rules: only concrete evidence, no interpretation.
3. **Update Version History**: Add a dated row describing what observations were added.
4. **Report**: Show what was added.

### 2c. Analyze mode

1. **Read the existing issue** at `issues/{filename}` (add `.md` if not present).

2. **Check precondition**: The Observations section must contain at least one concrete piece of evidence. If empty, tell the user to add observations first.

3. **Write the Analysis section**, replacing the placeholder. Begin with a **short summary** (2-3 sentences) stating what the evidence supports. Then provide:

   #### Part 1: Custody chain

   Establish the sequence of systems and actors that touched the data from origin to the unexpected behavior. Each step is a handoff where one system produces output that becomes the next system's input.

   > Example: User submits form → API validates input → Service processes request → Database persists → Cache invalidates → Client receives response

   The custody chain is **descriptive, not diagnostic** — it says what systems are involved, not what went wrong.

   #### Part 2: Mapping observations to links

   For each observation, state which link(s) in the custody chain it constrains:

   > **Observation N** → **Link X → Y**: what this observation tells us about this handoff.

   Each mapping must state only what the observation **rules in** or **rules out**.

   #### Part 3: What remains

   - Which links have **no observations** constraining them? These are the gaps.
   - What specific additional evidence would constrain the uncovered links? Be concrete.

   #### Part 4: Reproduction

   Clear, concise steps to reproduce the issue. Exact commands, queries, or tool invocations — not descriptions.

   **Rules for all four parts**:
   - Reference specific observation numbers
   - **Never extrapolate**: do not invent mechanisms, rank likelihoods, or cite training-data knowledge as evidence
   - Distinguish between "the evidence shows X" and "the evidence is consistent with X but does not confirm it"
   - If you want to mention a possibility not established by evidence, frame it as "the observations do not rule out [X]"

4. **Update Version History**: Add a dated row.
5. **Report**: Show what was analyzed.

## Writing quality

- **Active voice with named actors**: "Claude searched for...", "The user noticed that..." — never passive voice for actions.
- **Absence claims**: "Claude did not find [X] in [sources examined]" — scope the limitation.
- **No severity ratings in create/update mode.** Severity is analytical judgment; it belongs in the Analysis section.

## Important

- Issue reports are for **specific, concrete problems** — not broad topics. If the investigation sprawls, suggest converting to a research project.
- The Observations section is the foundation. A good observation is an exact quote, a screenshot, a diff, or a tool output — not a description of what happened.
- **Screenshots and images**: Copy evidence images into `issues/images/` with descriptive filenames. Inline them using `![alt text](images/filename.png)`.
