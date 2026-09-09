"""Диспетчер: регистрация, ``trigger``, middlewares, поллинг."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import pytest
from vkt_dispatcher import Dispatcher
from vkt_dispatcher.filters import Filter
from vkt_dispatcher.handlers import (
    CommandHandler,
    DefaultHandler,
    HandlerBase,
    MessageHandler,
)
from vkt_dispatcher.middleware import Middleware

from tests.factories import events_response, make_event

if TYPE_CHECKING:
    from vkteams_client.types import Event

    from tests.conftest import FakeBot


class Recorder(HandlerBase):
    """Хендлер, который пишет в общий журнал."""

    def __init__(self, log: list[str], name: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.log = log
        self.name = name

    async def handle(self, event: Event, dispatcher: Dispatcher) -> None:  # noqa: ARG002
        self.log.append(self.name)


@pytest.fixture
def log() -> list[str]:
    """Журнал вызовов."""
    return []


class TestRegistration:
    """Регистрация хендлеров и middlewares."""

    def test_register_instance(self, dispatcher: Dispatcher) -> None:
        handler = HandlerBase()
        assert dispatcher.register_handler(handler) is handler
        assert dispatcher.handlers == [handler]

    def test_register_class_instantiates_it(self, dispatcher: Dispatcher) -> None:
        registered = dispatcher.register_handler(MessageHandler)
        assert isinstance(registered, MessageHandler)
        assert dispatcher.handlers == [registered]

    def test_register_preserves_order(self, dispatcher: Dispatcher) -> None:
        first, second = HandlerBase(), HandlerBase()
        dispatcher.register_handler(first)
        dispatcher.register_handler(second)
        assert dispatcher.handlers == [first, second]

    def test_register_middleware_returns_class(self, dispatcher: Dispatcher) -> None:
        assert dispatcher.register_middleware(Middleware) is Middleware
        assert len(dispatcher.middlewares) == 1
        assert isinstance(dispatcher.middlewares[0], Middleware)

    def test_fresh_dispatcher_is_empty(self, fake_bot: FakeBot) -> None:
        dispatcher = Dispatcher(bot=fake_bot)  # type: ignore[arg-type]
        assert dispatcher.handlers == []
        assert dispatcher.middlewares == []
        assert dispatcher.tasks == []
        assert dispatcher.last_event_id == 0
        assert dispatcher.inited is False
        assert dispatcher.info is None


class TestTrigger:
    """``Dispatcher.trigger``."""

    async def test_runs_matching_handlers(
        self, dispatcher: Dispatcher, log: list[str]
    ) -> None:
        dispatcher.register_handler(Recorder(log, "commands", filters=Filter.command))
        dispatcher.register_handler(Recorder(log, "all"))

        await dispatcher.trigger(make_event("new_message", text="/help"))

        assert sorted(log) == ["all", "commands"]

    async def test_skips_non_matching_handlers(
        self, dispatcher: Dispatcher, log: list[str]
    ) -> None:
        dispatcher.register_handler(Recorder(log, "commands", filters=Filter.command))
        await dispatcher.trigger(make_event("new_message", text="привет"))
        assert log == []

    async def test_handlers_run_concurrently(self, dispatcher: Dispatcher) -> None:
        order: list[str] = []

        class Slow(HandlerBase):
            async def handle(self, event: Event, dispatcher: Dispatcher) -> None:  # noqa: ARG002
                order.append("slow-start")
                await asyncio.sleep(0.02)
                order.append("slow-end")

        class Fast(HandlerBase):
            async def handle(self, event: Event, dispatcher: Dispatcher) -> None:  # noqa: ARG002
                order.append("fast")

        dispatcher.register_handler(Slow())
        dispatcher.register_handler(Fast())

        await dispatcher.trigger(make_event("new_message"))

        assert order == ["slow-start", "fast", "slow-end"]

    async def test_exception_in_one_handler_does_not_stop_others(
        self,
        dispatcher: Dispatcher,
        log: list[str],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        class Boom(HandlerBase):
            async def handle(self, event: Event, dispatcher: Dispatcher) -> None:  # noqa: ARG002
                msg = "боом"
                raise RuntimeError(msg)

        dispatcher.register_handler(Boom())
        dispatcher.register_handler(Recorder(log, "survivor"))

        with caplog.at_level("ERROR", logger="vkt_dispatcher"):
            await dispatcher.trigger(make_event("new_message"))

        assert log == ["survivor"]
        assert "Ошибка при обработке хэндлера" in caplog.text

    async def test_stop_dispatching_is_swallowed(
        self, dispatcher: Dispatcher, caplog: pytest.LogCaptureFixture
    ) -> None:
        """``DefaultHandler`` кидает ``StopDispatchingError``, но она логируется."""
        dispatcher.register_handler(DefaultHandler())
        with caplog.at_level("ERROR", logger="vkt_dispatcher"):
            await dispatcher.trigger(make_event("new_message"))
        assert "Ошибка при обработке хэндлера" in caplog.text

    async def test_sync_handler_runs_in_thread(self, dispatcher: Dispatcher) -> None:
        seen: list[str] = []

        class Sync(HandlerBase):
            def handle(self, event: Event, dispatcher: Dispatcher) -> None:  # type: ignore[override]  # noqa: ARG002
                seen.append("sync")

        dispatcher.register_handler(Sync())
        await dispatcher.trigger(make_event("new_message"))
        assert seen == ["sync"]

    async def test_sync_handler_exception_is_logged(
        self, dispatcher: Dispatcher, caplog: pytest.LogCaptureFixture
    ) -> None:
        class SyncBoom(HandlerBase):
            def handle(self, event: Event, dispatcher: Dispatcher) -> None:  # type: ignore[override]  # noqa: ARG002
                msg = "боом"
                raise RuntimeError(msg)

        dispatcher.register_handler(SyncBoom())
        with caplog.at_level("ERROR", logger="vkt_dispatcher"):
            await dispatcher.trigger(make_event("new_message"))
        assert "Ошибка при обработке хэндлера" in caplog.text

    async def test_no_handlers_is_a_noop(self, dispatcher: Dispatcher) -> None:
        await dispatcher.trigger(make_event("new_message"))

    async def test_callbacks_receive_bot(
        self, dispatcher: Dispatcher, fake_bot: FakeBot
    ) -> None:
        dispatcher.register_handler(
            CommandHandler(
                command="ping",
                callback=lambda bot, event: bot.send_text(
                    event.payload.chat.chatId, "pong"
                ),
            )
        )
        await dispatcher.trigger(make_event("new_message", text="/ping"))
        assert fake_bot.texts == ["pong"]


class TestWrapHandler:
    """``wrap_handler``."""

    def test_returns_result(self, dispatcher: Dispatcher) -> None:
        wrapped = dispatcher.wrap_handler(lambda a, b: a + b, 1, 2)
        assert wrapped() == 3

    def test_swallows_exception(
        self, dispatcher: Dispatcher, caplog: pytest.LogCaptureFixture
    ) -> None:
        def boom() -> None:
            msg = "боом"
            raise RuntimeError(msg)

        with caplog.at_level("ERROR", logger="vkt_dispatcher"):
            assert dispatcher.wrap_handler(boom)() is None
        assert "Ошибка при обработке хэндлера" in caplog.text

    def test_passes_kwargs(self, dispatcher: Dispatcher) -> None:
        wrapped = dispatcher.wrap_handler(lambda *, x: x * 2, x=21)
        assert wrapped() == 42


class TestMiddlewares:
    """``apply_middlewares`` — все четыре формы."""

    async def test_plain_function(self, dispatcher: Dispatcher, log: list[str]) -> None:
        class Sync(Middleware):
            def on_event(self, event: Event) -> None:  # noqa: ARG002
                log.append("sync")

        dispatcher.register_middleware(Sync)
        await dispatcher.trigger(make_event("new_message"))
        assert log == ["sync"]

    async def test_coroutine_function(
        self, dispatcher: Dispatcher, log: list[str]
    ) -> None:
        class Async(Middleware):
            async def on_event(self, event: Event) -> None:  # noqa: ARG002
                log.append("async")

        dispatcher.register_middleware(Async)
        await dispatcher.trigger(make_event("new_message"))
        assert log == ["async"]

    async def test_generator_runs_before_and_after(
        self, dispatcher: Dispatcher, log: list[str]
    ) -> None:
        class Gen(Middleware):
            def on_event(self, event: Event) -> Any:  # noqa: ANN401, ARG002
                log.append("before")
                yield
                log.append("after")

        dispatcher.register_middleware(Gen)
        dispatcher.register_handler(Recorder(log, "handler"))
        await dispatcher.trigger(make_event("new_message"))
        assert log == ["before", "handler", "after"]

    async def test_async_generator_runs_before_and_after(
        self, dispatcher: Dispatcher, log: list[str]
    ) -> None:
        class AsyncGen(Middleware):
            async def on_event(self, event: Event) -> Any:  # noqa: ANN401, ARG002
                log.append("before")
                yield
                log.append("after")

        dispatcher.register_middleware(AsyncGen)
        dispatcher.register_handler(Recorder(log, "handler"))
        await dispatcher.trigger(make_event("new_message"))
        assert log == ["before", "handler", "after"]

    async def test_post_triggers_run_in_reverse_order(
        self, dispatcher: Dispatcher, log: list[str]
    ) -> None:
        def make(name: str) -> type[Middleware]:
            class Gen(Middleware):
                def on_event(self, event: Event) -> Any:  # noqa: ANN401, ARG002
                    log.append(f"before-{name}")
                    yield
                    log.append(f"after-{name}")

            return Gen

        dispatcher.register_middleware(make("1"))
        dispatcher.register_middleware(make("2"))
        await dispatcher.trigger(make_event("new_message"))

        assert log == ["before-1", "before-2", "after-2", "after-1"]

    async def test_default_middleware_is_a_noop(self, dispatcher: Dispatcher) -> None:
        dispatcher.register_middleware(Middleware)
        await dispatcher.trigger(make_event("new_message"))

    async def test_on_callback_wraps_each_handler(
        self, dispatcher: Dispatcher, log: list[str]
    ) -> None:
        class PerHandler(Middleware):
            def on_callback(self, event: Event) -> Any:  # noqa: ANN401, ARG002
                log.append("enter")
                yield
                log.append("exit")

        dispatcher.register_middleware(PerHandler)
        dispatcher.register_handler(Recorder(log, "a"))
        dispatcher.register_handler(Recorder(log, "b"))

        await dispatcher.trigger(make_event("new_message"))

        assert log.count("enter") == 2
        assert log.count("exit") == 2

    async def test_middleware_sees_the_event(self, dispatcher: Dispatcher) -> None:
        seen: list[Event] = []

        class Spy(Middleware):
            async def on_event(self, event: Event) -> None:
                seen.append(event)

        dispatcher.register_middleware(Spy)
        event = make_event("new_message")
        await dispatcher.trigger(event)
        assert seen == [event]

    async def test_middleware_exception_propagates(
        self, dispatcher: Dispatcher, log: list[str]
    ) -> None:
        """Ошибка в ``on_event`` не глушится: хендлеры не запускаются."""

        class Boom(Middleware):
            async def on_event(self, event: Event) -> None:  # noqa: ARG002
                msg = "боом"
                raise RuntimeError(msg)

        dispatcher.register_middleware(Boom)
        dispatcher.register_handler(Recorder(log, "handler"))

        with pytest.raises(RuntimeError, match="боом"):
            await dispatcher.trigger(make_event("new_message"))
        assert log == []


class TestPolling:
    """``run`` и ``start_polling``."""

    async def test_run_fetches_bot_info(self, dispatcher: Dispatcher) -> None:
        from vkteams_client.types import GetSelfResponse

        info = GetSelfResponse(ok=True, firstName="Бот", nick="bot", userId="1:bot")
        dispatcher.bot.results["get_self"] = info  # type: ignore[attr-defined]
        stop = RuntimeError("хватит")
        dispatcher.bot.errors["get_events"] = stop  # type: ignore[attr-defined]

        with pytest.raises(RuntimeError, match="хватит"):
            await dispatcher.run()

        assert dispatcher.inited is True
        assert dispatcher.info is info
        assert dispatcher.bot.calls_of("close")  # type: ignore[attr-defined]

    async def test_run_closes_bot_on_error(self, dispatcher: Dispatcher) -> None:
        dispatcher.bot.errors["get_self"] = RuntimeError("нет сети")  # type: ignore[attr-defined]

        with pytest.raises(RuntimeError, match="нет сети"):
            await dispatcher.run()

        assert dispatcher.bot.calls_of("close")  # type: ignore[attr-defined]

    async def test_last_event_id_is_max_event_id(
        self, dispatcher: Dispatcher, log: list[str]
    ) -> None:
        from vkteams_client.types import EventsResponse

        batches = [
            EventsResponse.model_validate(
                events_response("new_message", "callback_query")
            ),
            EventsResponse.model_validate(events_response("deleted_message")),
        ]

        async def get_events(**_: Any) -> EventsResponse:
            if not batches:
                msg = "хватит"
                raise RuntimeError(msg)
            return batches.pop(0)

        dispatcher.bot.get_events = get_events  # type: ignore[attr-defined]
        dispatcher.register_handler(Recorder(log, "handler", filters=Filter.message))

        with pytest.raises(RuntimeError, match="хватит"):
            await dispatcher.start_polling()

        assert dispatcher.last_event_id == 13
        assert log == ["handler"]

    async def test_last_event_id_never_decreases(self, dispatcher: Dispatcher) -> None:
        from vkteams_client.types import EventsResponse

        dispatcher.last_event_id = 100
        batches = [EventsResponse.model_validate(events_response("new_message"))]

        async def get_events(**_: Any) -> EventsResponse:
            if not batches:
                msg = "хватит"
                raise RuntimeError(msg)
            return batches.pop(0)

        dispatcher.bot.get_events = get_events  # type: ignore[attr-defined]

        with pytest.raises(RuntimeError, match="хватит"):
            await dispatcher.start_polling()

        assert dispatcher.last_event_id == 100

    async def test_poll_time_is_20_seconds(self, dispatcher: Dispatcher) -> None:
        calls: list[dict[str, Any]] = []

        async def get_events(**kwargs: Any) -> Any:  # noqa: ANN401
            calls.append(kwargs)
            msg = "хватит"
            raise RuntimeError(msg)

        dispatcher.bot.get_events = get_events  # type: ignore[attr-defined]
        with pytest.raises(RuntimeError, match="хватит"):
            await dispatcher.start_polling()

        assert calls == [{"last_event_id": 0, "poll_time": 20}]
