# Nuclode Audit Fixes — Plan

> **Source:** Deep audit of nuclode workspace conducted 2026-03-18 across hooks, agent prompts, config, installer, and tests.

**Goal:** Fix all bugs, security issues, and coverage gaps found during the audit. Organized by priority tier.

---

## Tier 1: Must Fix (Bugs that will cause errors)

### 1.1 Double-close fd crash in session_end.py

**File:** `workspace/hooks/session_end.py:100-113`

**Bug:** `_atomic_write` exception handler uses `os.get_inheritable(fd)` after `os.close(fd)` already succeeded. If an exception occurs after the close (e.g., `os.rename` fails), the except block tries to check an already-closed fd, raising `OSError` and masking the real error.

**Fix:** Replace the broken fd cleanup with safe close:
```python
except Exception:
    try:
        os.close(fd)
    except OSError:
        pass
    try:
        os.unlink(tmp)
    except OSError:
        pass
    raise
```

**Also apply to:** `cost_tracker.py` has the same `_trim_file` pattern (lines 48-68) but already uses the safer `try: os.close(fd) except OSError: pass` form. Verify both are consistent after fix.

### 1.2 ZeroDivisionError in suggest_compact.py

**File:** `workspace/hooks/suggest_compact.py:9`

**Bug:** If `NUCLODE_COMPACT_THRESHOLD=0`, line `count % threshold` raises `ZeroDivisionError`.

**Fix:** Add validation after parsing:
```python
threshold = int(os.environ.get("NUCLODE_COMPACT_THRESHOLD", "30"))
if threshold <= 0:
    threshold = 30
```

### 1.3 Regex catastrophic backtracking in console_warn.py

**File:** `workspace/hooks/console_warn.py:11`

**Bug:** Pattern `print\(.*debug)` uses greedy `.*` which causes exponential backtracking on lines with many parentheses.

**Fix:** Replace with bounded pattern:
```python
"py": r"(breakpoint\(\)|pdb\.set_trace|print\([^)]*debug)",
```

---

## Tier 2: Should Fix (Correctness & security)

### 2.1 Race condition in _trim_file

**Files:** `workspace/hooks/session_end.py:116-123`, `workspace/hooks/cost_tracker.py:48-68`

**Bug:** Concurrent sessions can both read a file, both decide to trim, and overwrite each other's entries. The read-then-write is not atomic.

**Fix:** Extract a shared `_atomic_io.py` utility (see 2.4) and use `fcntl.flock` for advisory file locking during trim:
```python
import fcntl

def _trim_file(path: Path, max_lines: int) -> None:
    try:
        with path.open("r+", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            lines = f.read().strip().splitlines()
            if len(lines) > max_lines:
                f.seek(0)
                f.write("\n".join(lines[-max_lines:]) + "\n")
                f.truncate()
            fcntl.flock(f, fcntl.LOCK_UN)
    except OSError:
        pass
```

### 2.2 Race condition in suggest_compact counter

**File:** `workspace/hooks/suggest_compact.py:24-32`

**Bug:** Same read-increment-write race between concurrent sessions using the same session_id.

**Fix:** Use `fcntl.flock` or `os.O_EXCL` for atomic counter updates. Since this is advisory (just a suggestion), the race is low-impact, but the fix is simple:
```python
with counter_file.open("a+", encoding="utf-8") as f:
    fcntl.flock(f, fcntl.LOCK_EX)
    f.seek(0)
    try:
        count = int(f.read().strip() or "0")
    except ValueError:
        count = 0
    count += 1
    f.seek(0)
    f.write(str(count))
    f.truncate()
    fcntl.flock(f, fcntl.LOCK_UN)
```

### 2.3 No symlink check in post_edit_format.py

**File:** `workspace/hooks/post_edit_format.py:8-15`

**Bug:** `Path(file_path).exists()` follows symlinks. A symlink to a sensitive file outside the project could be formatted by a subprocess.

**Fix:** Add resolve + symlink check:
```python
path = Path(file_path)
if not path.exists() or path.is_symlink():
    return None
```

### 2.4 Duplicate _atomic_write / _trim_file logic

**Files:** `workspace/hooks/session_end.py`, `workspace/hooks/cost_tracker.py`

**Problem:** Both files implement the same atomic write + trim logic independently.

**Fix:** Create `workspace/hooks/atomic_io.py` with shared functions:
```python
"""Shared atomic I/O utilities for hook modules."""

def atomic_write(path, content): ...
def trim_file(path, max_lines): ...
```

