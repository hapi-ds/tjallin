"""Unit tests for the path safety module."""

import os
from pathlib import Path

import pytest

from tj_chat.models import PathSecurityError
from tj_chat.path_safety import is_within_project, validate_project_path


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    """Create a temporary project root directory."""
    root = tmp_path / "project"
    root.mkdir()
    (root / "includes").mkdir()
    (root / "includes" / "tasks.tji").write_text("task foo {}")
    (root / "timesheets").mkdir()
    return root


class TestIsWithinProject:
    """Tests for is_within_project()."""

    def test_path_equal_to_root(self, project_root: Path) -> None:
        resolved_root = project_root.resolve()
        assert is_within_project(resolved_root, resolved_root) is True

    def test_path_inside_root(self, project_root: Path) -> None:
        resolved_root = project_root.resolve()
        child = (project_root / "includes" / "tasks.tji").resolve()
        assert is_within_project(child, resolved_root) is True

    def test_path_outside_root(self, project_root: Path) -> None:
        resolved_root = project_root.resolve()
        outside = project_root.parent.resolve()
        assert is_within_project(outside, resolved_root) is False

    def test_sibling_directory(self, tmp_path: Path) -> None:
        root = (tmp_path / "project").resolve()
        sibling = (tmp_path / "other").resolve()
        assert is_within_project(sibling, root) is False


class TestValidateProjectPath:
    """Tests for validate_project_path()."""

    def test_valid_relative_path(self, project_root: Path) -> None:
        result = validate_project_path("includes/tasks.tji", project_root)
        expected = (project_root / "includes" / "tasks.tji").resolve()
        assert result == expected

    def test_valid_absolute_path(self, project_root: Path) -> None:
        abs_path = project_root / "includes" / "tasks.tji"
        result = validate_project_path(str(abs_path), project_root)
        assert result == abs_path.resolve()

    def test_path_with_dot_segments(self, project_root: Path) -> None:
        result = validate_project_path("includes/../includes/tasks.tji", project_root)
        expected = (project_root / "includes" / "tasks.tji").resolve()
        assert result == expected

    def test_path_escaping_with_dotdot_raises(self, project_root: Path) -> None:
        with pytest.raises(PathSecurityError) as exc_info:
            validate_project_path("../../etc/passwd", project_root)
        assert exc_info.value.path == "../../etc/passwd"
        assert str(project_root.resolve()) in exc_info.value.project_root

    def test_absolute_path_outside_raises(self, project_root: Path, tmp_path: Path) -> None:
        outside = tmp_path / "outside.txt"
        outside.write_text("secret")
        with pytest.raises(PathSecurityError):
            validate_project_path(str(outside), project_root)

    def test_root_path_itself_is_valid(self, project_root: Path) -> None:
        result = validate_project_path(str(project_root), project_root)
        assert result == project_root.resolve()

    def test_accepts_path_object(self, project_root: Path) -> None:
        path_obj = Path("includes/tasks.tji")
        result = validate_project_path(path_obj, project_root)
        expected = (project_root / "includes" / "tasks.tji").resolve()
        assert result == expected

    @pytest.mark.skipif(os.name == "nt", reason="Symlinks may require admin on Windows")
    def test_symlink_escaping_raises(self, project_root: Path, tmp_path: Path) -> None:
        """Symlink inside project pointing outside should be rejected."""
        outside_file = tmp_path / "secret.txt"
        outside_file.write_text("secret data")
        link_path = project_root / "sneaky_link"
        try:
            link_path.symlink_to(outside_file)
        except OSError:
            pytest.skip("Cannot create symlinks in this environment")
        with pytest.raises(PathSecurityError):
            validate_project_path("sneaky_link", project_root)

    def test_nonexistent_path_within_project(self, project_root: Path) -> None:
        """Non-existent paths within project boundary should be accepted."""
        result = validate_project_path("new_file.tji", project_root)
        expected = (project_root / "new_file.tji").resolve()
        assert result == expected
