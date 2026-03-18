---
description: View nuclode hook telemetry — security events, blocks, and session metrics
---

# Telemetry

Display nuclode's hook execution telemetry from `~/.claude/metrics/`.

When invoked:

## 1. Security Events

Read `~/.claude/metrics/hooks.jsonl` and summarize:
- **Blocks**: How many times secrets_scan, sast_gate, or network-guard blocked an action
- **Warnings**: How many sast_scan, console_warn, quality_gate findings
- Group by: hook name, event type (block/warn/pass), and date

Example output:
```
Security events (last 7 days):
  secrets_scan:  2 blocks, 15 passes
  sast_gate:     1 block, 12 passes
  sast_scan:     8 warnings
  console_warn:  3 warnings
  network_guard: 0 blocks
```

## 2. Session History

Read `~/.claude/sessions/history.jsonl` and show:
- Total sessions, grouped by project (cwd)
- Average session size (transcript_bytes)
- Most recent 5 sessions with timestamp, branch, summary

## 3. Cost Metrics

Read `~/.claude/metrics/costs.jsonl` and show:
- Total transcript bytes by day/week
- Average session size
- Largest sessions

## 4. Hook Performance

If duration_ms is logged in hooks.jsonl:
- Average hook execution time
- Slowest hooks
- Any hooks that timed out

## Format

Present as a clean table or summary. Don't dump raw JSON — make it readable for a platform team member reviewing developer usage.
