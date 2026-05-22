"""Unit tests for email attachment validation."""

from tj_utils.validate_attachment import (
    MAX_ATTACHMENT_SIZE_BYTES,
    MAX_MESSAGE_SIZE_BYTES,
    format_rejection_log,
    format_size_rejection_log,
    validate_attachment,
    validate_message_size,
)


class TestValidateAttachment:
    """Tests for validate_attachment function."""

    def test_valid_tji_file(self):
        result = validate_attachment("timesheet.tji", 1024)
        assert result.valid is True
        assert result.reason is None

    def test_valid_tji_at_max_size(self):
        result = validate_attachment("timesheet.tji", MAX_ATTACHMENT_SIZE_BYTES)
        assert result.valid is True

    def test_wrong_extension_txt(self):
        result = validate_attachment("timesheet.txt", 1024)
        assert result.valid is False
        assert ".tji" in result.reason

    def test_wrong_extension_tjp(self):
        result = validate_attachment("project.tjp", 1024)
        assert result.valid is False

    def test_no_extension(self):
        result = validate_attachment("timesheet", 1024)
        assert result.valid is False

    def test_oversized_attachment(self):
        result = validate_attachment("timesheet.tji", MAX_ATTACHMENT_SIZE_BYTES + 1)
        assert result.valid is False
        assert "1 MB" in result.reason

    def test_case_insensitive_extension(self):
        result = validate_attachment("timesheet.TJI", 1024)
        assert result.valid is True

    def test_zero_size_valid(self):
        result = validate_attachment("empty.tji", 0)
        assert result.valid is True


class TestValidateMessageSize:
    """Tests for validate_message_size function."""

    def test_valid_message_size(self):
        result = validate_message_size(1024)
        assert result.valid is True
        assert result.message_size == 1024

    def test_at_limit(self):
        result = validate_message_size(MAX_MESSAGE_SIZE_BYTES)
        assert result.valid is True

    def test_over_limit(self):
        result = validate_message_size(MAX_MESSAGE_SIZE_BYTES + 1)
        assert result.valid is False
        assert "5 MB" in result.reason

    def test_zero_size(self):
        result = validate_message_size(0)
        assert result.valid is True


class TestFormatRejectionLog:
    """Tests for rejection log formatting."""

    def test_format_rejection_log(self):
        log = format_rejection_log(
            sender="bob@example.com",
            subject="My Timesheet",
            reason="Attachment does not have .tji extension",
        )
        assert "bob@example.com" in log
        assert "My Timesheet" in log
        assert ".tji extension" in log

    def test_format_size_rejection_log(self):
        log = format_size_rejection_log(
            sender="alice@example.com",
            message_size_bytes=6 * 1024 * 1024,
        )
        assert "alice@example.com" in log
        assert "5 MB" in log
