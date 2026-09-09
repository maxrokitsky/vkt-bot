"""Настройки и фабрика сессий — инфраструктура тестируемости."""

from __future__ import annotations

import subprocess
import sys
import textwrap
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from vkt_bot.config import VktSettings, get_settings

if TYPE_CHECKING:
    import pathlib


REQUIRED_ENV = {
    "LOGGING": "INFO",
    "BOT_TOKEN": "token",
    "DB_URL": "postgresql+psycopg://u:p@localhost:5432/db",
    "SECRET_KEY": "secret",
}
REQUIRED_KWARGS = {key.lower(): value for key, value in REQUIRED_ENV.items()}


def run_python(
    code: str, env: dict[str, str], cwd: pathlib.Path
) -> subprocess.CompletedProcess[str]:
    """Запустить код в отдельном процессе с заданным окружением."""
    return subprocess.run(  # noqa: S603
        [sys.executable, "-c", textwrap.dedent(code)],
        capture_output=True,
        text=True,
        check=False,
        env={"PATH": "/usr/bin:/bin", "PYTHONPATH": ":".join(sys.path), **env},
        cwd=cwd,
    )


class TestSettingsSchema:
    """``VktSettings``."""

    def test_required_fields(self) -> None:
        settings = VktSettings(_env_file=None, **REQUIRED_KWARGS)  # type: ignore[call-arg]

        assert settings.bot_token == "token"
        assert settings.secret_key == "secret"
        assert settings.logging == "INFO"

    def test_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for name in ("OWNER_ID", "PUBLIC_URL", "SENTRY_DSN", "LOG_FILE"):
            monkeypatch.delenv(name, raising=False)
        settings = VktSettings(_env_file=None, **REQUIRED_KWARGS)  # type: ignore[call-arg]

        assert settings.owner_id is None
        assert settings.log_file is None
        assert settings.sentry_dsn is None
        assert settings.public_url is None
        assert settings.rabbitmq_logging == "INFO"
        assert settings.access_token_expire_minutes == 60 * 24 * 8
        assert settings.max_file_size == 50 * 1024 * 1024

    @pytest.mark.parametrize("field", ["logging", "bot_token", "db_url", "secret_key"])
    def test_missing_required_field_raises(
        self, field: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(field.upper(), raising=False)
        kwargs = {k: v for k, v in REQUIRED_KWARGS.items() if k != field}
        with pytest.raises(ValidationError, match=field):
            VktSettings(_env_file=None, **kwargs)  # type: ignore[call-arg]

    def test_unknown_log_level_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            VktSettings(_env_file=None, **{**REQUIRED_KWARGS, "logging": "TRACE"})  # type: ignore[call-arg]

    def test_non_postgres_dsn_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            VktSettings(_env_file=None, **{**REQUIRED_KWARGS, "db_url": "sqlite:///x"})  # type: ignore[call-arg]

    def test_extra_env_vars_are_ignored(self) -> None:
        settings = VktSettings(_env_file=None, **{**REQUIRED_KWARGS, "something": "x"})  # type: ignore[call-arg]
        assert not hasattr(settings, "something")

    def test_allowed_file_types_default(self) -> None:
        settings = VktSettings(_env_file=None, **REQUIRED_KWARGS)  # type: ignore[call-arg]
        assert "application/pdf" in settings.allowed_file_types


class TestGetSettings:
    """``get_settings``."""

    def test_returns_settings(self) -> None:
        assert isinstance(get_settings(), VktSettings)

    def test_result_is_cached(self) -> None:
        assert get_settings() is get_settings()

    def test_module_attribute_is_the_same_object(self) -> None:
        from vkt_bot.config import settings

        assert settings is get_settings()

    def test_unknown_module_attribute_raises(self) -> None:
        import vkt_bot.config

        with pytest.raises(AttributeError):
            _ = vkt_bot.config.does_not_exist


class TestImportWithoutEnv:
    """Импорт без окружения не должен убивать процесс.

    Раньше ``config.py`` вызывал ``sys.exit(1)`` на уровне модуля, из-за
    чего pytest падал целиком (ROADMAP 1.0).
    """

    def test_import_succeeds(self, tmp_path: pathlib.Path) -> None:
        result = run_python(
            """
            import vkt_bot.config
            import vkt_bot.db.session
            print("ok")
            """,
            env={},
            cwd=tmp_path,
        )

        assert result.returncode == 0, result.stderr
        assert "ok" in result.stdout

    def test_get_settings_raises_validation_error(self, tmp_path: pathlib.Path) -> None:
        result = run_python(
            """
            from pydantic import ValidationError
            from vkt_bot.config import get_settings
            try:
                get_settings()
            except ValidationError:
                print("validation-error")
            """,
            env={},
            cwd=tmp_path,
        )

        assert result.returncode == 0, result.stderr
        assert "validation-error" in result.stdout

    def test_importing_handlers_does_not_exit(self, tmp_path: pathlib.Path) -> None:
        """Модули приложения импортируются без ``.env``."""
        result = run_python(
            """
            import vkt_bot.db.repository
            import vkt_bot.db.query
            import vkt_bot.core.models
            import vkteams_client
            import vkt_dispatcher
            print("ok")
            """,
            env={},
            cwd=tmp_path,
        )

        assert result.returncode == 0, result.stderr
        assert "ok" in result.stdout


class TestCheckSettings:
    """``main.check_settings`` — единственная точка выхода."""

    def test_exits_with_code_1_without_env(self, tmp_path: pathlib.Path) -> None:
        result = run_python(
            """
            from vkt_bot.main import check_settings
            check_settings()
            print("не должно напечататься")
            """,
            env={},
            cwd=tmp_path,
        )

        assert result.returncode == 1
        assert "не должно напечататься" not in result.stdout
        assert "validation error" in result.stderr.lower()

    def test_passes_with_env(self, tmp_path: pathlib.Path) -> None:
        result = run_python(
            """
            from vkt_bot.main import check_settings
            check_settings()
            print("ok")
            """,
            env=REQUIRED_ENV,
            cwd=tmp_path,
        )

        assert result.returncode == 0, result.stderr
        assert "ok" in result.stdout
