import asyncio
import contextlib
import inspect
import logging
from collections.abc import AsyncGenerator, Callable, Coroutine, Generator
from typing import Any

from bot_framework.handlers import HandlerBase
from bot_framework.middleware import Middleware

from .bot import VkTeamsBot
from .bot.types import (
    Event,
    GetSelfResponse,
)

logger = logging.getLogger('teams_bot.bot')


class Dispatcher:
    """VK Teams Bot."""

    inited: bool = False
    info: GetSelfResponse | None = None
    base_url: str = 'https://myteam.mail.ru/bot/v1'
    handlers: list[HandlerBase]
    middlewares: list[Middleware]

    bot: VkTeamsBot
    last_event_id: int = 0
    lyfecycle_hooks: list[AsyncGenerator[None]]
    tasks: list[asyncio.Task[Any]]

    def __init__(self, bot: VkTeamsBot) -> None:
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
            logger.info('Bot signed in as %s', self.info.nick)
            await self.start_polling()
        finally:
            await self.bot.close()

    async def start_polling(self) -> None:
        """Start polling."""
        while True:
            response = await self.bot.get_events(last_event_id=self.last_event_id, poll_time=20)
            for event in response.events:
                await self.trigger(event)
                self.last_event_id = max(self.last_event_id, event.eventId)

    async def trigger(self, event: Event) -> None:
        """Вызывает хэндлеры для события."""
        async with (
            self.apply_middlewares(event, [mw.on_event for mw in self.middlewares]),
            asyncio.TaskGroup() as tg,
        ):
            for handler in (h for h in self.handlers if h.check(event=event, dispatcher=self)):
                tg.create_task(self.run_handler(handler, event))

    async def run_handler(self, handler: HandlerBase, event: Event) -> None:
        try:
            async with self.apply_middlewares(event, [mw.on_callback for mw in self.middlewares]):
                if inspect.iscoroutinefunction(handler.handle):
                    await handler.handle(event, self)
                else:
                    await asyncio.to_thread(self.wrap_handler(handler.handle, event, self))
        except Exception:
            logger.exception('Ошибка при обработке хэндлера')

    @contextlib.asynccontextmanager
    async def apply_middlewares(
        self,
        event: Event,
        middlewares: list[
            Callable[[Event], AsyncGenerator[None, Any] | Generator[None, Any, None] | Coroutine[Any, Any, Any] | None],
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

    def wrap_handler(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Callable[[], Any]:  # noqa: ANN401
        """wrap_function."""

        def wrapper() -> Any:  # noqa: ANN401
            try:
                return func(*args, **kwargs)
            except Exception:
                logger.exception('Ошибка при обработке хэндлера')

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
