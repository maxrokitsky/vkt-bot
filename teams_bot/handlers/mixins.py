from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Protocol, cast

from bot_framework.bot.types import NewMessageEvent
from bot_framework.db.session import async_session
from bot_framework.exceptions import NotFoundError
from bot_framework.filters import FilterBase
from core.repositories.role import CreateRoleSchema, RoleAssignmentRepository, RoleRepository
from teams_bot.config import settings
from core.queries.roles import RoleAssignmentUserAndRoleQuery
from teams_bot.utils import mention

if TYPE_CHECKING:
    from bot_framework.bot.types import Event
    from bot_framework.dispatcher import Dispatcher


class HandlerProtocol(Protocol):
    """HandlerBase."""

    filters: FilterBase | None
    callback: Callable[..., Any] | None

    def check(self, event: Event, dispatcher: Dispatcher) -> bool: ...

    async def handle(self, event: Event, dispatcher: Dispatcher) -> None: ...


class AdminRequiredMixin:
    async def handle(self, event: Event, dispatcher: Dispatcher) -> None:
        if not isinstance(event, NewMessageEvent):
            msg = 'AdminRequiredMixin можно добавлять только в MessageHandler и CommandHandler'
            raise TypeError(msg)
        if self.check_user_is_owner(event.payload.sender.userId) or await self.check_user_is_admin(
            event.payload.sender.userId
        ):
            await cast(HandlerProtocol, super()).handle(event=event, dispatcher=dispatcher)
            return

        await dispatcher.bot.send_text(
            chat_id=event.payload.chat.chatId,
            text=f'{mention(event.payload.sender.userId)} У вас нет доступа к этой команде',
        )

    def check_user_is_owner(self, user_id: str) -> bool:
        return bool(settings.owner_id and user_id == settings.owner_id)

    async def check_user_is_admin(self, user_id: str) -> bool:
        async with async_session() as session:
            try:
                role = await RoleRepository(session).get_by_name('admin')
            except NotFoundError:
                role = await RoleRepository(session).create(
                    CreateRoleSchema(name='admin'),
                    commit=True,
                )
            return (
                await RoleAssignmentRepository(session)
                .query(RoleAssignmentUserAndRoleQuery(user_id=user_id, role_id=role.id))
                .exists()
            )
