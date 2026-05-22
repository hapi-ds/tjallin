"""Unit tests for environment variable validation."""

import pytest

from tj_utils.validate_env import (
    REQUIRED_ENV_VARS,
    VALID_LOG_LEVELS,
    EnvValidationResult,
    TJEnvironment,
    validate_env,
    validate_log_level,
    validate_port,
    validate_required_vars,
    validate_timezone,
)


class TestValidateRequiredVars:
    """Tests for validate_required_vars function."""

    def test_all_required_present(self):
        env = {
            "TJ_SMTP_HOST": "smtp.example.com",
            "TJ_SMTP_PORT": "587",
            "TJ_MAIL_DOMAIN": "example.com",
        }
        errors = validate_required_vars(env)
        assert errors == []

    def test_missing_smtp_host(self):
        env = {"TJ_SMTP_PORT": "587", "TJ_MAIL_DOMAIN": "example.com"}
        errors = validate_required_vars(env)
        assert len(errors) == 1
        assert "TJ_SMTP_HOST" in errors[0]

    def test_empty_smtp_host(self):
        env = {
            "TJ_SMTP_HOST": "",
            "TJ_SMTP_PORT": "587",
            "TJ_MAIL_DOMAIN": "example.com",
        }
        errors = validate_required_vars(env)
        assert len(errors) == 1
        assert "TJ_SMTP_HOST" in errors[0]

    def test_whitespace_only_value(self):
        env = {
            "TJ_SMTP_HOST": "   ",
            "TJ_SMTP_PORT": "587",
            "TJ_MAIL_DOMAIN": "example.com",
        }
        errors = validate_required_vars(env)
        assert len(errors) == 1
        assert "TJ_SMTP_HOST" in errors[0]

    def test_all_missing(self):
        env = {}
        errors = validate_required_vars(env)
        assert len(errors) == 3
        for var in REQUIRED_ENV_VARS:
            assert any(var in e for e in errors)

    def test_multiple_missing(self):
        env = {"TJ_SMTP_HOST": "smtp.example.com"}
        errors = validate_required_vars(env)
        assert len(errors) == 2


class TestValidatePort:
    """Tests for validate_port function."""

    def test_valid_port(self):
        port, error = validate_port("8080")
        assert port == 8080
        assert error is None

    def test_min_port(self):
        port, error = validate_port("1")
        assert port == 1
        assert error is None

    def test_max_port(self):
        port, error = validate_port("65535")
        assert port == 65535
        assert error is None

    def test_port_zero(self):
        port, error = validate_port("0")
        assert port is None
        assert error is not None
        assert "1 and 65535" in error

    def test_port_too_high(self):
        port, error = validate_port("65536")
        assert port is None
        assert error is not None

    def test_non_numeric(self):
        port, error = validate_port("abc")
        assert port is None
        assert "valid integer" in error

    def test_none_value(self):
        port, error = validate_port(None)
        assert port is None
        assert error is None

    def test_integer_input(self):
        port, error = validate_port(443)
        assert port == 443
        assert error is None


class TestValidateLogLevel:
    """Tests for validate_log_level function."""

    def test_valid_levels(self):
        for level in VALID_LOG_LEVELS:
            effective, warning = validate_log_level(level)
            assert effective == level
            assert warning is None

    def test_case_insensitive(self):
        effective, warning = validate_log_level("debug")
        assert effective == "DEBUG"
        assert warning is None

    def test_invalid_level_falls_back(self):
        effective, warning = validate_log_level("TRACE")
        assert effective == "INFO"
        assert warning is not None
        assert "TRACE" in warning

    def test_none_defaults_to_info(self):
        effective, warning = validate_log_level(None)
        assert effective == "INFO"
        assert warning is None

    def test_empty_defaults_to_info(self):
        effective, warning = validate_log_level("")
        assert effective == "INFO"
        assert warning is None


