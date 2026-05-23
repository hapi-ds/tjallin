"""Property-based tests for TJ_MAIL_USERS parsing.

Feature: integrated-mail-and-reporting, Property 8: TJ_MAIL_USERS parsing correctness

**Validates: Requirements 3.1, 3.2, 3.4**

Property 8: For any TJ_MAIL_USERS string containing a mix of valid user:password entries
and malformed entries, parsing SHALL extract all valid entries as MailUser objects and SHALL
report errors for each malformed entry, with the count of valid users plus errors equaling
the total entry count.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from tj_utils.parse_mail_users import (
    MAX_ENTRIES,
    MAX_PASSWORD_LENGTH,
    MAX_USERNAME_LENGTH,
    MailUser,
    parse_mail_users,
)

# --- Strategies ---

# Valid username: 1–64 chars, alphanumeric plus `-_.`
_username_alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_."
_valid_username = st.text(
    alphabet=_username_alphabet,
    min_size=1,
    max_size=MAX_USERNAME_LENGTH,
)

# Valid password: 1–128 chars, no commas or colons
# Note: commas are the top-level entry separator, so they cannot appear in passwords
_password_alphabet = st.characters(
    categories=("L", "N", "P", "S"),
    exclude_characters=",:\x00",
)
_valid_password = st.text(
    alphabet=_password_alphabet,
    min_size=1,
    max_size=MAX_PASSWORD_LENGTH,
)


@st.composite
def valid_entry(draw: st.DrawFn) -> str:
    """Generate a valid user:password entry string."""
    username = draw(_valid_username)
    password = draw(_valid_password)
    return f"{username}:{password}"


@st.composite
def malformed_entry(draw: st.DrawFn) -> str:
    """Generate a malformed entry that will fail validation.

    Important: entries must NOT contain commas, since commas are the top-level
    delimiter used by the parser to split entries. Including commas would cause
    the parser to see multiple entries where we expect one.

    Malformed entries include:
    - Missing colon separator
    - Empty username (starts with colon)
    - Username with invalid characters
    - Username too long (>64 chars)
    - Empty password
    - Password too long (>128 chars)
    - Password containing colon (split on first colon means rest goes to password)
    """
    # Password alphabet excluding commas (commas are the entry separator)
    _password_no_comma = st.characters(
        categories=("L", "N", "P", "S"),
        exclude_characters=",:\x00",
    )

    kind = draw(
        st.sampled_from([
            "no_colon",
            "empty_username",
            "invalid_username_chars",
            "username_too_long",
            "empty_password",
            "password_too_long",
            "password_with_colon",
        ])
    )

    if kind == "no_colon":
        # Text without any colon or comma
        return draw(st.text(
            alphabet=st.characters(categories=("L", "N"), exclude_characters=":,\x00"),
            min_size=1,
            max_size=20,
        ))
    elif kind == "empty_username":
        password = draw(st.text(alphabet=_password_no_comma, min_size=1, max_size=20))
        return f":{password}"
    elif kind == "invalid_username_chars":
        # Username with at least one invalid character (e.g., space, @, !)
        invalid_char = draw(st.sampled_from(list(" @!#$%^&*()+=[]{}|\\/<>?~`")))
        base = draw(st.text(alphabet=_username_alphabet, min_size=0, max_size=10))
        username = base + invalid_char
        password = draw(st.text(alphabet=_password_no_comma, min_size=1, max_size=20))
        return f"{username}:{password}"
    elif kind == "username_too_long":
        username = draw(st.text(
            alphabet=_username_alphabet,
            min_size=MAX_USERNAME_LENGTH + 1,
            max_size=MAX_USERNAME_LENGTH + 20,
        ))
        password = draw(st.text(alphabet=_password_no_comma, min_size=1, max_size=20))
        return f"{username}:{password}"
    elif kind == "empty_password":
        username = draw(_valid_username)
        return f"{username}:"
    elif kind == "password_too_long":
        username = draw(_valid_username)
        password = draw(st.text(
            alphabet=_password_no_comma,
            min_size=MAX_PASSWORD_LENGTH + 1,
            max_size=MAX_PASSWORD_LENGTH + 20,
        ))
        return f"{username}:{password}"
    elif kind == "password_with_colon":
        username = draw(_valid_username)
        # Password that contains at least one colon (no commas)
        prefix = draw(st.text(alphabet=_password_no_comma, min_size=1, max_size=10))
        suffix = draw(st.text(alphabet=_password_no_comma, min_size=1, max_size=10))
        return f"{username}:{prefix}:{suffix}"
    else:
        # Fallback: no colon entry
        return draw(st.text(
            alphabet=st.characters(categories=("L", "N"), exclude_characters=":,\x00"),
            min_size=1,
            max_size=10,
        ))


@st.composite
def mixed_entries(draw: st.DrawFn) -> tuple[list[str], list[bool]]:
    """Generate a list of entries mixing valid and malformed ones.

    Returns (entries, is_valid_flags) where is_valid_flags[i] indicates
    whether entries[i] is a valid entry.
    Limits to MAX_ENTRIES to keep within the parseable range.
    """
    count = draw(st.integers(min_value=1, max_value=MAX_ENTRIES))
    entries: list[str] = []
    is_valid: list[bool] = []

    for _ in range(count):
        use_valid = draw(st.booleans())
        if use_valid:
            entries.append(draw(valid_entry()))
            is_valid.append(True)
        else:
            entries.append(draw(malformed_entry()))
            is_valid.append(False)

    return entries, is_valid


class TestMailUsersParsingCorrectness:
    """Property 8: TJ_MAIL_USERS parsing correctness.

    Feature: integrated-mail-and-reporting, Property 8: TJ_MAIL_USERS parsing correctness

    **Validates: Requirements 3.1, 3.2, 3.4**
    """

    @given(data=mixed_entries())
    @settings(max_examples=100)
    def test_valid_users_plus_errors_equals_total_entries(
        self, data: tuple[list[str], list[bool]]
    ) -> None:
        """The count of valid users plus errors must equal the total entry count."""
        entries, _ = data
        value = ",".join(entries)

        result = parse_mail_users(value)

        total_entries = len(entries)
        assert len(result.users) + len(result.errors) == total_entries, (
            f"Expected users ({len(result.users)}) + errors ({len(result.errors)}) "
            f"== total entries ({total_entries}), "
            f"input: {value!r}"
        )

    @given(data=mixed_entries())
    @settings(max_examples=100)
    def test_valid_entries_produce_correct_mail_user_objects(
        self, data: tuple[list[str], list[bool]]
    ) -> None:
        """All valid entries produce MailUser objects with correct username and password fields."""
        entries, is_valid = data
        value = ",".join(entries)

        result = parse_mail_users(value)

        # Collect expected valid users in order
        expected_users: list[tuple[str, str]] = []
        for entry, valid in zip(entries, is_valid):
            if valid:
                parts = entry.split(":", 1)
                expected_users.append((parts[0], parts[1]))

        # The parsed valid users should match expected valid entries in order
        assert len(result.users) == len(expected_users), (
            f"Expected {len(expected_users)} valid users, got {len(result.users)}. "
            f"Input: {value!r}"
        )

        for user, (exp_username, exp_password) in zip(result.users, expected_users):
            assert isinstance(user, MailUser)
            assert user.username == exp_username, (
                f"Expected username {exp_username!r}, got {user.username!r}"
            )
            assert user.password == exp_password, (
                f"Expected password {exp_password!r}, got {user.password!r}"
            )

    @given(entries=st.lists(valid_entry(), min_size=1, max_size=MAX_ENTRIES))
    @settings(max_examples=100)
    def test_all_valid_entries_produce_no_errors(
        self, entries: list[str]
    ) -> None:
        """When all entries are valid, parsing produces zero errors."""
        value = ",".join(entries)

        result = parse_mail_users(value)

        assert len(result.errors) == 0, (
            f"Expected no errors for all-valid input, got: {result.errors}"
        )
        assert len(result.users) == len(entries), (
            f"Expected {len(entries)} users, got {len(result.users)}"
        )

    @given(entries=st.lists(malformed_entry(), min_size=1, max_size=MAX_ENTRIES))
    @settings(max_examples=100)
    def test_all_malformed_entries_produce_no_valid_users(
        self, entries: list[str]
    ) -> None:
        """When all entries are malformed, parsing produces zero valid users."""
        value = ",".join(entries)

        result = parse_mail_users(value)

        assert len(result.users) == 0, (
            f"Expected no valid users for all-malformed input, got {len(result.users)} users. "
            f"Input: {value!r}, Users: {result.users}"
        )
        assert len(result.errors) == len(entries), (
            f"Expected {len(entries)} errors, got {len(result.errors)}. "
            f"Input: {value!r}"
        )