Update `session_end.py` and `cost_tracker.py` to import from `atomic_io`.

### 2.5 TypeScript check assumes cwd is project root

**File:** `workspace/hooks/quality_gate.py:36`

**Bug:** `Path("tsconfig.json").exists()` checks cwd, but the edited file might be in a different project or monorepo package.

**Fix:** Walk up from the file's directory to find tsconfig:
```python
if ext in ("ts", "tsx"):
    tsconfig_dir = _find_tsconfig(file_path)
    if tsconfig_dir:
        return _run_cmd(
            ["npx", "--no-install", "tsc", "--noEmit", "--pretty", "false"],
            prefix="tsc", filter_path=file_path, cwd=str(tsconfig_dir),
        )
```

---

## Tier 3: Test Coverage Gaps

### 3.1 Add tests for untested hooks

Add test classes to `tests/test_hooks.py` using `unittest.mock.patch` for subprocess calls (same pattern as existing TestUncommittedGuard and TestToolErrorFormat):

| Hook | Test cases needed |
|------|-------------------|
| `session_start.py` | Project detection (pyproject.toml, package.json, go.mod), beads task auto-inject (`bd current` + `bd show`), previous session loading, resume event skipped |
| `session_end.py` | Atomic write lifecycle, history append + trim, session data structure validation, beads_task_id capture |
| `post_edit_format.py` | Formatter selection by extension (.py→ruff, .go→gofmt, .ts→prettier/biome), JS formatter config detection, missing formatter graceful skip |
| `console_warn.py` | Debug pattern matching per language, Go `fmt.Println` NOT flagged, `log.Println` IS flagged, git diff preferred over file scan |
| `quality_gate.py` | Linter invocation by extension, file path filtering, timeout handling |
| `pre_compact.py` | Modified files capture via git diff, active beads task detection, checkpoint file written |
| `cost_tracker.py` | Entry format (session_id, timestamp, cwd, transcript_bytes), trim to 500 lines |
| `beads_sync.py` | Skips when no .beads/ dir, skips when bd not installed, skips when no dirty beads, calls bd sync when dirty |

**Estimated new tests:** ~30-40, bringing total from 20 to ~55.

---

## Tier 4: Prompt & Workflow Improvements

### 4.1 Generalize "Payment processing" in coverage requirements

**Files:** All 5 agent `system_prompt.md` files + `workspace/agents/includes/coding-standards.md`

**Change:** Replace "Payment processing" with "Critical business logic" in the 100% coverage requirements list.

### 4.2 Define annotation cycle termination criteria

**File:** `workspace/agents/code-planner/system_prompt.md`

**Add** after the annotation cycle description:
- Explicit approval signal: user says "approved", "LGTM", or "proceed"
- If user doesn't respond after presenting revised plan, ask once for confirmation
- Max 6 rounds — if not converging, summarize disagreements and ask user to decide

### 4.3 Define plan approval signal

**Files:** `workspace/agents/code-planner/system_prompt.md`, `workspace/agents/code-implementer/system_prompt.md`

**Add** to both: explicit list of approval signals (e.g., "approved", "proceed", "go ahead", "LGTM") and non-approval signals (questions, concerns, "let me think").

### 4.4 Add beads workflow commands to agent prompts

**Files:** All 5 agent `system_prompt.md` files

**Add** a brief beads workflow section to each agent specifying their responsibilities:
- **Planner:** Check `bd ready` at start, create tasks with `bd create` during planning
- **Implementer:** Claim with `bd update <id> --claim`, update status during work
- **Reviewer:** Reference task IDs in findings
- **All agents at session end:** Follow "landing the plane" workflow from AGENTS.md

### 4.5 Document beads token budget rationale

**Files:** Agent prompts with beads viewer sections

**Add** brief rationale comments:
- Tier 3 (3000 tokens): Planner and defender need full graph for dependency-aware planning and attack surface mapping
- Tier 2 (1500 tokens): Reviewer needs blast radius context but not full insights
- No beads: Implementer and test-writer work from plans, not graphs

---

## Execution Notes

- **Tier 1** can be done in a single commit (3 small bug fixes)
- **Tier 2** is best done as 2 commits: one for `atomic_io.py` extraction + race fixes, one for symlink + tsconfig fixes
- **Tier 3** is a single large commit (test file additions)
- **Tier 4** is a single commit (prompt updates) — run `scripts/check-standards-sync.sh` after to verify sync

**Dependencies:** Tier 2.4 (shared utility) should be done before Tier 2.1 (race fix) since the race fix uses the shared module.
