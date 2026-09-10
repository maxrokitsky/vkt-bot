import asyncio
import contextlib
import inspect
import time
from collections.abc import AsyncGenerator, Callable, Coroutine, Generator
from typing import Any, ClassVar

import aiohttp
import structlog

from .handlers import HandlerBase
from .log_context import event_context
from .middleware import Middleware

from vkteams_client.client import VKTeams
from vkteams_client.types import (
    Event,
    GetSelfResponse,
)
from .loggers import main_logger


class Dispatcher:
    """VK Teams Bot."""

    inited: bool = False
    info: GetSelfResponse | None = None
    base_url: str = "https://myteam.mail.ru/bot/v1"
    handlers: list[HandlerBase]
    middlewares: list[Middleware]

    bot: VKTeams
    last_event_id: int = 0
    #: Паузы между повторами опроса событий после сетевой ошибки, секунды.
    RETRY_DELAYS: ClassVar[tuple[int, ...]] = (1, 2, 5, 10, 30)
    lyfecycle_hooks: list[AsyncGenerator[None]]
    tasks: list[asyncio.Task[Any]]

    def __init__(self, bot: VKTeams) -> None:
        self.bot = bot
        self.handlers = []
        self.message_handlers = []
        self.tasks = []
        self.lyfecycle_hooks = []
        self.middlewares = []

    async def run(self) -> None:
        """Запускает бота."""
        try:
            self.info = await self.bot.get_self()
            self.inited = True
            main_logger.info("bot.started", nick=self.info.nick)
            await self.start_polling()
        finally:
            await self.bot.close()

    async def start_polling(self) -> None:
        """Опрашивать события, переживая обрывы сети.

        Long-poll регулярно заканчивается таймаутом или разрывом соединения.
        Раньше любая такая ошибка завершала процесс бота, поэтому сетевые
        сбои гасятся здесь с нарастающей паузой. Ошибки в самом коде
        (не сетевые) по-прежнему поднимаются наружу.
        """
        failures = 0
        while True:
            try:
                response = await self.bot.get_events(
                    last_event_id=self.last_event_id, poll_time=20
                )
            except (TimeoutError, OSError, aiohttp.ClientError):
                delay = self.RETRY_DELAYS[min(failures, len(self.RETRY_DELAYS) - 1)]
                failures += 1
                main_logger.warning(
                    "bot.polling_failed",
                    attempt=failures,
                    retry_in=delay,
                    exc_info=True,
                )
                await asyncio.sleep(delay)
                continue

            if failures:
                main_logger.info("bot.polling_recovered", after_attempts=failures)
            failures = 0
            for event in response.events:
                await self.trigger(event)
                self.last_event_id = max(self.last_event_id, event.eventId)

    async def trigger(self, event: Event) -> None:
        """Вызывает хэндлеры для события.

        Контекст логирования привязывается здесь, а не отдельным middleware:
        порядок middleware определяется порядком импортов, и первая же
        строка лога рискует остаться без контекста. Привязка обязана быть
        до ``create_task`` — задача получает **копию** контекста в момент
        создания, поэтому поля, привязанные позже, до хэндлеров не дойдут.
        """
        with structlog.contextvars.bound_contextvars(**event_context(event)):
            main_logger.debug("event.received")
            async with (
                self.apply_middlewares(event, [mw.on_event for mw in self.middlewares]),
                asyncio.TaskGroup() as tg,
            ):
                for handler in (
                    h for h in self.handlers if h.check(event=event, dispatcher=self)
                ):
                    tg.create_task(self.run_handler(handler, event))

    async def run_handler(self, handler: HandlerBase, event: Event) -> None:
        # Своя задача — своя копия контекста, поэтому имя хэндлера здесь
        # не перетирается соседними хэндлерами того же события.
        with structlog.contextvars.bound_contextvars(handler=type(handler).__name__):
            started = time.perf_counter()
            try:
                async with self.apply_middlewares(
                    event, [mw.on_callback for mw in self.middlewares]
                ):
                    if inspect.iscoroutinefunction(handler.handle):
                        await handler.handle(event, self)
                    else:
                        await asyncio.to_thread(
                            self.wrap_handler(handler.handle, event, self)
                        )
            except Exception:
                main_logger.exception("handler.failed")
            else:
                main_logger.debug(
                    "handler.finished",
                    duration_ms=round((time.perf_counter() - started) * 1000, 1),
                )

    @contextlib.asynccontextmanager
    async def apply_middlewares(
        self,
        event: Event,
        middlewares: list[
            Callable[
                [Event],
                AsyncGenerator[None, Any]
                | Generator[None, Any, None]
                | Coroutine[Any, Any, Any]
                | None,
            ],
        ],
    ) -> AsyncGenerator[None, Any]:
        post_triggers: list[Any] = []
        for middleware in middlewares:
            if inspect.isasyncgenfunction(middleware):
                asyncgenerator = middleware(event)
                await anext(asyncgenerator)
                post_triggers.append(asyncgenerator)
            elif inspect.iscoroutinefunction(middleware):
                await middleware(event)
            elif inspect.isgeneratorfunction(middleware):
                generator = middleware(event)
                next(generator)
                post_triggers.append(generator)
            else:
                middleware(event)
        yield
        for trigger in reversed(post_triggers):
            if inspect.isgenerator(trigger):
                with contextlib.suppress(StopIteration):
                    next(trigger)
            if inspect.isasyncgen(trigger):
                with contextlib.suppress(StopAsyncIteration):
                    await anext(trigger)

    def wrap_handler(
        self, func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Callable[[], Any]:  # noqa: ANN401
        """wrap_function."""

        def wrapper() -> Any:  # noqa: ANN401
            try:
                return func(*args, **kwargs)
            except Exception:
                main_logger.exception("handler.failed")

        return wrapper

    def register_handler(self, handler: HandlerBase | type[HandlerBase]) -> HandlerBase:
        """Register handler."""
        if inspect.isclass(handler):
            handler = handler()
        self.handlers.append(handler)
        return handler

    def register_middleware(self, middleware: type[Middleware]) -> type[Middleware]:
        """Register middleware."""
        self.middlewares.append(middleware())
        return middleware

    # def lyfecycle(self, func: AsyncGenerator[Any]) -> AsyncGenerator[Any]:
    #     self.lyfecycle_hooks.append(func)
    #     return func
