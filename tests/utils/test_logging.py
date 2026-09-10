"""``vkt_bot.logging_setup``: маскирование, уровни, сборка обработчиков."""

from __future__ import annotations

import json
import logging
import logging.handlers
from typing import TYPE_CHECKING, Any

import pytest
import structlog

from vkt_bot.logging_setup import (
    apply_levels,
    build_formatter,
    build_processors,
    copy_event_to_message,
    init_logging,
    mask_secrets,
    mask_string,
    mask_url,
    mask_value,
    parse_log_levels,
    service_context,
    use_json,
)

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def _restore_logging() -> Iterator[None]:
    """Вернуть конфигурацию логирования и structlog после теста.

    ``init_logging`` сносит обработчики root и перенастраивает structlog —
    без восстановления следующий тест остался бы без ``caplog``.
    """
    root = logging.getLogger()
    handlers = root.handlers[:]
    level = root.level
    structlog_config = structlog.get_config()
    levels = {
        name: logging.getLogger(name).level
        for name in ("vkt_bot", "vkt_dispatcher", "vkteams_client", "vkt_gitlab")
    }
    yield
    root.handlers[:] = handlers
    root.setLevel(level)
    structlog.configure(**structlog_config)
    for name, saved in levels.items():
        logging.getLogger(name).setLevel(saved)


class TestMaskString:
    """``mask_string``."""

    def test_replaces_every_char(self) -> None:
        assert mask_string("secret") == "******"

    def test_empty_string(self) -> None:
        assert mask_string("") == ""


class TestMaskUrl:
    """``mask_url``."""

    def test_password_is_masked(self) -> None:
        masked = mask_url("postgresql://user:hunter2@localhost:5432/db")
        assert "hunter2" not in masked
        assert "user" in masked

    def test_host_and_port_survive(self) -> None:
        masked = mask_url("postgresql://user:pwd@db.internal:5432/vkt")
        assert "db.internal" in masked
        assert "5432" in masked

    def test_database_survives(self) -> None:
        assert mask_url("postgresql://u:p@host:5432/vkt").endswith("/vkt")

    def test_no_credentials(self) -> None:
        masked = mask_url("postgresql://localhost:5432/vkt")
        assert "localhost" in masked


class TestMaskValue:
    """``mask_value`` — рекурсивное маскирование."""

    def test_secret_key_is_masked(self) -> None:
        assert mask_value({"bot_token": "001.x"}) == {"bot_token": MASKED}

    def test_key_match_is_case_insensitive_and_partial(self) -> None:
        masked = mask_value({"Authorization": "Bearer x", "api_key_new": "k"})
        assert masked == {"Authorization": MASKED, "api_key_new": MASKED}

    def test_ordinary_keys_survive(self) -> None:
        assert mask_value({"chat_id": "c1"}) == {"chat_id": "c1"}

    def test_nested_structures(self) -> None:
        masked = mask_value({"body": {"items": [{"password": "p", "id": 1}]}})
        assert masked["body"]["items"][0] == {"password": MASKED, "id": 1}

    def test_numbers_under_secret_looking_keys_survive(self) -> None:
        """``access_token_expire_minutes`` — это число минут, а не секрет."""
        assert mask_value({"access_token_expire_minutes": 11520}) == {
            "access_token_expire_minutes": 11520
        }

    def test_token_in_query_string(self) -> None:
        masked = mask_value({"url": "https://api/x?token=001.abc&chatId=c1"})
        assert masked["url"] == f"https://api/x?token={MASKED}&chatId=c1"

    def test_deep_recursion_stops(self) -> None:
        deep: dict[str, Any] = {"password": "p"}
        for _ in range(10):
            deep = {"level": deep}
        # Не падает и не зацикливается; на предельной глубине маскировка
        # уже не работает — это осознанный предел.
        mask_value(deep)


MASKED = "***"


class TestMaskSecretsProcessor:
    """``mask_secrets`` как процессор structlog."""

    def test_masks_event_dict(self) -> None:
        result = mask_secrets(None, "info", {"event": "x", "token": "001.x"})
        assert result == {"event": "x", "token": MASKED}

    def test_returns_new_mapping(self) -> None:
        original = {"event": "x", "token": "001.x"}
        mask_secrets(None, "info", original)
        assert original["token"] == "001.x"


class TestServiceContext:
    """``service_context``."""

    def test_adds_fields(self) -> None:
        processor = service_context("vkt-bot", "prod", "1.2.3")
        assert processor(None, "info", {}) == {
            "service": "vkt-bot",
            "env": "prod",
            "version": "1.2.3",
        }

    def test_does_not_override_explicit_values(self) -> None:
        processor = service_context("vkt-bot", "prod", "1.2.3")
        assert processor(None, "info", {"env": "test"})["env"] == "test"


