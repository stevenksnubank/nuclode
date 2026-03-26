#!/usr/bin/env python3
"""Hook runtime control and module loader.

Usage: python3 run_with_profile.py <hook-id> <module-name> <profiles>

Mirrors ECC's run-with-flags.js pattern: reads stdin JSON, checks profile/disabled
controls, then importlib-loads the hook module and calls its run() function.

Env vars:
    NUCLODE_HOOK_PROFILE    - minimal|standard|strict (default: standard)
    NUCLODE_DISABLED_HOOKS  - comma-separated hook IDs to disable
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 4:
        print("Usage: run_with_profile.py <hook-id> <module-name> <profiles>", file=sys.stderr)
        sys.exit(1)

    hook_id = sys.argv[1]
    module_name = sys.argv[2]
    profiles = sys.argv[3].split(",")

    current_profile = os.environ.get("NUCLODE_HOOK_PROFILE", "standard")
    disabled = [h.strip() for h in os.environ.get("NUCLODE_DISABLED_HOOKS", "").split(",") if h.strip()]

    # Fast-path exits: profile mismatch or explicitly disabled
    if hook_id in disabled:
        return
    if current_profile not in profiles:
        return

    # Read stdin (Claude Code sends JSON payload)
    input_text = sys.stdin.read()
    try:
        input_data = json.loads(input_text) if input_text.strip() else {}
    except json.JSONDecodeError as e:
        print(f"Warning: invalid JSON on stdin: {e}", file=sys.stderr)
        input_data = {}

    # Load hook module via importlib
    hook_dir = Path(__file__).parent
    module_path = hook_dir / f"{module_name}.py"

    if not module_path.exists():
        print(f"Hook module not found: {module_path}", file=sys.stderr)
        return

    spec = importlib.util.spec_from_file_location(module_name, str(module_path))
    if spec is None or spec.loader is None:
        print(f"Failed to create module spec for: {module_path}", file=sys.stderr)
        return

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Validate the module has a callable run()
    if not hasattr(module, "run") or not callable(module.run):
        print(f"Hook module {module_name} has no callable run()", file=sys.stderr)
        return

    # Call the hook's run() function
    result = module.run(input_data)

    # Output result as JSON if the hook returned something
    if result is not None:
        json.dump(result, sys.stdout)
        sys.stdout.flush()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Advisory hooks never block Claude. Log to stderr, exit clean.
        print(f"Hook runner error: {e}", file=sys.stderr)
        sys.exit(0)
