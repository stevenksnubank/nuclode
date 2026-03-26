# /watch — Launch live agent dashboard

Opens nuclode-watch in a new iTerm2 split pane. Shows per-agent activity,
current tool, skill invocations, and recent hook events in real-time.

Run this command by executing the following bash command:

```bash
osascript <<'EOF'
tell application "iTerm2"
  tell current window
    tell current session
      split horizontally with default profile command "python3 ~/.claude/hooks/nuclode_watch.py"
    end tell
  end tell
end tell
EOF
```

If iTerm2 is not available, fall back to opening a new Terminal window:

```bash
open -a Terminal && osascript -e 'tell application "Terminal" to do script "python3 ~/.claude/hooks/nuclode_watch.py"'
```

The watcher updates every 0.5 seconds. Press Ctrl+C in the watcher pane to exit.
