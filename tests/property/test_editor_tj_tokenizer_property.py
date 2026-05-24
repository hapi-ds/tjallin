"""Property-based tests for TJ tokenizer classification.

# Feature: project-file-editor, Property 5: TJ tokenizer classification

**Validates: Requirements 3.2**

For any string that is a known TaskJuggler keyword, the tokenizer SHALL
classify it as a keyword token. For any string starting with `#` or `//`
up to end-of-line, the tokenizer SHALL classify it as a comment token.
For any quoted string (double or single quotes), the tokenizer SHALL
classify it as a string token.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from tj_chat.tj_codemirror import (
    TJ_KEYWORDS,
    TJ_NUMBER_PATTERN,
    TJ_OPERATORS,
    classify_tj_token,
)

# Strategy: pick any keyword from the TJ_KEYWORDS list
_tj_keyword = st.sampled_from(TJ_KEYWORDS)

# Strategy: arbitrary text that doesn't contain newlines (comment body)
_comment_body = st.text(
    alphabet=st.characters(exclude_characters="\x00\r\n"),
    min_size=0,
    max_size=80,
)

# Strategy: string content without the quote character (for double-quoted strings)
_double_quote_content = st.text(
    alphabet=st.characters(exclude_characters='\x00"'),
    min_size=0,
    max_size=50,
)

# Strategy: string content without the quote character (for single-quoted strings)
_single_quote_content = st.text(
    alphabet=st.characters(exclude_characters="\x00'"),
    min_size=0,
    max_size=50,
)

# Strategy: valid integer numbers
_integer = st.integers(min_value=0, max_value=999999).map(str)

# Strategy: valid float numbers
_float_number = st.tuples(
    st.integers(min_value=0, max_value=9999),
    st.integers(min_value=0, max_value=9999),
).map(lambda t: f"{t[0]}.{t[1]}")

# Strategy: valid date literals (YYYY-MM-DD)
_date_literal = st.tuples(
    st.integers(min_value=1900, max_value=2100),
    st.integers(min_value=1, max_value=12),
    st.integers(min_value=1, max_value=28),
).map(lambda t: f"{t[0]:04d}-{t[1]:02d}-{t[2]:02d}")

# Strategy: operator characters
_operator = st.sampled_from(sorted(TJ_OPERATORS))


class TestTJTokenizerClassification:
    """Property 5: TJ tokenizer classification.

    **Validates: Requirements 3.2**
    """

    @given(keyword=_tj_keyword)
    @settings(max_examples=100)
    def test_keywords_classified_as_keyword(self, keyword: str) -> None:
        """Any known TJ keyword is classified as 'keyword'."""
        assert classify_tj_token(keyword) == "keyword"

    @given(body=_comment_body)
    @settings(max_examples=100)
    def test_hash_comment_classified_as_comment(self, body: str) -> None:
        """Any string starting with '#' followed by arbitrary text is classified as 'comment'."""
        token = f"#{body}"
        assert classify_tj_token(token) == "comment"

    @given(body=_comment_body)
    @settings(max_examples=100)
    def test_slash_comment_classified_as_comment(self, body: str) -> None:
        """Any string starting with '//' followed by arbitrary text is classified as 'comment'."""
        token = f"//{body}"
        assert classify_tj_token(token) == "comment"

    @given(content=_double_quote_content)
    @settings(max_examples=100)
    def test_double_quoted_string_classified_as_string(self, content: str) -> None:
        """Any string wrapped in double quotes is classified as 'string'."""
        token = f'"{content}"'
        assert classify_tj_token(token) == "string"

    @given(content=_single_quote_content)
    @settings(max_examples=100)
    def test_single_quoted_string_classified_as_string(self, content: str) -> None:
        """Any string wrapped in single quotes is classified as 'string'."""
        token = f"'{content}'"
        assert classify_tj_token(token) == "string"

    @given(number=_integer)
    @settings(max_examples=100)
    def test_integer_classified_as_number(self, number: str) -> None:
        """Any valid integer is classified as 'number'."""
        assert classify_tj_token(number) == "number"

    @given(number=_float_number)
    @settings(max_examples=100)
    def test_float_classified_as_number(self, number: str) -> None:
        """Any valid float number is classified as 'number'."""
        assert classify_tj_token(number) == "number"

    @given(date=_date_literal)
    @settings(max_examples=100)
    def test_date_literal_classified_as_number(self, date: str) -> None:
        """Any valid date literal (YYYY-MM-DD) is classified as 'number'."""
        assert classify_tj_token(date) == "number"

    @given(op=_operator)
    @settings(max_examples=100)
    def test_operator_classified_as_operator(self, op: str) -> None:
        """Any operator character is classified as 'operator'."""
        assert classify_tj_token(op) == "operator"
