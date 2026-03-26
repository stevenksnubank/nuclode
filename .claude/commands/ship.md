---
description: Stage, commit, and push changes in a single gesture
---

# Ship

Stage all current changes, create a well-formed commit, and push. One command to go from working tree to remote.

## Steps

1. **Find changes**: Run `git status` (never use `-uall`) and `git diff` (both staged and unstaged) to understand what changed. Also run `git log --oneline -5` to match the repository's commit message style. Find the conversation ID for the commit trailer:
   ```
   PROJ_DIR="$HOME/.claude/projects/$(echo "$PWD" | tr '/.' '-')"
   SESSION_ID=$(basename "$(ls -t "$PROJ_DIR"/*.jsonl 2>/dev/null | head -1)" .jsonl 2>/dev/null)
   ```

2. **Stage changes**: Stage modified and new files relevant to the current work. Use `git add -u` by default to avoid accidentally staging untracked files that aren't part of the work. If there are new files that are clearly part of the work (e.g., files just created in this session), stage those explicitly by name. Never stage `.env`, credentials, or other sensitive files.

3. **Draft commit message**: Summarize the nature of the changes in 1-2 concise sentences focused on the "why" rather than the "what." End the message with the co-author trailer.

4. **Commit**: Create the commit. Include the conversation ID as a `Session:` trailer. Use a HEREDOC for the message:
   Use a HEREDOC for the message, including a `Session:` trailer with the conversation ID and a `Co-Authored-By:` trailer with the current Claude model name. The HEREDOC must NOT use single quotes around EOF so that `$SESSION_ID` is expanded.

5. **Push**: Run `git push` to send the commit to the remote. If the branch has no upstream, use `git push -u origin HEAD`.

6. **Report**: Show the commit hash and a one-line summary of what was committed.

7. **Nudge (occasionally)**: If there were already 3+ unpushed commits before this one (check with `git log --oneline @{u}..HEAD 2>/dev/null | wc -l`), mention the count. Skip this if the upstream is not set.

## Important

- If there are no changes to commit, say so and stop.
- If the commit fails (e.g., pre-commit hook), report the error — do not retry automatically.
- If the push fails, report the error and suggest the user resolve it manually.
