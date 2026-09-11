"""Сборка приложения без веб-сервера."""

from __future__ import annotations

import pytest

from vkt_bot import bootstrap as bootstrap_module
from vkt_bot.bootstrap import bootstrap
from vkt_bot.core.bot_events import record_bot_action
from vkt_bot.core.messages import record_outgoing
from vkt_bot.worker.broker import broker


@pytest.fixture(autouse=True)
def _built(app: object) -> None:  # noqa: ARG001
    """Приложение уже собрано фикстурой ``app`` — сборка идемпотентна."""
    bootstrap()


class TestBootstrap:
    """``bootstrap``."""

    def test_plugin_tasks_are_registered(self) -> None:
        """Воркер не знает про плагины — их приносит сборка."""
        assert broker.find_task("vkt_ai.run_session") is not None

    def test_bot_sinks_are_wired(self) -> None:
        """В воркере бот тоже пишет свои сообщения в историю чата.

        Ответы агента отправляет уже другой процесс, и клиент там свой:
        без этого переписка осталась бы с дырами, а действия бота — вне
        журнала. Самая незаметная из возможных регрессий.
        """
        import vkt_bot.app as app_module

        assert app_module.bot.event_sink is record_bot_action
        assert app_module.bot.message_sink is record_outgoing

    def test_no_fastapi_needed(self) -> None:
        """Роутеры подключает веб-процесс, а не плагин.

        Воркеру ``FastAPI`` взять неоткуда, поэтому ``install()`` о нём
        не знает вовсе.
        """
        import inspect

        import vkt_ai

        assert inspect.signature(vkt_ai.install).parameters == {}

    def test_is_idempotent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """``create_app`` и ``bootstrap`` в одном процессе — не беда.

        Второй проход заново настроил бы логирование и Sentry и повторил
        бы ``install()`` каждого плагина.
        """
        calls: list[str] = []
        monkeypatch.setattr(
            bootstrap_module, "init_logging", lambda: calls.append("logging")
        )

        bootstrap()

        assert calls == []
