"""tests/test_hooks.py - Test suite for hook infrastructure and critical hook logic."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


# ─── Runner Tests ────────────────────────────────────────────────────────

class TestRunnerProfileMatching:
    """Test that the runner correctly filters by profile and disabled hooks."""

    def test_hook_skipped_when_profile_mismatch(self, tmp_path):
        """Hook should not fire when current profile is not in allowed profiles."""
        hook = tmp_path / "test_hook.py"
        hook.write_text('def run(input):\n    return {"fired": True}\n')
        runner = _get_runner_path()
        result = subprocess.run(
            ["python3", runner, "test:hook", "test_hook", "strict"],
            input="{}",
            capture_output=True, text=True,
            env={**os.environ, "NUCLODE_HOOK_PROFILE": "minimal"},
            cwd=str(tmp_path),
        )
        assert result.stdout == ""
        assert result.returncode == 0

    def test_hook_fires_when_profile_matches(self, tmp_path):
        hook = tmp_path / "test_hook.py"
        hook.write_text('def run(input):\n    return {"fired": True}\n')
        # Symlink runner to tmp_path so importlib finds the module
        runner_src = _get_runner_path()
        runner_link = tmp_path / "run_with_profile.py"
        runner_link.symlink_to(runner_src)
        result = subprocess.run(
            ["python3", str(runner_link), "test:hook", "test_hook", "standard,strict"],
            input="{}",
            capture_output=True, text=True,
            env={**os.environ, "NUCLODE_HOOK_PROFILE": "standard"},
        )
        assert result.returncode == 0
        assert "fired" in result.stdout

    def test_hook_skipped_when_disabled(self, tmp_path):
        hook = tmp_path / "test_hook.py"
        hook.write_text('def run(input):\n    return {"fired": True}\n')
        runner = _get_runner_path()
        result = subprocess.run(
            ["python3", runner, "test:hook", "test_hook", "standard"],
            input="{}",
            capture_output=True, text=True,
            env={**os.environ, "NUCLODE_HOOK_PROFILE": "standard", "NUCLODE_DISABLED_HOOKS": "test:hook"},
            cwd=str(tmp_path),
        )
        assert result.stdout == ""
        assert result.returncode == 0


class TestRunnerModuleLoading:
    """Test importlib edge cases."""

    def test_missing_module_exits_clean(self, tmp_path):
        runner = _get_runner_path()
        result = subprocess.run(
            ["python3", runner, "test:hook", "nonexistent", "standard"],
            input="{}",
            capture_output=True, text=True,
            env={**os.environ, "NUCLODE_HOOK_PROFILE": "standard"},
            cwd=str(tmp_path),
        )
        assert result.returncode == 0
        assert "not found" in result.stderr

    def test_module_without_run_exits_clean(self, tmp_path):
        hook = tmp_path / "no_run.py"
        hook.write_text("x = 1\n")
        runner_link = tmp_path / "run_with_profile.py"
        runner_link.symlink_to(_get_runner_path())
        result = subprocess.run(
            ["python3", str(runner_link), "test:hook", "no_run", "standard"],
            input="{}",
            capture_output=True, text=True,
            env={**os.environ, "NUCLODE_HOOK_PROFILE": "standard"},
        )
        assert result.returncode == 0
        assert "no callable run" in result.stderr

    def test_syntax_error_in_module_exits_clean(self, tmp_path):
        hook = tmp_path / "bad_syntax.py"
        hook.write_text("def run(input) this is broken\n")
        runner_link = tmp_path / "run_with_profile.py"
        runner_link.symlink_to(_get_runner_path())
        result = subprocess.run(
            ["python3", str(runner_link), "test:hook", "bad_syntax", "standard"],
            input="{}",
            capture_output=True, text=True,
            env={**os.environ, "NUCLODE_HOOK_PROFILE": "standard"},
        )
        assert result.returncode == 0  # Never blocks Claude


class TestRunnerJsonHandling:
    """Test stdin JSON parsing."""

    def test_empty_stdin_treated_as_empty_dict(self, tmp_path):
        hook = tmp_path / "echo_hook.py"
        hook.write_text('import json\ndef run(input):\n    return {"keys": list(input.keys())}\n')
        runner_link = tmp_path / "run_with_profile.py"
        runner_link.symlink_to(_get_runner_path())
        result = subprocess.run(
            ["python3", str(runner_link), "test:hook", "echo_hook", "standard"],
            input="",
            capture_output=True, text=True,
            env={**os.environ, "NUCLODE_HOOK_PROFILE": "standard"},
        )
        assert result.returncode == 0
        assert json.loads(result.stdout)["keys"] == []

    def test_malformed_json_logs_warning(self, tmp_path):
        hook = tmp_path / "echo_hook.py"
        hook.write_text('def run(input):\n    return None\n')
        runner_link = tmp_path / "run_with_profile.py"
        runner_link.symlink_to(_get_runner_path())
        result = subprocess.run(
            ["python3", str(runner_link), "test:hook", "echo_hook", "standard"],
            input="not json",
            capture_output=True, text=True,
            env={**os.environ, "NUCLODE_HOOK_PROFILE": "standard"},
        )
        assert result.returncode == 0
        assert "invalid JSON" in result.stderr


# ─── Trim Logic Tests ────────────────────────────────────────────────────

class TestTrimFile:
    """Test the _trim_file utility used by session_end and cost_tracker."""

    def test_trim_keeps_last_n_lines(self, tmp_path):
        f = tmp_path / "test.jsonl"
        f.write_text("\n".join(f"line{i}" for i in range(100)) + "\n", encoding="utf-8")
        # Import trim logic
        from importlib.util import spec_from_file_location, module_from_spec
        spec = spec_from_file_location("session_end", str(Path(__file__).parent.parent / "workspace/hooks/session_end.py"))
        if spec and spec.loader:
            mod = module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod._trim_file(f, max_lines=50)
            lines = f.read_text(encoding="utf-8").strip().splitlines()
            assert len(lines) == 50
            assert lines[0] == "line50"

    def test_trim_no_op_under_limit(self, tmp_path):
        f = tmp_path / "test.jsonl"
        f.write_text("line1\nline2\n", encoding="utf-8")
        from importlib.util import spec_from_file_location, module_from_spec
        spec = spec_from_file_location("session_end", str(Path(__file__).parent.parent / "workspace/hooks/session_end.py"))
        if spec and spec.loader:
            mod = module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod._trim_file(f, max_lines=50)
            assert f.read_text(encoding="utf-8").strip().splitlines() == ["line1", "line2"]


def _load_hook_module(name: str):
    """Load a hook module from the workspace by name."""
    from importlib.util import spec_from_file_location, module_from_spec
    hook_path = Path(__file__).parent.parent / "workspace" / "hooks" / f"{name}.py"
    spec = spec_from_file_location(name, str(hook_path))
    if spec and spec.loader:
        mod = module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    return None


# ─── Uncommitted Guard Tests ─────────────────────────────────────────────

class TestUncommittedGuard:
    """Test the uncommitted_guard Stop hook."""

    def test_clean_repo_returns_none(self):
        mod = _load_hook_module("uncommitted_guard")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            assert mod.run({}) is None

    def test_dirty_repo_returns_warning(self):
        mod = _load_hook_module("uncommitted_guard")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout=" M file.py\n?? new.txt\n", stderr=""
            )
            result = mod.run({})
            assert result is not None
            assert "unsaved change" in result["systemMessage"]
            assert "2 unsaved" in result["systemMessage"]

    def test_git_failure_returns_none(self):
        mod = _load_hook_module("uncommitted_guard")
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert mod.run({}) is None

    def test_many_files_truncated(self):
        mod = _load_hook_module("uncommitted_guard")
        files = "\n".join(f" M file{i}.py" for i in range(20))
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout=files, stderr=""
            )
            result = mod.run({})
            assert "and 10 more" in result["systemMessage"] or "unsaved" in result["systemMessage"]


# ─── Tool Error Format Tests ─────────────────────────────────────────────

class TestToolErrorFormat:
    """Test the tool_error_format PostToolUseFailure hook."""

    def test_permission_denied_bash_suggestion(self):
        mod = _load_hook_module("tool_error_format")
        result = mod.run({"tool_name": "Bash", "error": "Permission denied", "tool_input": {}})
        assert "permission" in result["hookSpecificOutput"]["additionalContext"].lower()

    def test_command_not_found_suggestion(self):
        mod = _load_hook_module("tool_error_format")
        result = mod.run({"tool_name": "Bash", "error": "command not found: foo", "tool_input": {}})
        assert "installed" in result["hookSpecificOutput"]["additionalContext"].lower()

    def test_edit_old_string_not_found(self):
        mod = _load_hook_module("tool_error_format")
        result = mod.run({"tool_name": "Edit", "error": "old_string not found in file", "tool_input": {}})
        assert "Read the file" in result["hookSpecificOutput"]["additionalContext"]

    def test_unknown_tool_default_suggestion(self):
        mod = _load_hook_module("tool_error_format")
        result = mod.run({"tool_name": "CustomTool", "error": "something broke", "tool_input": {}})
        assert "retry" in result["hookSpecificOutput"]["additionalContext"].lower()

    def test_empty_error_returns_none(self):
        mod = _load_hook_module("tool_error_format")
        assert mod.run({"tool_name": "Bash", "error": "", "tool_input": {}}) is None

    def test_long_error_truncated(self):
        mod = _load_hook_module("tool_error_format")
        long_error = "x" * 500
        result = mod.run({"tool_name": "Bash", "error": long_error, "tool_input": {}})
        # Summary should be truncated to 200 chars
        context = result["hookSpecificOutput"]["additionalContext"]
        assert len(context) < 500


# ─── Secrets Scan Tests ────────────────────────────────────────────────

class TestSecretsScan:
    """Test the secrets_scan PreToolUse BLOCKING hook."""

    def test_non_commit_command_ignored(self):
        mod = _load_hook_module("secrets_scan")
        result = mod.run({"tool_name": "Bash", "tool_input": {"command": "ls -la"}})
        assert result is None

    def test_non_bash_tool_ignored(self):
        mod = _load_hook_module("secrets_scan")
        result = mod.run({"tool_name": "Edit", "tool_input": {"command": "git commit"}})
        assert result is None

    def test_blocks_aws_key(self, tmp_path, monkeypatch):
        mod = _load_hook_module("secrets_scan")
        _setup_git_with_file(tmp_path, "config.py", 'KEY = "AKIAIOSFODNN7EXAMPLE"\n')
        monkeypatch.chdir(tmp_path)
        result = mod.run({"tool_name": "Bash", "tool_input": {"command": "git commit -m test"}})
        assert result is not None
        assert result["hookSpecificOutput"]["permissionDecision"] == "block"
        assert "AWS Access Key" in result["hookSpecificOutput"]["permissionDecisionReason"]

    def test_blocks_github_token(self, tmp_path, monkeypatch):
        mod = _load_hook_module("secrets_scan")
        _setup_git_with_file(tmp_path, "config.py", 'TOKEN = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef1234"\n')
        monkeypatch.chdir(tmp_path)
        result = mod.run({"tool_name": "Bash", "tool_input": {"command": "git commit -m test"}})
        assert result is not None
        assert "GitHub Token" in result["hookSpecificOutput"]["permissionDecisionReason"]

    def test_passes_clean_file(self, tmp_path, monkeypatch):
        mod = _load_hook_module("secrets_scan")
        _setup_git_with_file(tmp_path, "clean.py", 'import os\nKEY = os.environ["KEY"]\n')
        monkeypatch.chdir(tmp_path)
        result = mod.run({"tool_name": "Bash", "tool_input": {"command": "git commit -m test"}})
        assert result is None

    def test_skips_lock_files(self, tmp_path, monkeypatch):
        mod = _load_hook_module("secrets_scan")
        _setup_git_with_file(tmp_path, "package-lock.json", '{"key": "AKIAIOSFODNN7EXAMPLE"}\n')
        monkeypatch.chdir(tmp_path)
        result = mod.run({"tool_name": "Bash", "tool_input": {"command": "git commit -m test"}})
        assert result is None


# ─── SAST Gate Tests ──────────────────────────────────────────────────

class TestSastGate:
    """Test the sast_gate PreToolUse BLOCKING hook."""

    def test_blocks_sql_injection(self, tmp_path, monkeypatch):
        mod = _load_hook_module("sast_gate")
        _setup_git_with_file(tmp_path, "vuln.py", 'cursor.execute(f"SELECT * FROM users WHERE id = {uid}")\n')
        monkeypatch.chdir(tmp_path)
        result = mod.run({"tool_name": "Bash", "tool_input": {"command": "git commit -m test"}})
        assert result is not None
        assert result["hookSpecificOutput"]["permissionDecision"] == "block"
        assert "SQL injection" in result["hookSpecificOutput"]["permissionDecisionReason"]

    def test_blocks_eval(self, tmp_path, monkeypatch):
        mod = _load_hook_module("sast_gate")
        _setup_git_with_file(tmp_path, "vuln.py", 'result = eval(user_input)\n')
        monkeypatch.chdir(tmp_path)
        result = mod.run({"tool_name": "Bash", "tool_input": {"command": "git commit -m test"}})
        assert result is not None
        assert "eval" in result["hookSpecificOutput"]["permissionDecisionReason"]

    def test_blocks_shell_true(self, tmp_path, monkeypatch):
        mod = _load_hook_module("sast_gate")
        _setup_git_with_file(tmp_path, "vuln.py", 'import subprocess\nsubprocess.run(cmd, shell=True)\n')
        monkeypatch.chdir(tmp_path)
        result = mod.run({"tool_name": "Bash", "tool_input": {"command": "git commit -m test"}})
        assert result is not None
        assert "shell=True" in result["hookSpecificOutput"]["permissionDecisionReason"]

    def test_blocks_innerhtml_xss(self, tmp_path, monkeypatch):
        mod = _load_hook_module("sast_gate")
        _setup_git_with_file(tmp_path, "xss.js", 'document.getElementById("out").innerHTML = input;\n')
        monkeypatch.chdir(tmp_path)
        result = mod.run({"tool_name": "Bash", "tool_input": {"command": "git commit -m test"}})
        assert result is not None
        assert "innerHTML" in result["hookSpecificOutput"]["permissionDecisionReason"]

    def test_passes_medium_severity(self, tmp_path, monkeypatch):
        """MEDIUM patterns (yaml.load, exec) should NOT block commits."""
        mod = _load_hook_module("sast_gate")
        _setup_git_with_file(tmp_path, "medium.py", 'import yaml\ndata = yaml.load(open("cfg.yaml"))\n')
        monkeypatch.chdir(tmp_path)
        result = mod.run({"tool_name": "Bash", "tool_input": {"command": "git commit -m test"}})
        assert result is None

    def test_passes_safe_parameterized_query(self, tmp_path, monkeypatch):
        mod = _load_hook_module("sast_gate")
        _setup_git_with_file(tmp_path, "safe.py", 'cursor.execute("SELECT * FROM users WHERE id = ?", (uid,))\n')
        monkeypatch.chdir(tmp_path)
        result = mod.run({"tool_name": "Bash", "tool_input": {"command": "git commit -m test"}})
        assert result is None

    def test_skips_comments(self, tmp_path, monkeypatch):
        """Security patterns in comments should not trigger blocking."""
        mod = _load_hook_module("sast_gate")
        _setup_git_with_file(tmp_path, "doc.py", '# Example: cursor.execute(f"SELECT * FROM {table}")\n')
        monkeypatch.chdir(tmp_path)
        result = mod.run({"tool_name": "Bash", "tool_input": {"command": "git commit -m test"}})
        assert result is None


# ─── SAST Scan Advisory Tests ────────────────────────────────────────

class TestSastScan:
    """Test the sast_scan PostToolUse advisory hook."""

    def test_warns_sql_injection(self, tmp_path):
        mod = _load_hook_module("sast_scan")
        f = tmp_path / "vuln.py"
        f.write_text('cursor.execute(f"SELECT * FROM users WHERE id = {uid}")\n')
        result = mod.run({"tool_input": {"file_path": str(f)}})
        assert result is not None
        assert "systemMessage" in result
        assert "security" in result["systemMessage"].lower() or "spotted" in result["systemMessage"].lower()
        assert "SQL injection" in result["hookSpecificOutput"]["additionalContext"]

    def test_warns_eval(self, tmp_path):
        mod = _load_hook_module("sast_scan")
        f = tmp_path / "vuln.py"
        f.write_text('result = eval(user_input)\n')
        result = mod.run({"tool_input": {"file_path": str(f)}})
        assert result is not None
        assert "security" in result["systemMessage"].lower() or "spotted" in result["systemMessage"].lower()
        assert "eval" in result["hookSpecificOutput"]["additionalContext"]

    def test_no_warning_for_safe_code(self, tmp_path):
        mod = _load_hook_module("sast_scan")
        f = tmp_path / "safe.py"
        f.write_text('cursor.execute("SELECT * FROM users WHERE id = ?", (uid,))\n')
        result = mod.run({"tool_input": {"file_path": str(f)}})
        assert result is None

    def test_missing_file_returns_none(self):
        mod = _load_hook_module("sast_scan")
        result = mod.run({"tool_input": {"file_path": "/nonexistent/path.py"}})
        assert result is None

    def test_unknown_extension_returns_none(self, tmp_path):
        mod = _load_hook_module("sast_scan")
        f = tmp_path / "data.csv"
        f.write_text('eval(something)\n')
        result = mod.run({"tool_input": {"file_path": str(f)}})
        assert result is None


# ─── Console Warn Tests ──────────────────────────────────────────────

class TestConsoleWarn:
    """Test the console_warn PostToolUse hook."""

    def test_warns_console_log_js(self, tmp_path):
        mod = _load_hook_module("console_warn")
        f = tmp_path / "test.js"
        f.write_text('console.log("debug info")\n')
        result = mod.run({"tool_input": {"file_path": str(f)}})
        assert result is not None
        assert "debug" in result["systemMessage"].lower()

    def test_warns_breakpoint_python(self, tmp_path):
        mod = _load_hook_module("console_warn")
        f = tmp_path / "test.py"
        f.write_text('breakpoint()\n')
        result = mod.run({"tool_input": {"file_path": str(f)}})
        assert result is not None
        assert "debug" in result["systemMessage"].lower()

    def test_no_warn_go_fmt_println(self, tmp_path):
        """fmt.Println is standard Go output, NOT debug."""
        mod = _load_hook_module("console_warn")
        f = tmp_path / "main.go"
        f.write_text('package main\nimport "fmt"\nfunc main() { fmt.Println("hello") }\n')
        result = mod.run({"tool_input": {"file_path": str(f)}})
        assert result is None

    def test_warns_go_log_println(self, tmp_path):
        """log.Println IS debug in Go."""
        mod = _load_hook_module("console_warn")
        f = tmp_path / "main.go"
        f.write_text('package main\nimport "log"\nfunc main() { log.Println("debug") }\n')
        result = mod.run({"tool_input": {"file_path": str(f)}})
        assert result is not None

    def test_unknown_extension_returns_none(self, tmp_path):
        mod = _load_hook_module("console_warn")
        f = tmp_path / "data.txt"
        f.write_text('console.log("test")\n')
        result = mod.run({"tool_input": {"file_path": str(f)}})
        assert result is None


# ─── Session Start Tests ─────────────────────────────────────────────

class TestSessionStart:
    """Test the session_start SessionStart hook."""

    def test_resume_event_skipped(self):
        mod = _load_hook_module("session_start")
        result = mod.run({"source": "resume", "cwd": "."})
        assert result is None

    def test_first_session_shows_guidance(self, tmp_path):
        mod = _load_hook_module("session_start")
        with patch.dict(os.environ, {"HOME": str(tmp_path)}):
            result = mod.run({"source": "startup", "cwd": str(tmp_path)})
        # No previous session, so should include guidance
        if result:
            context = result["hookSpecificOutput"]["additionalContext"]
            assert "describe what you want" in context.lower() or "welcome" in context.lower()

    def test_detects_python_project(self, tmp_path):
        mod = _load_hook_module("session_start")
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        with patch.dict(os.environ, {"HOME": str(tmp_path)}):
            result = mod.run({"source": "startup", "cwd": str(tmp_path)})
        assert result is not None
        assert "Python project" in result["hookSpecificOutput"]["additionalContext"]

    def test_detects_node_project(self, tmp_path):
        mod = _load_hook_module("session_start")
        (tmp_path / "package.json").write_text('{"name": "test"}\n')
        with patch.dict(os.environ, {"HOME": str(tmp_path)}):
            result = mod.run({"source": "startup", "cwd": str(tmp_path)})
        assert result is not None
        assert "Node project" in result["hookSpecificOutput"]["additionalContext"]


# ─── Session End Tests ────────────────────────────────────────────────

class TestSessionEnd:
    """Test the session_end Stop hook."""

    def test_persists_session_data(self, tmp_path):
        mod = _load_hook_module("session_end")
        sessions_dir = tmp_path / ".claude" / "sessions"
        sessions_dir.mkdir(parents=True)
        with patch.dict(os.environ, {"HOME": str(tmp_path)}):
            mod.run({
                "session_id": "test-123",
                "transcript_path": "/dev/null",
                "last_assistant_message": "Fixed the auth bug",
            })
        latest = sessions_dir / "latest.json"
        assert latest.exists()
        data = json.loads(latest.read_text())
        assert data["session_id"] == "test-123"
        assert data["summary"] == "Fixed the auth bug"

    def test_appends_to_history(self, tmp_path):
        mod = _load_hook_module("session_end")
        sessions_dir = tmp_path / ".claude" / "sessions"
        sessions_dir.mkdir(parents=True)
        with patch.dict(os.environ, {"HOME": str(tmp_path)}):
            mod.run({"session_id": "s1", "transcript_path": "", "last_assistant_message": "First"})
            mod.run({"session_id": "s2", "transcript_path": "", "last_assistant_message": "Second"})
        history = sessions_dir / "history.jsonl"
        assert history.exists()
        lines = history.read_text().strip().splitlines()
        assert len(lines) == 2


# ─── Helper ──────────────────────────────────────────────────────────

def _setup_git_with_file(tmp_path, filename, content):
    """Initialize a git repo in tmp_path, write a file, and stage it."""
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(tmp_path), capture_output=True)
    (tmp_path / filename).write_text(content)
    subprocess.run(["git", "add", filename], cwd=str(tmp_path), capture_output=True)


def _get_runner_path() -> str:
    """Return the path to run_with_profile.py in the workspace."""
    return str(Path(__file__).parent.parent / "workspace" / "hooks" / "run_with_profile.py")
