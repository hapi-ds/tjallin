"""Unit tests for log line formatting."""

from datetime import datetime, timezone

from tj_utils.format_log import format_log


class TestFormatLog:
    """Tests for format_log function."""

    def test_basic_format(self):
        ts = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = format_log("tj-core", "INFO", "Compilation complete", timestamp=ts)
        assert result == "[tj-core] [2024-01-15T10:30:00+00:00] [INFO] Compilation complete"

    def test_contains_service_name(self):
        result = format_log("tj-mail", "WARNING", "test message")
        assert "[tj-mail]" in result

    def test_contains_level(self):
        result = format_log("tj-cron", "ERROR", "task failed")
        assert "[ERROR]" in result

    def test_contains_message(self):
        result = format_log("tj-web", "DEBUG", "request received")
        assert "request received" in result

    def test_contains_iso_timestamp(self):
        ts = datetime(2024, 6, 15, 14, 0, 0, tzinfo=timezone.utc)
        result = format_log("tj-core", "INFO", "test", timestamp=ts)
        assert "2024-06-15T14:00:00" in result

    def test_default_timestamp_is_utc(self):
        result = format_log("tj-core", "INFO", "test")
        # Should contain a valid ISO timestamp with timezone info
        assert "+00:00" in result or "Z" in result

    def test_special_characters_in_message(self):
        result = format_log("tj-core", "INFO", "file: /path/to/file.tji [ok]")
        assert "file: /path/to/file.tji [ok]" in result

    def test_unicode_in_message(self):
        result = format_log("tj-core", "INFO", "Ärende: uppgift klar ✓")
        assert "Ärende: uppgift klar ✓" in result

    def test_empty_message(self):
        result = format_log("tj-core", "INFO", "")
        assert result.endswith("[INFO] ")
