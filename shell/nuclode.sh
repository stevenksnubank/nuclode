#!/bin/bash
# nuclode.sh - Shell functions for agentic development workflow
# Add to your shell profile: source ~/dev/nuclode/shell/nuclode.sh
# (setup.sh will add this automatically)

# ─── Git Worktree + Claude Code ──────────────────────────────────────

# Create a worktree for the current branch and launch Claude in it
claude-worktree() {
  local repo_root=$(git rev-parse --show-toplevel)
  local repo_name=$(basename "$repo_root")
  local branch=$(git branch --show-current)
  local default_branch=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
  default_branch="${default_branch:-main}"
  local wt_dir="${repo_root}/../${repo_name}-wt/${branch}"

  if [ "$branch" = "$default_branch" ]; then
    echo "You're on $default_branch. Switch to a feature branch first."
    return 1
  fi

  if [ ! -d "$wt_dir" ]; then
    git checkout "$default_branch"
    git worktree add "$wt_dir" "$branch"
  fi

  cd "$wt_dir" && claude
}
alias cw=claude-worktree

# Remove all worktrees for the current repo (interactive)
remove-worktrees() {
  local repo_root=$(git rev-parse --show-toplevel)
  local repo_name=$(basename "$repo_root")
  local wt_base="${repo_root}/../${repo_name}-wt"

  if [ ! -d "$wt_base" ]; then
    echo "No worktree directory found at $wt_base"
    return 0
  fi

  for wt in "$wt_base"/*/; do
    [ -d "$wt" ] || continue
    local wt_name=$(basename "$wt")

    if git -C "$wt" diff --quiet 2>/dev/null && git -C "$wt" diff --cached --quiet 2>/dev/null; then
      echo "Removing worktree: $wt_name"
      git worktree remove "$wt"
    else
      echo "Worktree '$wt_name' has uncommitted changes."
      read -q "REPLY?  Force remove? [y/N] "
      echo
      if [[ "$REPLY" =~ ^[Yy]$ ]]; then
        git worktree remove "$wt" --force
      else
        echo "  Skipped."
      fi
    fi
  done

  rmdir "$wt_base" 2>/dev/null
  echo "Done."
}
