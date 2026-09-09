"""Чистые функции из ``vkt_bot.utils``."""

from __future__ import annotations

import datetime
import json
import logging
import logging.handlers
from typing import TYPE_CHECKING

import pytest
from pydantic_core import MultiHostUrl

from vkt_bot.utils.datetime import localize_datetime, now
from vkt_bot.utils.formatters import (
    LOG_RECORD_BUILTIN_ATTRS,
    ColorFormatter,
    JsonFormatter,
)
from vkt_bot.utils.log import import_logging, mask_string, mask_url
from vkt_bot.utils.message import mention

if TYPE_CHECKING:
    pass


class TestMention:
    """``mention``."""

    def test_wraps_user_id(self) -> None:
        assert mention("1234567890") == "@[1234567890]"

    def test_email_like_id(self) -> None:
        assert mention("user@example.com") == "@[user@example.com]"

    def test_empty_id(self) -> None:
        assert mention("") == "@[]"


class TestLocalizeDatetime:
    """``localize_datetime``."""

    def test_recent_past_in_russian(self) -> None:
        moment = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=2)
        assert localize_datetime(moment) == "2 часа назад"

    def test_future(self) -> None:
        moment = datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=3)
        assert "через" in localize_datetime(moment)

    def test_naive_datetime_is_treated_as_utc(self) -> None:
        moment = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
        assert localize_datetime(moment) in {"только что", "сейчас"}


class TestNow:
    """``now``."""

    def test_is_broken(self) -> None:
        """Известный дефект: ``datetime.datetime()`` вызывается без аргументов."""
        with pytest.raises(TypeError):
            now()


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
        assert "*******" in masked

    def test_username_host_and_port_are_kept(self) -> None:
        masked = mask_url("postgresql://user:pwd@db.internal:5432/vkt")

        assert "user" in masked
        assert "db.internal" in masked
        assert "5432" in masked

    def test_path_is_kept(self) -> None:
        assert mask_url("postgresql://u:p@host:5432/vkt").endswith("/vkt")

    def test_accepts_multi_host_url(self) -> None:
        url = MultiHostUrl("postgresql://u:p@host:5432/vkt")
        assert "p" not in mask_url(url).split("@")[0].split(":")[-1]

    def test_url_without_credentials(self) -> None:
        masked = mask_url("postgresql://localhost:5432/vkt")
        assert "localhost" in masked


class TestJsonFormatter:
    """``JsonFormatter``."""

    @pytest.fixture
    def formatter(self) -> JsonFormatter:
        return JsonFormatter(
            fmt_keys={"level": "levelname", "message": "message", "logger": "name"}
        )

    def make_record(self, **extra: object) -> logging.LogRecord:
        """Создать LogRecord."""
        record = logging.LogRecord(
            name="vkt_bot.test",
            level=logging.INFO,
            pathname="/app/handler.py",
            lineno=42,
            msg="Событие %s",
            args=("newMessage",),
            exc_info=None,
        )
        for key, value in extra.items():
            setattr(record, key, value)
        return record

    def test_output_is_json(self, formatter: JsonFormatter) -> None:
        payload = json.loads(formatter.format(self.make_record()))
        assert payload["level"] == "INFO"
        assert payload["message"] == "Событие newMessage"
        assert payload["logger"] == "vkt_bot.test"

    def test_always_present_fields(self, formatter: JsonFormatter) -> None:
        payload = json.loads(formatter.format(self.make_record()))
        assert payload["module_path"] == "handler.py"
        assert payload["pathname"] == "/app/handler.py"
        assert "timestamp" in payload

    def test_extra_fields_are_included(self, formatter: JsonFormatter) -> None:
        payload = json.loads(formatter.format(self.make_record(chat_id="chat-1")))
        assert payload["chat_id"] == "chat-1"

    def test_builtin_attrs_are_not_duplicated(self, formatter: JsonFormatter) -> None:
        payload = json.loads(formatter.format(self.make_record()))
        assert "levelno" not in payload
        assert "msecs" not in payload

    def test_non_ascii_is_not_escaped(self, formatter: JsonFormatter) -> None:
        output = formatter.format(self.make_record())
        assert "Событие" in output

    def test_exception_info(self, formatter: JsonFormatter) -> None:
        try:
            msg = "боом"
            raise RuntimeError(msg)
        except RuntimeError:
            import sys

            record = self.make_record()
            record.exc_info = sys.exc_info()

        payload = json.loads(formatter.format(record))
        assert "RuntimeError" in payload["exc_info"]

    def test_stack_info(self, formatter: JsonFormatter) -> None:
        record = self.make_record()
        record.stack_info = "Stack (most recent call last):\n  ..."
        payload = json.loads(formatter.format(record))
        assert "Stack" in payload["stack_info"]

    def test_non_serialisable_values_fall_back_to_str(
        self, formatter: JsonFormatter
    ) -> None:
        payload = json.loads(formatter.format(self.make_record(obj=object())))
        assert payload["obj"].startswith("<object object")

    def test_builtin_attrs_list_is_complete(self) -> None:
        assert "levelname" in LOG_RECORD_BUILTIN_ATTRS
        assert "taskName" in LOG_RECORD_BUILTIN_ATTRS


