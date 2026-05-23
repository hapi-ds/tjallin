"""Unit tests for startup validation and initialization logic.

Tests that the system can start with default values when .env is not present,
and that the shared validation script provides sensible defaults for all
required environment variables.

Validates: Requirements 2.3, 2.5, 2.6, 7.4
"""

import os

import pytest

from tj_utils.validate_env import validate_env, validate_required_vars


class TestDefaultsWithoutEnvFile:
    """Test that the system provides working defaults when .env is absent (Req 2.3)."""

    def test_validate_env_with_defaults_passes(self):
        """When all required vars have default values, validation passes."""
        env = {
            "TJ_SMTP_HOST": "localhost",
            "TJ_SMTP_PORT": "25",
            "TJ_MAIL_DOMAIN": "taskjuggler.local",
        }
        result = validate_env(env)
        assert result.valid is True
        assert result.errors == []

    def test_validate_env_with_all_defaults(self):
        """Full default configuration produces a valid result."""
        env = {
            "TJ_PROJECT_PATH": "./project",
            "TJ_PROJECT_FILE": "project.tjp",
            "TJ_WEB_PORT": "8080",
            "TJ_MAIL_DOMAIN": "taskjuggler.local",
            "TJ_SMTP_HOST": "localhost",
            "TJ_SMTP_PORT": "25",
            "TJ_TIMEZONE": "UTC",
            "TJ_LOG_LEVEL": "INFO",
            "TJ_TASK_TIMEOUT": "300",
        }
        result = validate_env(env)
        assert result.valid is True
        assert result.errors == []
        assert result.effective_log_level == "INFO"


class TestRequiredVarsValidation:
    """Test that required env vars are validated before service start (Req 2.5, 2.6)."""

    def test_missing_smtp_host_produces_error(self):
        """Missing TJ_SMTP_HOST is reported as an error."""
        env = {"TJ_SMTP_PORT": "587", "TJ_MAIL_DOMAIN": "example.com"}
        errors = validate_required_vars(env)
        assert any("TJ_SMTP_HOST" in e for e in errors)

    def test_missing_smtp_port_produces_error(self):
        """Missing TJ_SMTP_PORT is reported as an error."""
        env = {"TJ_SMTP_HOST": "smtp.example.com", "TJ_MAIL_DOMAIN": "example.com"}
        errors = validate_required_vars(env)
        assert any("TJ_SMTP_PORT" in e for e in errors)

    def test_missing_mail_domain_produces_error(self):
        """Missing TJ_MAIL_DOMAIN is reported as an error."""
        env = {"TJ_SMTP_HOST": "smtp.example.com", "TJ_SMTP_PORT": "587"}
        errors = validate_required_vars(env)
        assert any("TJ_MAIL_DOMAIN" in e for e in errors)

    def test_empty_required_var_produces_error(self):
        """Empty string for a required var is treated as missing."""
        env = {"TJ_SMTP_HOST": "", "TJ_SMTP_PORT": "587", "TJ_MAIL_DOMAIN": "example.com"}
        errors = validate_required_vars(env)
        assert any("TJ_SMTP_HOST" in e for e in errors)

    def test_all_required_vars_present_no_errors(self):
        """When all required vars are present and non-empty, no errors."""
        env = {
            "TJ_SMTP_HOST": "smtp.example.com",
            "TJ_SMTP_PORT": "587",
            "TJ_MAIL_DOMAIN": "example.com",
        }
        errors = validate_required_vars(env)
        assert errors == []

    def test_multiple_missing_vars_all_reported(self):
        """All missing required vars are reported in a single validation pass."""
        env = {}
        errors = validate_required_vars(env)
        assert len(errors) == 3
        error_text = " ".join(errors)
        assert "TJ_SMTP_HOST" in error_text
        assert "TJ_SMTP_PORT" in error_text
        assert "TJ_MAIL_DOMAIN" in error_text


