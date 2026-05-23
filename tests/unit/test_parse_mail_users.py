"""Unit tests for mail user parsing and validation."""

from tj_utils.parse_mail_users import (
    MAX_ENTRIES,
    MailUser,
    ParseResult,
    parse_mail_users,
)


class TestParseMailUsersBasic:
    """Tests for basic parsing behavior."""

    def test_single_valid_entry(self):
        result = parse_mail_users("alice:secret123")
        assert len(result.users) == 1
        assert result.users[0].username == "alice"
        assert result.users[0].password == "secret123"
        assert result.errors == []

    def test_multiple_valid_entries(self):
        result = parse_mail_users("alice:pass1,bob:pass2,carol:pass3")
        assert len(result.users) == 3
        assert result.users[0] == MailUser(username="alice", password="pass1")
        assert result.users[1] == MailUser(username="bob", password="pass2")
        assert result.users[2] == MailUser(username="carol", password="pass3")
        assert result.errors == []

    def test_entries_with_whitespace(self):
        result = parse_mail_users(" alice:pass1 , bob:pass2 ")
        assert len(result.users) == 2
        assert result.users[0].username == "alice"
        assert result.users[1].username == "bob"


class TestParseMailUsersFallback:
    """Tests for default fallback behavior when value is None/empty."""

    def test_none_value_uses_mail_sender(self):
        result = parse_mail_users(None, mail_sender="alice@example.com")
        assert len(result.users) == 1
        assert result.users[0].username == "alice"
        assert result.users[0].password == "alice"
        assert result.errors == []

    def test_empty_string_uses_mail_sender(self):
        result = parse_mail_users("", mail_sender="bob@domain.org")
        assert len(result.users) == 1
        assert result.users[0].username == "bob"
        assert result.users[0].password == "bob"

    def test_whitespace_only_uses_mail_sender(self):
        result = parse_mail_users("   ", mail_sender="admin@local.host")
        assert len(result.users) == 1
        assert result.users[0].username == "admin"
        assert result.users[0].password == "admin"

    def test_default_mail_sender(self):
        result = parse_mail_users(None)
        assert len(result.users) == 1
        assert result.users[0].username == "taskjuggler"
        assert result.users[0].password == "taskjuggler"

    def test_mail_sender_without_at(self):
        result = parse_mail_users(None, mail_sender="localuser")
        assert len(result.users) == 1
        assert result.users[0].username == "localuser"
        assert result.users[0].password == "localuser"


class TestParseMailUsersValidation:
    """Tests for username and password validation."""

    def test_username_with_valid_special_chars(self):
        result = parse_mail_users("user-name.test_1:pass")
        assert len(result.users) == 1
        assert result.users[0].username == "user-name.test_1"

    def test_username_too_long(self):
        long_name = "a" * 65
        result = parse_mail_users(f"{long_name}:pass")
        assert len(result.users) == 0
        assert len(result.errors) == 1
        assert "exceeds 64 characters" in result.errors[0]

    def test_username_at_max_length(self):
        name = "a" * 64
        result = parse_mail_users(f"{name}:pass")
        assert len(result.users) == 1
        assert result.users[0].username == name

    def test_username_invalid_chars(self):
        result = parse_mail_users("user@name:pass")
        assert len(result.users) == 0
        assert len(result.errors) == 1
        assert "invalid characters" in result.errors[0]

    def test_username_empty(self):
        result = parse_mail_users(":password")
        assert len(result.users) == 0
        assert len(result.errors) == 1
        assert "empty" in result.errors[0]

    def test_password_too_long(self):
        long_pass = "x" * 129
        result = parse_mail_users(f"user:{long_pass}")
        assert len(result.users) == 0
        assert len(result.errors) == 1
        assert "exceeds 128 characters" in result.errors[0]

    def test_password_at_max_length(self):
        password = "x" * 128
        result = parse_mail_users(f"user:{password}")
        assert len(result.users) == 1
        assert result.users[0].password == password

    def test_password_empty(self):
        result = parse_mail_users("user:")
        assert len(result.users) == 0
        assert len(result.errors) == 1
        assert "empty" in result.errors[0]

    def test_password_with_comma(self):
        # Comma in password is not possible via normal parsing since comma is the delimiter.
        # But if somehow a password contains a comma, it would be split as separate entries.
        # This test verifies the split behavior.
        result = parse_mail_users("user:pass,word")
        # "user:pass" is valid, "word" has no colon
        assert len(result.users) == 1
        assert result.users[0].password == "pass"
        assert len(result.errors) == 1

    def test_password_with_colon(self):
        # Split on first colon: username="user", password="pass:word"
        result = parse_mail_users("user:pass:word")
        assert len(result.users) == 0
        assert len(result.errors) == 1
        assert "colon" in result.errors[0]


class TestParseMailUsersMalformed:
    """Tests for malformed entries."""

    def test_missing_colon_separator(self):
        result = parse_mail_users("alicepassword")
        assert len(result.users) == 0
        assert len(result.errors) == 1
        assert "missing ':'" in result.errors[0]

    def test_empty_entry_between_commas(self):
        result = parse_mail_users("alice:pass,,bob:pass2")
        assert len(result.users) == 2
        assert len(result.errors) == 1
        assert "empty entry" in result.errors[0]

    def test_mixed_valid_and_invalid(self):
        result = parse_mail_users("alice:pass1,badentry,bob:pass2")
        assert len(result.users) == 2
        assert result.users[0].username == "alice"
        assert result.users[1].username == "bob"
        assert len(result.errors) == 1


class TestParseMailUsersMaxEntries:
    """Tests for maximum entries enforcement."""

    def test_exactly_50_entries(self):
        entries = ",".join(f"user{i}:pass{i}" for i in range(50))
        result = parse_mail_users(entries)
        assert len(result.users) == MAX_ENTRIES
        assert result.errors == []

    def test_51st_entry_rejected(self):
        entries = ",".join(f"user{i}:pass{i}" for i in range(51))
        result = parse_mail_users(entries)
        assert len(result.users) == MAX_ENTRIES
        assert len(result.errors) == 1
        assert "exceeds maximum" in result.errors[0]

    def test_many_entries_over_limit(self):
        entries = ",".join(f"user{i}:pass{i}" for i in range(55))
        result = parse_mail_users(entries)
        assert len(result.users) == MAX_ENTRIES
        assert len(result.errors) == 5
