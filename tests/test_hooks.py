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


def _get_runner_path() -> str:
    """Return the path to run_with_profile.py in the workspace."""
    return str(Path(__file__).parent.parent / "workspace" / "hooks" / "run_with_profile.py")
