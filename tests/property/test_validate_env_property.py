"""Property-based tests for environment variable validation.

**Validates: Requirements 2.5, 2.6**

Property 1: Environment validation rejects missing required variables with descriptive error.
- When any required variable (TJ_SMTP_HOST, TJ_SMTP_PORT, TJ_MAIL_DOMAIN) is missing or empty,
  the validation result must be invalid and the error messages must name all missing/empty variables.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from tj_utils.validate_env import (
    REQUIRED_ENV_VARS,
    validate_env,
    validate_required_vars,
)

# Strategy for values that count as "present and valid" (non-empty, non-whitespace strings)
_valid_value = st.text(
    alphabet=st.characters(categories=("L", "N", "P", "S"), exclude_characters="\x00"),
    min_size=1,
).filter(lambda s: s.strip() != "")

# Strategy for values that count as "empty" (None, empty string, or whitespace-only)
_empty_value = st.one_of(
    st.none(),
    st.just(""),
    st.text(alphabet=st.just(" "), min_size=1, max_size=10),  # whitespace-only
)

# Strategy for a subset selection of required vars (at least one must be missing/empty)
_required_vars = list(REQUIRED_ENV_VARS)


@st.composite
def env_with_missing_required(draw: st.DrawFn) -> tuple[dict[str, str | None], set[str]]:
    """Generate an env dict where at least one required var is missing or empty.

    Returns a tuple of (env_dict, set_of_missing_var_names).
    """
    env: dict[str, str | None] = {}
    missing: set[str] = set()

    # For each required var, randomly decide if it's present, missing (absent), or empty
    for var in _required_vars:
        choice = draw(st.sampled_from(["present", "absent", "empty"]))
        if choice == "present":
            env[var] = draw(_valid_value)
        elif choice == "absent":
            # Key not in dict at all
            missing.add(var)
        else:
            # Key present but empty/whitespace
            env[var] = draw(_empty_value)
            missing.add(var)

    # Ensure at least one required var is missing/empty
    if not missing:
        # Force one to be missing
        var_to_remove = draw(st.sampled_from(_required_vars))
        choice = draw(st.sampled_from(["absent", "empty"]))
        if choice == "absent":
            env.pop(var_to_remove, None)
        else:
            env[var_to_remove] = draw(_empty_value)
        missing.add(var_to_remove)

    # Add some random extra keys to make the dict more realistic
    extra_keys = draw(
        st.dictionaries(
            keys=st.text(min_size=1, max_size=20).filter(lambda k: k not in _required_vars),
            values=st.text(max_size=50),
            max_size=5,
        )
    )
    env.update(extra_keys)

    return env, missing


@st.composite
def env_with_all_required_present(draw: st.DrawFn) -> dict[str, str]:
    """Generate an env dict where all required vars are present and non-empty."""
    env: dict[str, str] = {}
    for var in _required_vars:
        env[var] = draw(_valid_value)

    # Add some random extra keys
    extra_keys = draw(
        st.dictionaries(
            keys=st.text(min_size=1, max_size=20).filter(lambda k: k not in _required_vars),
            values=st.text(max_size=50),
            max_size=5,
        )
    )
    env.update(extra_keys)

    return env


class TestEnvValidationRejectsMissingRequired:
    """Property 1: Environment validation rejects missing required variables with descriptive error.

    **Validates: Requirements 2.5, 2.6**
    """

    @given(data=env_with_missing_required())
    @settings(max_examples=100)
    def test_missing_required_vars_produce_errors(
        self, data: tuple[dict[str, str | None], set[str]]
    ) -> None:
        """When required vars are missing/empty, validate_required_vars returns errors naming them."""
        env, missing_vars = data

        # Filter out None values from env for the function call (simulates absent keys)
        clean_env = {k: v for k, v in env.items() if v is not None}

        errors = validate_required_vars(clean_env)

        # Must have at least one error for each missing/empty var
        assert len(errors) >= len(missing_vars), (
            f"Expected at least {len(missing_vars)} errors for missing vars {missing_vars}, "
            f"got {len(errors)}: {errors}"
        )

        # Each missing var name must appear in at least one error message
        for var in missing_vars:
            assert any(var in err for err in errors), (
                f"Expected variable name '{var}' in error messages, got: {errors}"
            )

    @given(data=env_with_missing_required())
    @settings(max_examples=100)
    def test_validate_env_marks_invalid_when_required_missing(
        self, data: tuple[dict[str, str | None], set[str]]
    ) -> None:
        """When required vars are missing/empty, validate_env returns result with valid=False."""
        env, missing_vars = data

        # Filter out None values (simulates absent keys)
        clean_env = {k: v for k, v in env.items() if v is not None}

        result = validate_env(clean_env)

        # Result must be invalid
        assert result.valid is False, (
            f"Expected valid=False for missing vars {missing_vars}, "
            f"but got valid=True with errors={result.errors}"
        )

        # Errors must name all missing/empty required variables
        for var in missing_vars:
            assert any(var in err for err in result.errors), (
                f"Expected variable name '{var}' in result.errors, got: {result.errors}"
            )

    @given(env=env_with_all_required_present())
    @settings(max_examples=100)
    def test_all_required_present_produces_no_required_var_errors(
        self, env: dict[str, str]
    ) -> None:
        """When all required vars are present and non-empty, validate_required_vars returns no errors."""
        errors = validate_required_vars(env)
        assert errors == [], (
            f"Expected no errors when all required vars are present, got: {errors}"
        )
