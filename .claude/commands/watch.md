# /watch — Launch live agent dashboard

Opens nuclode-watch in a new iTerm2 split pane. Shows per-agent activity,
current tool, skill invocations, and recent hook events in real-time.

Run this command by executing the following bash command:

```bash
osascript <<'EOF'
-- Activate iTerm2 (brings it to front, creates a window if none exists)
tell application "iTerm2"
  activate
  -- Use existing window or create a new one
  if (count of windows) = 0 then
    create window with default profile
  end if
  tell current window
    tell current session
      split horizontally with default profile command "python3 ~/.claude/hooks/nuclode_watch.py"
    end tell
  end tell
end tell
EOF
```

If the above fails (iTerm2 not installed), fall back to a new Terminal window:

```bash
osascript -e 'tell application "Terminal" to do script "python3 ~/.claude/hooks/nuclode_watch.py"'
```

The watcher updates every 0.5 seconds. Press Ctrl+C in the watcher pane to exit.
