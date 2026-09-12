"""Выбор брокера и его жизненный цикл."""

from __future__ import annotations

from typing import Any

import pytest
from taskiq import InMemoryBroker, SimpleRetryMiddleware
from taskiq_redis import ListQueueBroker

from vkt_bot.worker import broker as broker_module
from vkt_bot.worker.broker import broker as module_broker
from vkt_bot.worker.broker import broker_client, create_broker, distributed


def settings_with(monkeypatch: pytest.MonkeyPatch, **fields: Any) -> None:  # noqa: ANN401
    """Подменить настройки у фабрики брокера.

    Не через ``get_settings.cache_clear()``: настройки общие на процесс, и
    сброс кэша задел бы всех, кто их уже держит.
    """
    from vkt_bot.config import get_settings

    real = get_settings()
    fake = real.model_copy(update=fields)
    monkeypatch.setattr(broker_module, "get_settings", lambda: fake)


class TestBrokerChoice:
    """Какой брокер собирается по настройкам."""

    def test_without_redis_url_it_is_in_memory(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Локальная разработка не должна требовать поднятого Redis."""
        settings_with(monkeypatch, redis_url=None)

        assert isinstance(create_broker(), InMemoryBroker)

    def test_the_fallback_is_loud(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Без очереди бот работает, но хуже — молчать об этом нельзя."""
        settings_with(monkeypatch, redis_url=None)

        with caplog.at_level("WARNING", logger="vkt_bot.worker"):
            create_broker()

        assert "broker.in_memory" in caplog.text

    def test_with_redis_url_it_is_a_list_queue(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Боевая ветка проверяется без Redis: пул соединений ленивый.

        ``ListQueueBroker`` в конструкторе никуда не ходит, поэтому
        сервис для этого теста не нужен.
        """
        settings_with(
            monkeypatch, redis_url="redis://localhost:6379/0", task_queue="vkt-bot"
        )

        built = create_broker()

        assert isinstance(built, ListQueueBroker)
        assert built.queue_name == "vkt-bot"

    def test_blocking_read_has_no_deadline(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``brpop`` ждёт задачу сколько нужно — а redis-py её обрывает.

        С восьмой версии у redis-py ``socket_timeout=5`` по умолчанию,
        и бесконечное чтение падает через пять секунд.
        ``ListQueueBroker.listen()`` ловит только ``ConnectionError``,
        поэтому воркер уходил в бесконечный перезапуск — и терял задачу,
        которую выполнял: подтверждений у списка нет. Проверено на живом
        Redis: без этой строки воркер не живёт и десяти секунд.
        """
        settings_with(monkeypatch, redis_url="redis://localhost:6379/0")

        kwargs = create_broker().connection_pool.connection_kwargs

        assert kwargs["socket_timeout"] is None
        assert kwargs["socket_keepalive"] is True

    def test_retries_do_not_touch_the_agent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Повтор вызова модели — второй ответ в чат и второй счёт.

        ``SimpleRetryMiddleware`` действует только по метке
        ``retry_on_error``, и сессия агента её не ставит.
        """
        settings_with(monkeypatch, redis_url="redis://localhost:6379/0")

        built = create_broker()

        assert any(isinstance(mw, SimpleRetryMiddleware) for mw in built.middlewares)

    def test_tests_never_get_a_real_broker(self) -> None:
        """Страховка той же породы, что ``_no_global_session_factory``."""
        assert isinstance(module_broker, InMemoryBroker)
        assert distributed() is False


class TestBrokerClient:
    """``broker_client``."""

    async def test_does_not_start_listening(self) -> None:
        """Процесс бота ставит задачи, но не разбирает свою же очередь.

        Без ``is_worker_process = False`` taskiq поднял бы приёмник прямо
        в боте — ровно то, от чего мы уходим.
        """
        async with broker_client() as client:
            assert client.is_worker_process is False