class TestSharedValidateEnvScript:
    """Test the shared validate-env.sh script provides defaults (Req 2.3, 7.4)."""

    @pytest.fixture
    def script_path(self):
        """Path to the shared validation script."""
        return os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "services",
            "shared",
            "validate-env.sh",
        )

    def test_script_exists(self, script_path):
        """The shared validation script exists."""
        assert os.path.isfile(script_path), f"Script not found at {script_path}"

    def test_script_sets_default_smtp_host(self, script_path):
        """Script defines a default for TJ_SMTP_HOST (localhost)."""
        with open(script_path) as f:
            content = f.read()
        assert 'TJ_SMTP_HOST="${TJ_SMTP_HOST:-localhost}"' in content

    def test_script_sets_default_smtp_port(self, script_path):
        """Script defines a default for TJ_SMTP_PORT (25)."""
        with open(script_path) as f:
            content = f.read()
        assert 'TJ_SMTP_PORT="${TJ_SMTP_PORT:-25}"' in content

    def test_script_sets_default_mail_domain(self, script_path):
        """Script defines a default for TJ_MAIL_DOMAIN (taskjuggler.local)."""
        with open(script_path) as f:
            content = f.read()
        assert 'TJ_MAIL_DOMAIN="${TJ_MAIL_DOMAIN:-taskjuggler.local}"' in content

    def test_script_sets_default_project_file(self, script_path):
        """Script defines a default for TJ_PROJECT_FILE (project.tjp)."""
        with open(script_path) as f:
            content = f.read()
        assert 'TJ_PROJECT_FILE="${TJ_PROJECT_FILE:-project.tjp}"' in content

    def test_script_sets_default_web_port(self, script_path):
        """Script defines a default for TJ_WEB_PORT (8080)."""
        with open(script_path) as f:
            content = f.read()
        assert 'TJ_WEB_PORT="${TJ_WEB_PORT:-8080}"' in content

    def test_script_sets_default_log_level(self, script_path):
        """Script defines a default for TJ_LOG_LEVEL (INFO)."""
        with open(script_path) as f:
            content = f.read()
        assert 'TJ_LOG_LEVEL="${TJ_LOG_LEVEL:-INFO}"' in content

    def test_script_sets_default_timezone(self, script_path):
        """Script defines a default for TJ_TIMEZONE (UTC)."""
        with open(script_path) as f:
            content = f.read()
        assert 'TJ_TIMEZONE="${TJ_TIMEZONE:-UTC}"' in content

    def test_script_validates_log_level(self, script_path):
        """Script validates TJ_LOG_LEVEL and falls back to INFO if invalid."""
        with open(script_path) as f:
            content = f.read()
        # Script should check against valid levels and fall back
        assert "VALID_LOG_LEVELS" in content or "DEBUG INFO WARNING ERROR" in content
        assert 'TJ_LOG_LEVEL="INFO"' in content  # fallback assignment

    def test_script_validates_port_number(self, script_path):
        """Script validates TJ_WEB_PORT is a valid port number."""
        with open(script_path) as f:
            content = f.read()
        assert "65535" in content  # port range check

    def test_script_uses_bash_default_syntax(self, script_path):
        """Script uses ${VAR:-default} syntax to preserve existing values."""
        with open(script_path) as f:
            content = f.read()
        # All defaults use the :- syntax which preserves existing values
        assert ":-" in content
        # Should not unconditionally overwrite
        assert "TJ_SMTP_HOST=" not in content.replace(
            'TJ_SMTP_HOST="${TJ_SMTP_HOST:-localhost}"', ""
        )


class TestVolumeInitialization:
    """Test that volume initialization works on first start (Req 7.4).

    Docker named volumes are initialized automatically by Docker on first start.
    The entrypoint scripts create required subdirectories within volumes.
    Subsequent starts reuse existing volumes without re-initialization.
    """

    def test_tj_mail_dockerfile_creates_timesheets_dir(self):
        """The tj-mail Dockerfile creates /app/timesheets at build time.

        This is verified by checking the Dockerfile contains mkdir -p /app/timesheets.
        """
        dockerfile_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "services",
            "tj-mail",
            "Dockerfile",
        )
        with open(dockerfile_path) as f:
            content = f.read()
        assert "/app/timesheets" in content

    def test_docker_compose_uses_named_volumes(self):
        """docker-compose.yml defines named volumes for persistent data."""
        compose_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "docker-compose.yml",
        )
        with open(compose_path) as f:
            content = f.read()
        # Named volumes are defined at the top level
        assert "report-data:" in content
        assert "timesheet-data:" in content
        assert "mail-spool:" in content

    def test_docker_compose_env_file_optional(self):
        """docker-compose.yml marks .env as optional so system starts without it."""
        compose_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "docker-compose.yml",
        )
        with open(compose_path) as f:
            content = f.read()
        assert "required: false" in content
