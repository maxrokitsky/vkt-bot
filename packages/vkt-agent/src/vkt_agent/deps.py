"""Зависимости, которые инструменты получают на входе.

Инструменту нужны сессия БД, клиент бота и — главное — актор: тот, кто
задал вопрос. Права проверяются **внутри** инструмента по актору, а не по
словам модели: модель не должна быть каналом эскалации привилегий.

Пакет ничего не знает про ``vkt_bot``: всё, что специфично для
приложения, приезжает сюда готовым.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclasses.dataclass(frozen=True, slots=True)
class AgentActor:
    """Кто спрашивает.

    ``is_admin`` вычисляется приложением заранее (владелец бота,
    ``is_superuser`` или роль ``admin``) — инструменту остаётся только
    прочитать флаг.
    """

    user_id: str
    display_name: str
    is_admin: bool = False

    def __str__(self) -> str:
        return self.display_name or self.user_id


@dataclasses.dataclass(slots=True)
class AgentDeps:
    """Контекст одной сессии агента.

    ``chat_id`` — тот чат, где идёт разговор; в обсуждении это ``chatId``
    треда, а не родительского чата, — узнать родителя по треду нечем.
    """

    session: AsyncSession
    actor: AgentActor
    chat_id: str
    #: Клиент VK Teams. Инструментам первой фазы не нужен, но он же
    #: понадобится мутирующим — ради него ``deps`` и существует.
    bot: Any = None
    thread_id: str | None = None
    #: Сам вопрос задан внутри обсуждения. Это не то же самое, что
    #: ``thread_id``: диалог может жить в треде, созданном на вопрос из
    #: обычного чата. Флаг важен для прав — состав обсуждения у API не
    #: спросить, поэтому там инструменты не выходят за его пределы.
    chat_is_thread: bool = False
    #: Есть ли в этом чате записанная история сообщений. Выключенная
    #: запись — не ошибка, но агент обязан сказать об этом прямо.
    history_enabled: bool = True