class TestCopyEventToMessage:
    """``copy_event_to_message``."""

    def test_duplicates_event(self) -> None:
        assert copy_event_to_message(None, "info", {"event": "message.sent"}) == {
            "event": "message.sent",
            "message": "message.sent",
        }

    def test_keeps_existing_message(self) -> None:
        result = copy_event_to_message(None, "info", {"event": "e", "message": "m"})
        assert result["message"] == "m"

    def test_without_event(self) -> None:
        assert copy_event_to_message(None, "info", {"a": 1}) == {"a": 1}


class TestParseLogLevels:
    """``parse_log_levels``."""

    def test_single_pair(self) -> None:
        assert parse_log_levels("sqlalchemy.engine=WARNING") == (
            {"sqlalchemy.engine": "WARNING"},
            [],
        )

    def test_several_pairs_and_spaces(self) -> None:
        levels, problems = parse_log_levels(" a=info , b=DEBUG ")
        assert levels == {"a": "INFO", "b": "DEBUG"}
        assert problems == []

    def test_empty_string(self) -> None:
        assert parse_log_levels("") == ({}, [])

    def test_unknown_level_is_reported(self) -> None:
        levels, problems = parse_log_levels("a=LOUD")
        assert levels == {}
        assert problems == ["a=LOUD"]

    def test_missing_separator_is_reported(self) -> None:
        assert parse_log_levels("justaname")[1] == ["justaname"]

    def test_good_pairs_survive_a_bad_one(self) -> None:
        levels, problems = parse_log_levels("a=DEBUG,broken,b=ERROR")
        assert levels == {"a": "DEBUG", "b": "ERROR"}
        assert problems == ["broken"]


class TestUseJson:
    """``use_json``."""

    def test_explicit_json(self) -> None:
        assert use_json("json") is True

    def test_explicit_console(self) -> None:
        assert use_json("console") is False

    def test_auto_without_tty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("sys.stdout.isatty", lambda: False)
        assert use_json("auto") is True

    def test_auto_with_tty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("sys.stdout.isatty", lambda: True)
        assert use_json("auto") is False


class TestBuildProcessors:
    """``build_processors``."""

    def test_service_fields_only_in_json(self) -> None:
        args = {"service": "s", "env": "local", "version": "1"}
        console = build_processors(json_output=False, **args)
        json_chain = build_processors(json_output=True, **args)
        assert len(json_chain) > len(console)

    def test_masking_is_last(self) -> None:
        chain = build_processors(
            json_output=True, service="s", env="local", version="1"
        )
        assert chain[-1] is mask_secrets


class TestRendering:
    """Боевая цепочка целиком: запись stdlib → строка."""

    def make_record(self, **extra: object) -> logging.LogRecord:
        record = logging.LogRecord(
            name="vkt_bot.test",
            level=logging.INFO,
            pathname="/app/handler.py",
            lineno=42,
            msg="сообщение %s",
            args=("от библиотеки",),
            exc_info=None,
        )
        for key, value in extra.items():
            setattr(record, key, value)
        return record

    def formatter(self, *, json_output: bool) -> logging.Formatter:
        return build_formatter(
            json_output=json_output,
            colors=False,
            processors=build_processors(
                json_output=json_output, service="vkt-bot", env="local", version="1.0"
            ),
        )

    def test_foreign_record_becomes_json(self) -> None:
        payload = json.loads(
            self.formatter(json_output=True).format(self.make_record())
        )
        assert payload["event"] == "сообщение от библиотеки"
        assert payload["logger"] == "vkt_bot.test"
        assert payload["level"] == "info"
        assert payload["service"] == "vkt-bot"
        assert payload["message"] == payload["event"]

    def test_extra_fields_of_foreign_record(self) -> None:
        """Библиотеки передают структурные поля через ``extra=``."""
        formatted = self.formatter(json_output=True).format(
            self.make_record(chat_id="c1")
        )
        assert json.loads(formatted)["chat_id"] == "c1"

    def test_secrets_of_foreign_record_are_masked(self) -> None:
        formatted = self.formatter(json_output=True).format(
            self.make_record(api_key="key-1")
        )
        assert json.loads(formatted)["api_key"] == MASKED
        assert "key-1" not in formatted

    def test_json_output_is_single_line(self) -> None:
        try:
            msg = "боом"
            raise RuntimeError(msg)
        except RuntimeError:
            import sys

            record = self.make_record()
            record.exc_info = sys.exc_info()

        formatted = self.formatter(json_output=True).format(record)

        # Трейсбек уехал в поле: promtail режет вывод по переводам строк.
        assert "\n" not in formatted
        assert json.loads(formatted)["exception"][0]["exc_type"] == "RuntimeError"

    def test_traceback_has_no_locals(self) -> None:
        """Локальные переменные кадров в лог не выгружаются."""
        try:
            api_key = "не-должен-утечь"  # noqa: F841
            msg = "боом"
            raise RuntimeError(msg)
        except RuntimeError:
            import sys

            record = self.make_record()
            record.exc_info = sys.exc_info()

        assert "не-должен-утечь" not in self.formatter(json_output=True).format(record)

    def test_console_output_is_readable(self) -> None:
        formatted = self.formatter(json_output=False).format(self.make_record())
        assert "сообщение от библиотеки" in formatted
        assert "vkt_bot.test" in formatted


