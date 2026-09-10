"""Индикатор «печатает…» на время работы агента.

Раньше вместо него бот присылал сообщение «🤔 думаю…», которое потом
правилось в ответ. Сообщение-заглушка мусорит в чате и выглядит как
ответ, которым не является; индикатор для этого и придуман.

Состояние надо повторять: сервер держит его недолго, поэтому спека
требует слать `chats/sendActions` при каждой смене действий и не реже
раза в 10 секунд, пока они не менялись. Отсюда фоновая задача.

Действий два, и они ложатся на работу агента точно: `looking` — пока он
ходит инструментами за данными, `typing` — пока сочиняет ответ.
"""

from __future__ import annotations

import asyncio
import contextlib
from types import TracebackType
from typing import TYPE_CHECKING, Self

import structlog

from vkt_agent import Step, StepKind
from vkteams_client.enums import ChatAction

if TYPE_CHECKING:
    from vkteams_client import VKTeams

logger = structlog.get_logger("vkt_ai.activity")

#: Как часто повторять состояние. Спека разрешает раз в 10 секунд —
#: берём с запасом, чтобы индикатор не мигал на границе.
INTERVAL = 8.0


class ChatActivity:
    """Держит индикатор, пока агент работает.

    Индикатор — украшение: любая ошибка здесь глотается. Не показать
    «печатает…» неприятно, не ответить из-за этого — недопустимо.
    """

    def __init__(self, bot: VKTeams, chat_id: str) -> None:
        self.bot = bot
        self.chat_id = chat_id
        self.action = ChatAction.TYPING
        self._task: asyncio.Task[None] | None = None

    async def __aenter__(self) -> Self:
        self._task = asyncio.create_task(self._keep())
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        # Пустые действия — «закончил». Спека просит сказать это один раз,
        # поэтому здесь, а не в цикле.
        await self._send()

    async def on_step(self, step: Step) -> None:
        """Переключить состояние по шагу агента."""
        action = (
            ChatAction.LOOKING if step.kind is StepKind.TOOL_CALL else ChatAction.TYPING
        )
        if action is self.action:
            return
        self.action = action
        # Смена действия сообщается сразу, не дожидаясь очередного круга:
        # этого требует спека, и так индикатор не отстаёт от работы.
        await self._send(action)

    async def _keep(self) -> None:
        """Повторять текущее состояние, пока задачу не снимут."""
        while True:
            await self._send(self.action)
            await asyncio.sleep(INTERVAL)

    async def _send(self, *actions: ChatAction) -> None:
        try:
            await self.bot.send_actions(self.chat_id, *actions)
        except Exception:
            logger.debug("agent.activity_failed", chat_id=self.chat_id, exc_info=True)
