"""Tests for beads custom tools — validates argument construction and input validation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from knowledge.recipes.codebase_analysis.beads_tools import (
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
    with patch("knowledge.recipes.codebase_analysis.beads_tools.subprocess.run") as mock:
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
        assert "-d" in args
        assert "My Body" in args
        assert "--silent" in args

    def test_create_with_tags(self, mock_run: MagicMock) -> None:
        create_bead("Title", "Body", tags=["structure", "diplomat-logic"])
        args = mock_run.call_args[0][0]
        assert "-l" in args
        label_idx = args.index("-l")
        assert args[label_idx + 1] == "structure,diplomat-logic"

    def test_create_with_db_path(self, mock_run: MagicMock) -> None:
        create_bead("Title", "Body", db_path=Path("/my/beads.db"))
        args = mock_run.call_args[0][0]
        assert "--db" in args
        assert "/my/beads.db" in args
        assert "cwd" not in mock_run.call_args[1]

    def test_invalid_tag_rejected(self, mock_run: MagicMock) -> None:
        with pytest.raises(ValueError, match="Invalid tag"):
            create_bead("Title", "Body", tags=["valid", "$(evil)"])

    def test_uses_list_args_not_shell(self, mock_run: MagicMock) -> None:
        create_bead("Title with spaces", "Body with $pecial chars")
        assert mock_run.call_args[1].get("shell") is None or mock_run.call_args[1].get("shell") is False

    def test_no_cwd_without_db_path(self, mock_run: MagicMock) -> None:
        create_bead("Title", "Body")
        assert "cwd" not in mock_run.call_args[1]

    def test_no_cwd_with_db_path(self, mock_run: MagicMock) -> None:
        create_bead("Title", "Body", db_path=Path("/my/beads.db"))
        assert "cwd" not in mock_run.call_args[1]


class TestLinkBeads:

    def test_depends_on(self, mock_run: MagicMock) -> None:
        assert link_beads("bead-1", "bead-2", "depends-on") is True
        args = mock_run.call_args[0][0]
        assert "dep" in args
        assert "add" in args
        assert "bead-1" in args
        assert "bead-2" in args

    def test_blocks_reverses_order(self, mock_run: MagicMock) -> None:
        link_beads("bead-1", "bead-2", "blocks")
        args = mock_run.call_args[0][0]
        # "bead-1 blocks bead-2" means "bead-2 depends on bead-1"
        # → bd dep add bead-2 bead-1
        dep_idx = args.index("add")
        assert args[dep_idx + 1] == "bead-2"
        assert args[dep_idx + 2] == "bead-1"

    def test_invalid_rel_type(self, mock_run: MagicMock) -> None:
        with pytest.raises(ValueError, match="Invalid rel_type"):
            link_beads("a", "b", "invalid-type")

    def test_invalid_bead_id(self, mock_run: MagicMock) -> None:
        with pytest.raises(ValueError, match="Invalid bead ID"):
            link_beads("$(evil)", "b", "depends-on")

    def test_all_valid_rel_types(self, mock_run: MagicMock) -> None:
        for rel in ("depends-on", "relates-to", "blocks"):
            assert link_beads("a", "b", rel) is True

    def test_link_with_db_path(self, mock_run: MagicMock) -> None:
        link_beads("bead-1", "bead-2", "depends-on", db_path=Path("/my/beads.db"))
        args = mock_run.call_args[0][0]
        assert "--db" in args
        assert "/my/beads.db" in args
        assert "cwd" not in mock_run.call_args[1]


class TestTagBead:

    def test_valid_tag(self, mock_run: MagicMock) -> None:
        assert tag_bead("bead-1", ["structure", "has-db"]) is True
        # Should call bd label add once per tag
        assert mock_run.call_count == 2

    def test_tag_uses_label_add(self, mock_run: MagicMock) -> None:
        tag_bead("bead-1", ["structure"])
        args = mock_run.call_args[0][0]
        assert "label" in args
        assert "add" in args
        assert "bead-1" in args
        assert "structure" in args

    def test_invalid_bead_id(self, mock_run: MagicMock) -> None:
        with pytest.raises(ValueError, match="Invalid bead ID"):
            tag_bead("'; DROP TABLE", ["tag"])

    def test_invalid_tag(self, mock_run: MagicMock) -> None:
        with pytest.raises(ValueError, match="Invalid tag"):
            tag_bead("bead-1", ["valid", "not valid"])


class TestCommentBead:

    def test_valid_comment(self, mock_run: MagicMock) -> None:
        assert comment_bead("bead-1", "This is a comment") is True
        args = mock_run.call_args[0][0]
        assert "comments" in args
        assert "add" in args

    def test_invalid_bead_id(self, mock_run: MagicMock) -> None:
        with pytest.raises(ValueError, match="Invalid bead ID"):
            comment_bead("$(cmd)", "comment")


class TestCloseBead:

    def test_valid_close(self, mock_run: MagicMock) -> None:
        assert close_bead("bead-1", "Analysis complete") is True
        args = mock_run.call_args[0][0]
        assert "close" in args
        assert "-r" in args

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


class TestRunBd:

    def test_db_flag_injected_before_subcommand(self, mock_run: MagicMock) -> None:
        """--db <path> should appear between 'bd' and the subcommand args."""
        create_bead("Title", "Body", db_path=Path("/out/beads.db"))
        args = mock_run.call_args[0][0]
        assert args[0] == "bd"
        assert args[1] == "--db"
        assert args[2] == "/out/beads.db"
        assert "--no-daemon" in args
        assert "create" in args

    def test_no_db_flag_without_db_path(self, mock_run: MagicMock) -> None:
        create_bead("Title", "Body")
        args = mock_run.call_args[0][0]
        assert "--db" not in args
        assert args == ["bd", "create", "Title", "-d", "Body", "--silent"]


class TestGetCustomTools:

    def test_returns_all_tools(self) -> None:
        tools = get_custom_tools(Path("/out/beads.db"))
        expected_keys = {
            "create_bead", "link_beads", "tag_bead",
            "comment_bead", "close_bead", "query_beads", "export_graph",
        }
        assert set(tools.keys()) == expected_keys

    def test_tools_have_callable_and_description(self) -> None:
        tools = get_custom_tools(Path("/out/beads.db"))
        for name, tool_def in tools.items():
            assert "tool" in tool_def, f"{name} missing 'tool'"
            assert "description" in tool_def, f"{name} missing 'description'"
            assert callable(tool_def["tool"]), f"{name} tool not callable"
            assert isinstance(tool_def["description"], str), f"{name} description not str"
