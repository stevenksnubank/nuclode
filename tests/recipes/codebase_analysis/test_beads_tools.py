"""Tests for beads custom tools — validates argument construction and input validation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from recipes.codebase_analysis.beads_tools import (
    close_bead,
    comment_bead,
    create_bead,
    export_graph,
    get_custom_tools,
    link_beads,
    query_beads,
    tag_bead,
)


@pytest.fixture
def mock_run():
    """Mock subprocess.run to capture arguments without running bd."""
    with patch("recipes.codebase_analysis.beads_tools.subprocess.run") as mock:
        mock.return_value = MagicMock(returncode=0, stdout="bead-123\n", stderr="")
        yield mock


class TestCreateBead:

    def test_basic_create(self, mock_run: MagicMock) -> None:
        result = create_bead("My Title", "My Body")
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "bd"
        assert args[1] == "create"
        assert "My Title" in args
        assert "My Body" in args

    def test_create_with_tags(self, mock_run: MagicMock) -> None:
        create_bead("Title", "Body", tags=["structure", "diplomat-logic"])
        args = mock_run.call_args[0][0]
        assert "-t" in args
        assert "structure" in args
        assert "diplomat-logic" in args

    def test_create_with_project_dir(self, mock_run: MagicMock) -> None:
        create_bead("Title", "Body", project_dir=Path("/my/project"))
        assert mock_run.call_args[1]["cwd"] == "/my/project"

    def test_invalid_tag_rejected(self, mock_run: MagicMock) -> None:
        with pytest.raises(ValueError, match="Invalid tag"):
            create_bead("Title", "Body", tags=["valid", "$(evil)"])

    def test_uses_list_args_not_shell(self, mock_run: MagicMock) -> None:
        create_bead("Title with spaces", "Body with $pecial chars")
        assert mock_run.call_args[1].get("shell") is None or mock_run.call_args[1].get("shell") is False


class TestLinkBeads:

    def test_valid_link(self, mock_run: MagicMock) -> None:
        assert link_beads("bead-1", "bead-2", "depends-on") is True
        args = mock_run.call_args[0][0]
        assert "link" in args
        assert "bead-1" in args
        assert "bead-2" in args
        assert "depends-on" in args

    def test_invalid_rel_type(self, mock_run: MagicMock) -> None:
        with pytest.raises(ValueError, match="Invalid rel_type"):
            link_beads("a", "b", "invalid-type")

    def test_invalid_bead_id(self, mock_run: MagicMock) -> None:
        with pytest.raises(ValueError, match="Invalid bead ID"):
            link_beads("$(evil)", "b", "depends-on")

    def test_all_valid_rel_types(self, mock_run: MagicMock) -> None:
        for rel in ("depends-on", "relates-to", "blocks"):
            assert link_beads("a", "b", rel) is True


class TestTagBead:

    def test_valid_tag(self, mock_run: MagicMock) -> None:
        assert tag_bead("bead-1", ["structure", "has-db"]) is True

    def test_invalid_bead_id(self, mock_run: MagicMock) -> None:
        with pytest.raises(ValueError, match="Invalid bead ID"):
            tag_bead("'; DROP TABLE", ["tag"])

    def test_invalid_tag(self, mock_run: MagicMock) -> None:
        with pytest.raises(ValueError, match="Invalid tag"):
            tag_bead("bead-1", ["valid", "not valid"])


class TestCommentBead:

    def test_valid_comment(self, mock_run: MagicMock) -> None:
        assert comment_bead("bead-1", "This is a comment") is True

    def test_invalid_bead_id(self, mock_run: MagicMock) -> None:
        with pytest.raises(ValueError, match="Invalid bead ID"):
            comment_bead("$(cmd)", "comment")


class TestCloseBead:

    def test_valid_close(self, mock_run: MagicMock) -> None:
        assert close_bead("bead-1", "Analysis complete") is True

    def test_invalid_bead_id(self, mock_run: MagicMock) -> None:
        with pytest.raises(ValueError, match="Invalid bead ID"):
            close_bead("bad id", "summary")


class TestQueryBeads:

    def test_query(self, mock_run: MagicMock) -> None:
        mock_run.return_value.stdout = "bead-1\nbead-2\n"
        result = query_beads("--tag structure")
        assert "bead-1" in result

    def test_query_failure(self, mock_run: MagicMock) -> None:
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "error"
        with pytest.raises(RuntimeError, match="bd query failed"):
            query_beads("bad-filter")


class TestGetCustomTools:

    def test_returns_all_tools(self) -> None:
        tools = get_custom_tools(Path("/project"))
        expected_keys = {
            "create_bead", "link_beads", "tag_bead",
            "comment_bead", "close_bead", "query_beads", "export_graph",
        }
        assert set(tools.keys()) == expected_keys

    def test_tools_have_callable_and_description(self) -> None:
        tools = get_custom_tools(Path("/project"))
        for name, tool_def in tools.items():
            assert "tool" in tool_def, f"{name} missing 'tool'"
            assert "description" in tool_def, f"{name} missing 'description'"
            assert callable(tool_def["tool"]), f"{name} tool not callable"
            assert isinstance(tool_def["description"], str), f"{name} description not str"