class TestColorFormatter:
    """``ColorFormatter``."""

    def make_record(self, level: int) -> logging.LogRecord:
        """Создать LogRecord нужного уровня."""
        return logging.LogRecord(
            name="vkt_bot.test",
            level=level,
            pathname="/app/handler.py",
            lineno=42,
            msg="сообщение",
            args=(),
            exc_info=None,
        )

    @pytest.mark.parametrize(
        ("level", "color"),
        [
            (logging.DEBUG, ColorFormatter.grey),
            (logging.INFO, ColorFormatter.grey),
            (logging.WARNING, ColorFormatter.yellow),
            (logging.ERROR, ColorFormatter.red),
            (logging.CRITICAL, ColorFormatter.bold_red),
        ],
    )
    def test_colour_per_level(self, level: int, color: str) -> None:
        output = ColorFormatter().format(self.make_record(level))
        assert output.startswith(color)
        assert output.endswith(ColorFormatter.reset)

    def test_message_and_location_are_present(self) -> None:
        output = ColorFormatter().format(self.make_record(logging.INFO))
        assert "сообщение" in output
        assert "/app/handler.py:42" in output

    def test_unknown_level_has_no_colour(self) -> None:
        output = ColorFormatter().format(self.make_record(5))
        assert not output.startswith(ColorFormatter.grey)


class TestLoggingConfig:
    """``logging.yaml``."""

    def test_config_loads(self) -> None:
        config = import_logging()
        assert config["version"] == 1

    def test_declares_expected_handlers(self) -> None:
        config = import_logging()
        assert set(config["handlers"]) >= {"stderr", "stdout", "file"}

    def test_json_formatter_is_wired(self) -> None:
        config = import_logging()
        assert (
            config["formatters"]["json"]["()"]
            == "vkt_bot.utils.formatters.JsonFormatter"
        )

    def test_root_uses_console_handlers(self) -> None:
        config = import_logging()
        assert config["root"]["handlers"] == ["stderr", "stdout"]


class TestInitLogging:
    """``init_logging`` и ``setup_sentry``."""

    @pytest.fixture(autouse=True)
    def _restore_logging(self) -> object:
        """Вернуть конфигурацию логирования после теста."""
        root = logging.getLogger()
        handlers = root.handlers[:]
        level = root.level
        yield
        root.handlers[:] = handlers
        root.setLevel(level)

    def test_applies_config(self, settings: object) -> None:
        from vkt_bot.utils.log import init_logging

        init_logging()

        assert logging.getLogger().handlers

    def test_logs_settings_masked(
        self,
        settings: object,
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import logging.config

        from vkt_bot.utils.log import init_logging

        # dictConfig снёс бы обработчик caplog вместе с остальными.
        monkeypatch.setattr(logging.config, "dictConfig", lambda config: None)
        with caplog.at_level("INFO", logger="vkt_bot.settings"):
            init_logging()

        messages = "\n".join(
            r.getMessage() for r in caplog.records if r.name == "vkt_bot.settings"
        )
        assert "bot_token: ***" in messages
        assert settings.bot_token not in messages
        assert "version:" in messages

    def test_unset_secrets_are_marked(
        self,
        settings: object,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        from vkt_bot.utils.log import init_logging

        import logging.config

        monkeypatch.setattr(logging.config, "dictConfig", lambda config: None)
        monkeypatch.setattr(settings, "sentry_dsn", None)
        with caplog.at_level("INFO", logger="vkt_bot.settings"):
            init_logging()

        messages = "\n".join(
            r.getMessage() for r in caplog.records if r.name == "vkt_bot.settings"
        )
        assert "sentry_dsn: <NOT_SET>" in messages

    def test_file_handler_is_added_for_log_file(
        self,
        settings: object,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: object,
    ) -> None:
        from vkt_bot.utils.log import init_logging

        log_file = tmp_path / "logs" / "bot.log"
        monkeypatch.setattr(settings, "log_file", log_file)

        init_logging()

        assert log_file.parent.exists()
        assert any(
            isinstance(h, logging.handlers.RotatingFileHandler)
            for h in logging.getLogger().handlers
        )

    def test_setup_sentry_is_a_noop_without_dsn(
        self, settings: object, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from vkt_bot.utils.log import setup_sentry

        monkeypatch.setattr(settings, "sentry_dsn", None)
        setup_sentry()

    def test_setup_sentry_initialises_sdk(
        self, settings: object, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import sentry_sdk

        from vkt_bot.utils.log import setup_sentry

        captured: list[str] = []
        monkeypatch.setattr(settings, "sentry_dsn", "https://key@sentry.local/1")
        monkeypatch.setattr(sentry_sdk, "init", lambda dsn: captured.append(dsn))

        setup_sentry()

        assert captured == ["https://key@sentry.local/1"]
