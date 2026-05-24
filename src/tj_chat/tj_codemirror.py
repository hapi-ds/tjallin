"""TJ (TaskJuggler) CodeMirror language mode configuration.

Defines keyword lists, comment/string/number/operator patterns for
TaskJuggler syntax highlighting. Provides both a Python-side token
classifier (for testing) and a JavaScript CodeMirror 5 mode definition
(for browser-side highlighting via NiceGUI's ui.codemirror).
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Token pattern definitions
# ---------------------------------------------------------------------------

TJ_KEYWORDS: list[str] = [
    "task",
    "resource",
    "project",
    "account",
    "shift",
    "booking",
    "supplement",
    "include",
    "macro",
    "report",
    "timesheet",
    "journalentry",
    "vacation",
    "flags",
    "leaves",
    "limits",
    "allocate",
    "effort",
    "duration",
    "length",
    "start",
    "end",
    "period",
    "complete",
    "depends",
    "precedes",
    "priority",
    "scheduling",
    "responsible",
]

TJ_COMMENT_PATTERNS: dict[str, str] = {
    "line_hash": "#",
    "line_slash": "//",
    "block_start": "/*",
    "block_end": "*/",
}

TJ_STRING_PATTERNS: dict[str, str] = {
    "double_quote": '"',
    "single_quote": "'",
}

TJ_NUMBER_PATTERN: re.Pattern[str] = re.compile(
    r"^(\d{4}-\d{2}-\d{2}|\d+\.\d+|\d+)$"
)

TJ_OPERATORS: set[str] = {"{", "}", "!", "&", "|"}

# Pre-compiled set for fast keyword lookup
_TJ_KEYWORD_SET: set[str] = set(TJ_KEYWORDS)

# Regex for line comments (matches from comment start to end of string)
_LINE_COMMENT_RE: re.Pattern[str] = re.compile(r"^(#|//).*$")

# Regex for block comments (matches /* ... */ including multiline)
_BLOCK_COMMENT_RE: re.Pattern[str] = re.compile(r"^/\*.*\*/$", re.DOTALL)

# Regex for strings (double or single quoted, non-greedy)
_STRING_RE: re.Pattern[str] = re.compile(r'^(".*"|\'.*\')$', re.DOTALL)


def classify_tj_token(text: str) -> str | None:
    """Classify a text fragment as a TJ token type.

    Args:
        text: The text fragment to classify.

    Returns:
        One of "keyword", "comment", "string", "number", "operator",
        or None if the text does not match any known token pattern.
    """
    if not text:
        return None

    # Check for keyword (exact match, case-sensitive)
    if text in _TJ_KEYWORD_SET:
        return "keyword"

    # Check for line comments (# or //)
    if _LINE_COMMENT_RE.match(text):
        return "comment"

    # Check for block comments (/* ... */)
    if _BLOCK_COMMENT_RE.match(text):
        return "comment"

    # Check for strings (quoted)
    if _STRING_RE.match(text):
        return "string"

    # Check for numbers and date literals
    if TJ_NUMBER_PATTERN.match(text):
        return "number"

    # Check for operators
    if text in TJ_OPERATORS:
        return "operator"

    return None


# ---------------------------------------------------------------------------
# CodeMirror 5 mode JavaScript definition
# ---------------------------------------------------------------------------

def get_codemirror_mode_js() -> str:
    """Return JavaScript code that registers a 'tj' mode with CodeMirror 5.

    This JavaScript should be injected into the page (e.g. via
    `ui.add_body_html` or `ui.run_javascript`) before creating a
    CodeMirror editor that uses the 'tj' mode.

    Returns:
        A string of JavaScript that calls CodeMirror.defineMode("tj", ...).
    """
    keywords_js = ", ".join(f'"{kw}"' for kw in TJ_KEYWORDS)

    return f"""\
(function() {{
  if (typeof CodeMirror === 'undefined') return;
  if (CodeMirror.modes.tj) return;  // Already registered

  var keywords = new Set([{keywords_js}]);

  CodeMirror.defineMode("tj", function() {{
    return {{
      startState: function() {{
        return {{ inBlockComment: false, inString: false, stringChar: null }};
      }},

      token: function(stream, state) {{
        // Block comment continuation
        if (state.inBlockComment) {{
          if (stream.match("*/")) {{
            state.inBlockComment = false;
          }} else {{
            stream.next();
          }}
          return "comment";
        }}

        // String continuation
        if (state.inString) {{
          var ch = stream.next();
          if (ch === state.stringChar) {{
            state.inString = false;
            state.stringChar = null;
          }} else if (ch === "\\\\") {{
            stream.next();  // Skip escaped character
          }}
          return "string";
        }}

        // Skip whitespace
        if (stream.eatSpace()) return null;

        var ch = stream.peek();

        // Line comment: # or //
        if (ch === "#") {{
          stream.skipToEnd();
          return "comment";
        }}
        if (ch === "/" && stream.match("//")) {{
          stream.skipToEnd();
          return "comment";
        }}

        // Block comment start: /*
        if (ch === "/" && stream.match("/*")) {{
          state.inBlockComment = true;
          return "comment";
        }}

        // Strings
        if (ch === '"' || ch === "'") {{
          state.inString = true;
          state.stringChar = ch;
          stream.next();
          return "string";
        }}

        // Date literals: YYYY-MM-DD
        if (/\\d/.test(ch)) {{
          if (stream.match(/^\\d{{4}}-\\d{{2}}-\\d{{2}}/)) {{
            return "number";
          }}
          // Float or integer
          stream.match(/^\\d+\\.?\\d*/);
          return "number";
        }}

        // Operators
        if (ch === "{{" || ch === "}}" || ch === "!" || ch === "&" || ch === "|") {{
          stream.next();
          return "operator";
        }}

        // Words (identifiers / keywords)
        if (/[a-zA-Z_]/.test(ch)) {{
          stream.match(/^[a-zA-Z_][a-zA-Z0-9_]*/);
          var word = stream.current();
          if (keywords.has(word)) {{
            return "keyword";
          }}
          return null;
        }}

        // Consume any other character
        stream.next();
        return null;
      }}
    }};
  }});

  // Also register a MIME type
  CodeMirror.defineMIME("text/x-tj", "tj");
}})();
"""
