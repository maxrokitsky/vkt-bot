"""Прогресс в чате.

Стрима в мессенджере нет, поэтому «печатает…» изображается правкой
одного сообщения. Правка чаще раза в две секунды упрётся в лимиты API,
поэтому шаги копятся и показываются пачкой.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import structlog

from vkt_agent import Step, StepKind

if TYPE_CHECKING:
    from vkteams_client import VKTeams

logger = structlog.get_logger("vkt_ai.progress")

#: Минимальный интервал между правками одного сообщения.
MIN_INTERVAL = 2.0

THINKING = "🤔 думаю…"

#: Как называть инструменты по-человечески. Незнакомое имя показывается
#: как есть: новый инструмент не должен ломать прогресс.
TOOL_TITLES = {
    "find_chats": "ищу чаты",
    "chat_members": "смотрю состав чата",
    "user_roles": "смотрю роли",
    "role_members": "смотрю носителей роли",
    "recent_events": "читаю журнал событий",
    "chat_messages": "читаю переписку",
}


class Progress:
    """Одно сообщение, которое правится по ходу работы."""

    def __init__(self, bot: VKTeams, chat_id: str, msg_id: str | None) -> None:
        self.bot = bot
        self.chat_id = chat_id
        self.msg_id = msg_id
        self.steps: list[str] = []
        self._last_edit = 0.0

    async def on_step(self, step: Step) -> None:
        """Показать очередной шаг."""
        if step.kind is not StepKind.TOOL_CALL or not step.tool:
            return
        self.steps.append(TOOL_TITLES.get(step.tool, step.tool))
        if time.monotonic() - self._last_edit < MIN_INTERVAL:
            return
        await self.edit("🔧 " + " → ".join(self.steps))

    async def edit(self, text: str) -> Any:  # noqa: ANN401
        """Заменить текст сообщения.

        Отказ сервера исключением не является — в логах он выглядел бы
        успешной отправкой, поэтому ``ok`` проверяется явно.
        """
        if not self.msg_id:
            return None
        self._last_edit = time.monotonic()
        response = await self.bot.edit_text(
            chat_id=self.chat_id, msg_id=self.msg_id, text=text
        )
        if response is not None and not response.ok:
            logger.warning(
                "agent.progress_edit_refused",
                chat_id=self.chat_id,
                reason=response.description,
            )
        return response