@pytest.mark.usefixtures("_restore_logging")
class TestInitLogging:
    """``init_logging``."""

    def test_single_stdout_handler(self, settings: Any) -> None:  # noqa: ANN401, ARG002
        init_logging()

        (handler,) = logging.getLogger().handlers
        assert isinstance(handler, logging.StreamHandler)
        assert isinstance(handler.formatter, structlog.stdlib.ProcessorFormatter)

    def test_app_loggers_get_configured_level(
        self,
        settings: Any,  # noqa: ANN401
    ) -> None:
        init_logging()

        assert (
            logging.getLogger("vkt_bot").level
            == logging.getLevelNamesMapping()[settings.logging]
        )
        # Чужой шум приглушён отдельно от уровня приложения.
        assert logging.getLogger("passlib").level == logging.ERROR

    def test_log_levels_override(
        self, settings: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:  # noqa: ANN401
        monkeypatch.setattr(settings, "log_levels", "vkt_bot=ERROR")

        init_logging()

        assert logging.getLogger("vkt_bot").level == logging.ERROR

    def test_structlog_routes_into_stdlib(self, settings: Any) -> None:  # noqa: ANN401, ARG002
        init_logging()

        config = structlog.get_config()
        assert isinstance(config["logger_factory"], structlog.stdlib.LoggerFactory)

    def test_file_handler_is_added_for_log_file(
        self,
        settings: Any,  # noqa: ANN401
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Any,  # noqa: ANN401
    ) -> None:
        log_file = tmp_path / "logs" / "bot.log"
        monkeypatch.setattr(settings, "log_file", log_file)

        init_logging()

        assert log_file.parent.exists()
        assert any(
            isinstance(handler, logging.handlers.RotatingFileHandler)
            for handler in logging.getLogger().handlers
        )

    def test_startup_line_masks_secrets(
        self, settings: Any, capsys: pytest.CaptureFixture[str]
    ) -> None:  # noqa: ANN401
        monkey_format = settings.log_format
        try:
            settings.log_format = "json"
            init_logging()
        finally:
            settings.log_format = monkey_format

        printed = capsys.readouterr().out
        assert settings.bot_token not in printed
        assert '"bot_token": "***"' in printed
        # Пароль базы не должен утечь, а хост — должен остаться.
        assert "postgres:postgres@" not in printed
        assert "app.settings" in printed

    def test_invalid_log_levels_are_reported(
        self,
        settings: Any,  # noqa: ANN401
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(settings, "log_levels", "broken")
        monkeypatch.setattr(settings, "log_format", "json")

        init_logging()

        assert "settings.log_levels_invalid" in capsys.readouterr().out


class TestApplyLevels:
    """``apply_levels`` отдельно от остальной настройки."""

    def test_returns_problems(
        self,
        settings: Any,  # noqa: ANN401
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "log_levels", "broken,vkt_bot=DEBUG")
        saved = logging.getLogger("vkt_bot").level
        try:
            assert apply_levels(settings) == ["broken"]
            assert logging.getLogger("vkt_bot").level == logging.DEBUG
        finally:
            logging.getLogger("vkt_bot").setLevel(saved)


class TestSetupSentry:
    """``setup_sentry``."""

    def test_noop_without_dsn(
        self,
        settings: Any,  # noqa: ANN401
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from vkt_bot.logging_setup import setup_sentry

        monkeypatch.setattr(settings, "sentry_dsn", None)
        setup_sentry()

    def test_initialises_sdk(
        self,
        settings: Any,  # noqa: ANN401
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import sentry_sdk

        from vkt_bot.logging_setup import setup_sentry

        captured: list[tuple[str, dict[str, Any]]] = []
        monkeypatch.setattr(settings, "sentry_dsn", "https://key@sentry.local/1")
        monkeypatch.setattr(
            sentry_sdk,
            "init",
            lambda dsn, **kwargs: captured.append((dsn, kwargs)),
        )

        setup_sentry()

        (dsn, kwargs) = captured[0]
        assert dsn == "https://key@sentry.local/1"
        # Без окружения и версии события всех стендов сливаются в одну кучу.
        assert kwargs["environment"] == settings.env
        assert kwargs["release"]