class TestValidateTimezone:
    """Tests for validate_timezone function."""

    def test_valid_timezone(self):
        tz, error = validate_timezone("Europe/Stockholm")
        assert tz == "Europe/Stockholm"
        assert error is None

    def test_utc(self):
        tz, error = validate_timezone("UTC")
        assert tz == "UTC"
        assert error is None

    def test_invalid_timezone(self):
        tz, error = validate_timezone("Invalid/Timezone")
        assert error is not None
        assert "Invalid/Timezone" in error

    def test_none_defaults_to_utc(self):
        tz, error = validate_timezone(None)
        assert tz == "UTC"
        assert error is None

    def test_empty_defaults_to_utc(self):
        tz, error = validate_timezone("")
        assert tz == "UTC"
        assert error is None


class TestValidateEnv:
    """Tests for the main validate_env function."""

    def test_valid_complete_env(self):
        env = {
            "TJ_SMTP_HOST": "smtp.example.com",
            "TJ_SMTP_PORT": "587",
            "TJ_MAIL_DOMAIN": "example.com",
            "TJ_WEB_PORT": "8080",
            "TJ_LOG_LEVEL": "INFO",
            "TJ_TIMEZONE": "UTC",
        }
        result = validate_env(env)
        assert result.valid is True
        assert result.errors == []
        assert result.warnings == []
        assert result.effective_log_level == "INFO"

    def test_invalid_env_missing_required(self):
        env = {"TJ_WEB_PORT": "8080"}
        result = validate_env(env)
        assert result.valid is False
        assert len(result.errors) == 3

    def test_invalid_port_in_env(self):
        env = {
            "TJ_SMTP_HOST": "smtp.example.com",
            "TJ_SMTP_PORT": "587",
            "TJ_MAIL_DOMAIN": "example.com",
            "TJ_WEB_PORT": "99999",
        }
        result = validate_env(env)
        assert result.valid is False
        assert any("TJ_WEB_PORT" in e for e in result.errors)

    def test_invalid_log_level_produces_warning(self):
        env = {
            "TJ_SMTP_HOST": "smtp.example.com",
            "TJ_SMTP_PORT": "587",
            "TJ_MAIL_DOMAIN": "example.com",
            "TJ_LOG_LEVEL": "VERBOSE",
        }
        result = validate_env(env)
        assert result.valid is True
        assert result.effective_log_level == "INFO"
        assert len(result.warnings) == 1
        assert "VERBOSE" in result.warnings[0]


class TestTJEnvironment:
    """Tests for the Pydantic TJEnvironment model."""

    def test_valid_model(self):
        model = TJEnvironment(
            tj_smtp_host="smtp.example.com",
            tj_smtp_port=587,
            tj_mail_domain="example.com",
        )
        assert model.tj_smtp_host == "smtp.example.com"
        assert model.tj_web_port == 8080
        assert model.tj_log_level == "INFO"
        assert model.tj_timezone == "UTC"

    def test_empty_host_rejected(self):
        with pytest.raises(ValueError):
            TJEnvironment(
                tj_smtp_host="",
                tj_smtp_port=587,
                tj_mail_domain="example.com",
            )

    def test_invalid_port_rejected(self):
        with pytest.raises(ValueError):
            TJEnvironment(
                tj_smtp_host="smtp.example.com",
                tj_smtp_port=0,
                tj_mail_domain="example.com",
            )

    def test_invalid_timezone_rejected(self):
        with pytest.raises(ValueError):
            TJEnvironment(
                tj_smtp_host="smtp.example.com",
                tj_smtp_port=587,
                tj_mail_domain="example.com",
                tj_timezone="Not/A/Timezone",
            )

    def test_invalid_log_level_falls_back(self):
        model = TJEnvironment(
            tj_smtp_host="smtp.example.com",
            tj_smtp_port=587,
            tj_mail_domain="example.com",
            tj_log_level="TRACE",
        )
        assert model.tj_log_level == "INFO"
