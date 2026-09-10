"""Фабрики событий и моделей + загрузка JSON-фикстур событий."""

from __future__ import annotations

import copy
import functools
import json
import pathlib
import uuid
from typing import TYPE_CHECKING, Any

import pytest
from pydantic import TypeAdapter

from vkteams_client.types import Event

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from vkt_bot.core.models import Chat, ChatUser, Role

EVENTS_DIR = pathlib.Path(__file__).parent / "fixtures" / "events"

event_adapter: TypeAdapter[Event] = TypeAdapter(Event)


@functools.cache
def _raw(name: str) -> dict[str, Any]:
    path = EVENTS_DIR / f"{name}.json"
    if not path.exists():
        available = sorted(p.stem for p in EVENTS_DIR.glob("*.json"))
        msg = f"Нет фикстуры события {name!r}. Есть: {', '.join(available)}"
        raise FileNotFoundError(msg)
    return json.loads(path.read_text(encoding="utf-8"))


def raw_event(name: str, **overrides: Any) -> dict[str, Any]:
    """Сырой payload события из JSON-фикстуры.

    ``overrides`` мержатся в ``payload`` (рекурсивно для вложенных словарей).
    """
    data = copy.deepcopy(_raw(name))
    if overrides:
        _deep_update(data["payload"], overrides)
    return data


def _deep_update(target: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_update(target[key], value)
        else:
            target[key] = value
    return target


def make_event(name: str, **overrides: Any) -> Event:
    """Распарсенное событие из JSON-фикстуры."""
    return event_adapter.validate_python(raw_event(name, **overrides))


def events_response(*names: str) -> dict[str, Any]:
    """Тело ответа ``/events/get`` с указанными событиями."""
    return {"ok": True, "events": [raw_event(name) for name in names]}


ALL_EVENT_FIXTURES: tuple[str, ...] = (
    "new_message",
    "new_message_private",
    "new_message_in_thread",
    "new_message_from_bot",
    "new_message_with_format",
    "new_message_with_parts",
    "edited_message",
    "deleted_message",
    "pinned_message",
    "unpinned_message",
    "new_chat_members",
    "left_chat_members",
    "changed_chat_info",
    "callback_query",
)


@pytest.fixture
def make_raw_event() -> Any:  # noqa: ANN401
    """Фабрика сырых событий."""
    return raw_event


@pytest.fixture
def event_factory() -> Any:  # noqa: ANN401
    """Фабрика распарсенных событий."""
    return make_event


@pytest.fixture
def message_event() -> Event:
    """Событие ``newMessage`` в групповом чате."""
    return make_event("new_message")


@pytest.fixture
def callback_event() -> Event:
    """Событие ``callbackQuery``."""
    return make_event("callback_query")


# --------------------------------------------------------------------------- #
# Модели
# --------------------------------------------------------------------------- #


async def create_chat_user(
    session: AsyncSession,
    user_id: str,
    *,
    is_superuser: bool = False,
    is_bot: bool = False,
    first_name: str | None = None,
    last_name: str | None = None,
    nick: str | None = None,
) -> ChatUser:
    """Создать пользователя бота."""
    from vkt_bot.core.models import ChatUser

    user = ChatUser(
        id=user_id,
        is_superuser=is_superuser,
        is_bot=is_bot,
        first_name=first_name,
        last_name=last_name,
        nick=nick,
    )
    session.add(user)
    await session.commit()
    return user


async def create_chat(
    session: AsyncSession,
    chat_id: str,
    chat_type: str = "group",
    *,
    title: str | None = None,
) -> Chat:
    """Создать чат."""
    from vkteams_client.enums import ChatType

    from vkt_bot.core.models import Chat

    chat = Chat(id=chat_id, type=ChatType(chat_type), title=title)
    session.add(chat)
    await session.commit()
    return chat


async def create_role(session: AsyncSession, name: str) -> Role:
    """Создать роль."""
    from vkt_bot.core.models import Role

    role = Role(id=uuid.uuid4(), name=name)
    session.add(role)
    await session.commit()
    return role


async def assign_role(session: AsyncSession, user_id: str, role_id: uuid.UUID) -> None:
    """Назначить роль пользователю."""
    from vkt_bot.core.models import RoleAssignment

    session.add(RoleAssignment(role_id=role_id, user_id=user_id))
    await session.commit()


@pytest.fixture
async def user(session: AsyncSession) -> ChatUser:
    """Обычный пользователь бота."""
    return await create_chat_user(session, "user@example.com")


@pytest.fixture
async def superuser(session: AsyncSession) -> ChatUser:
    """Пользователь-администратор панели."""
    return await create_chat_user(session, "admin@example.com", is_superuser=True)


@pytest.fixture
async def owner(session: AsyncSession, owner_id: str) -> ChatUser:
    """Владелец бота (из ``settings.owner_id``)."""
    return await create_chat_user(session, owner_id)


@pytest.fixture
async def chat(session: AsyncSession) -> Chat:
    """Групповой чат."""
    return await create_chat(session, "681869378@chat.agent")


@pytest.fixture
async def admin_role(session: AsyncSession) -> Role:
    """Роль ``admin``."""
    return await create_role(session, "admin")


@pytest.fixture
async def bot_admin(session: AsyncSession, admin_role: Role) -> ChatUser:
    """Пользователь бота с ролью ``admin``."""
    user = await create_chat_user(session, "botadmin@example.com")
    await assign_role(session, user.id, admin_role.id)
    return user
