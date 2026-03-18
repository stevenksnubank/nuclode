---
description: Fast path for small changes — plan and implement in one step
---

# Quick Code

For small, well-defined changes (1-2 files, clear scope). Combines planning and implementation without the full annotation cycle.

## When invoked:

1. **Assess scope**: Read the relevant code to understand what's being changed. If the change touches more than 3 files or involves architectural decisions, tell the user: "This is bigger than a quick fix — let me use `/agents:code-planner` to design it properly."

2. **Brief plan** (2-3 sentences): State what you'll change and why. Don't produce a full plan document. Example: "I'll add null checking to the `getUser` handler and update the test to cover the empty-ID case."

3. **Implement**: Make the changes.

4. **Verify**:
   - Run existing tests if they exist
   - Check for lint errors
   - If the change is security-relevant (auth, input validation, data handling), flag it: "This touches security-sensitive code. Consider running `/agents:active-defender` to verify."

5. **Show result**: Present the diff and ask if it looks right.

## Scope guard

If at any point you realize the change is larger than expected:
- Stop implementing
- Tell the user what you discovered
- Recommend switching to the full workflow: "This is more involved than it looked — want me to run `/agents:code-planner` to design it properly?"

## Do NOT:
- Produce a multi-page plan document
- Require explicit "approval" before implementing
- Skip running tests if they exist
- Ignore security implications of the change
