"""PostToolUseFailure hook — format tool errors into actionable context."""
from __future__ import annotations


def run(input: dict) -> dict | None:
    tool_name = input.get("tool_name", "unknown")
    error = str(input.get("error", ""))
    tool_input = input.get("tool_input", {})

    if not error:
        return None

    summary = _summarize_error(error)
    suggestion = _suggest_fix(tool_name, error, tool_input)

    context = f"[tool-error] {tool_name}: {summary}. Suggestion: {suggestion}"

    return {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUseFailure",
            "additionalContext": context,
        }
    }


def _summarize_error(error: str) -> str:
    """Extract first meaningful line, truncate to 200 chars."""
    for line in error.splitlines():
        cleaned = line.strip()
        if cleaned:
            return cleaned[:200]
    return error[:200]


def _suggest_fix(tool_name: str, error: str, tool_input: dict) -> str:
    """Provide actionable hints based on common error patterns."""
    error_lower = error.lower()

    if tool_name == "Bash":
        if "permission denied" in error_lower:
            return "Check file permissions or use sudo if appropriate"
        if "command not found" in error_lower:
            return "Verify the command is installed and in PATH"
        if "no such file or directory" in error_lower:
            return "Verify the file path exists; use Glob to search"
        if "timeout" in error_lower:
            return "Command took too long; simplify or add a timeout"

    if tool_name == "Edit":
        if "not found" in error_lower or "no such file" in error_lower:
            return "Verify the file path exists; use Glob to search"
        if "old_string" in error_lower or "not unique" in error_lower:
            return "Read the file first to get the exact current content, then retry with more context"

    if tool_name == "Write":
        if "permission denied" in error_lower:
            return "Check directory permissions or write to an allowed path"

    if tool_name == "Read":
        if "not found" in error_lower or "does not exist" in error_lower:
            return "Verify the file path; use Glob to find the correct location"

    return "Review the error details and retry with corrected inputs"
