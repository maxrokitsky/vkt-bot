"""``AsyncRepository`` — базовый CRUD."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import pytest
import sqlalchemy as sa
from pydantic import BaseModel
from vkteams_client.enums import ChatType

from vkt_bot.core.models import Chat, ChatUser, Role
from vkt_bot.core.repositories.chat import ChatRepository, CreateChatSchema
from vkt_bot.core.repositories.role import CreateRoleSchema, RoleRepository
from vkt_bot.core.repositories.user import ChatUserRepository, CreateChatUserSchema
from vkt_bot.db.exceptions import NotFoundError
from vkt_bot.db.repository import AsyncRepository

from tests.conftest import table_count
from tests.factories import create_chat_user

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class TestGenericInference:
    """Модель выводится из параметров дженерика."""

    def test_model_from_generic_args(self) -> None:
        assert ChatUserRepository.model is ChatUser
        assert RoleRepository.model is Role
        assert ChatRepository.model is Chat

    def test_explicit_model_wins(self) -> None:
        class Explicit(AsyncRepository[ChatUser, str, CreateChatUserSchema, Any]):
            model = Chat

        assert Explicit.model is Chat

    def test_model_is_inherited(self) -> None:
        class Inherited(ChatUserRepository):
            pass

        assert Inherited.model is ChatUser

    def test_session_is_stored(self, session: AsyncSession) -> None:
        assert ChatUserRepository(session).session is session


class TestCreate:
    """``create``."""

    async def test_from_schema(self, session: AsyncSession) -> None:
        repo = ChatUserRepository(session)
        user = await repo.create(CreateChatUserSchema(id="a@example.com"))

        assert user.id == "a@example.com"
        assert user in session.new

    async def test_from_dict(self, session: AsyncSession) -> None:
        repo = ChatUserRepository(session)
        user = await repo.create({"id": "b@example.com", "is_superuser": True})

        assert user.is_superuser is True

    async def test_without_commit_is_not_persisted(
        self, session: AsyncSession, session_factory: Any
    ) -> None:
        await ChatUserRepository(session).create(
            CreateChatUserSchema(id="c@example.com")
        )
        async with session_factory() as other:
            assert await ChatUserRepository(other).get_or_none("c@example.com") is None

    async def test_commit_persists(
        self, session: AsyncSession, session_factory: Any
    ) -> None:
        await ChatUserRepository(session).create(
            CreateChatUserSchema(id="d@example.com"), commit=True
        )
        async with session_factory() as other:
            assert await ChatUserRepository(other).get("d@example.com")

    async def test_commit_refreshes_server_defaults(
        self, session: AsyncSession
    ) -> None:
        user = await ChatUserRepository(session).create(
            CreateChatUserSchema(id="e@example.com"), commit=True
        )
        assert user.created_at is not None
        assert user.is_superuser is False

    async def test_duplicate_primary_key_raises(self, session: AsyncSession) -> None:
        repo = ChatUserRepository(session)
        await repo.create(CreateChatUserSchema(id="dup@example.com"), commit=True)
        await repo.create(CreateChatUserSchema(id="dup@example.com"))

        with pytest.raises(sa.exc.IntegrityError):
            await session.commit()
        await session.rollback()

    async def test_session_is_usable_after_rollback(
        self, session: AsyncSession
    ) -> None:
        repo = ChatUserRepository(session)
        await repo.create(CreateChatUserSchema(id="r@example.com"), commit=True)
        await repo.create(CreateChatUserSchema(id="r@example.com"))
        with pytest.raises(sa.exc.IntegrityError):
            await session.commit()
        await session.rollback()

        assert await repo.get("r@example.com")


class TestGet:
    """``get`` / ``get_or_none`` / ``exists``."""

    async def test_get_returns_model(self, session: AsyncSession) -> None:
        await create_chat_user(session, "get@example.com")
        user = await ChatUserRepository(session).get("get@example.com")
        assert user.id == "get@example.com"

    async def test_get_missing_raises(self, session: AsyncSession) -> None:
        with pytest.raises(NotFoundError):
            await ChatUserRepository(session).get("nope@example.com")

    async def test_get_or_none_missing(self, session: AsyncSession) -> None:
        assert await ChatUserRepository(session).get_or_none("nope@example.com") is None

    async def test_get_or_none_found(self, session: AsyncSession) -> None:
        await create_chat_user(session, "found@example.com")
        assert await ChatUserRepository(session).get_or_none("found@example.com")

    async def test_exists(self, session: AsyncSession) -> None:
        repo = ChatUserRepository(session)
        await create_chat_user(session, "ex@example.com")
        assert await repo.exists("ex@example.com") is True
        assert await repo.exists("nope@example.com") is False

    async def test_get_by_uuid_pk(self, session: AsyncSession) -> None:
        repo = RoleRepository(session)
        role = await repo.create(CreateRoleSchema(name="devs"), commit=True)
        assert (await repo.get(role.id)).name == "devs"

    async def test_get_wrong_pk_type_returns_not_found(
        self, session: AsyncSession
    ) -> None:
        with pytest.raises(NotFoundError):
            await RoleRepository(session).get(uuid.uuid4())


class TestList:
    """``list``."""

    async def test_empty(self, session: AsyncSession) -> None:
        assert list(await ChatUserRepository(session).list()) == []

    async def test_returns_all_rows(self, session: AsyncSession) -> None:
        for i in range(3):
            await create_chat_user(session, f"u{i}@example.com")
        users = await ChatUserRepository(session).list()
        assert {u.id for u in users} == {f"u{i}@example.com" for i in range(3)}


class TestUpdate:
    """``update``."""

    async def test_from_dict(self, session: AsyncSession) -> None:
        await create_chat_user(session, "up@example.com")
        user = await ChatUserRepository(session).update(
            "up@example.com", {"is_superuser": True}, commit=True
        )
        assert user.is_superuser is True

    async def test_from_schema(self, session: AsyncSession) -> None:
        class UpdateUser(BaseModel):
            is_superuser: bool

        await create_chat_user(session, "ups@example.com")
        user = await ChatUserRepository(session).update(
            "ups@example.com", UpdateUser(is_superuser=True), commit=True
        )
        assert user.is_superuser is True

    async def test_missing_row_raises(self, session: AsyncSession) -> None:
        with pytest.raises(NotFoundError):
            await ChatUserRepository(session).update("nope@example.com", {})

    async def test_empty_data_is_a_noop(self, session: AsyncSession) -> None:
        await create_chat_user(session, "noop@example.com")
        user = await ChatUserRepository(session).update("noop@example.com", {})
        assert user.is_superuser is False

    async def test_without_commit_is_not_persisted(
        self, session: AsyncSession, session_factory: Any
    ) -> None:
        await create_chat_user(session, "nc@example.com")
        await ChatUserRepository(session).update(
            "nc@example.com", {"is_superuser": True}
        )
        await session.rollback()

        async with session_factory() as other:
            user = await ChatUserRepository(other).get("nc@example.com")
            assert user.is_superuser is False


class TestDelete:
    """``delete``."""

    async def test_removes_row(self, session: AsyncSession) -> None:
        await create_chat_user(session, "del@example.com")
        await ChatUserRepository(session).delete("del@example.com", commit=True)
        assert await table_count(session, ChatUser) == 0

    async def test_missing_row_raises(self, session: AsyncSession) -> None:
        with pytest.raises(NotFoundError):
            await ChatUserRepository(session).delete("nope@example.com")

    async def test_without_commit_is_not_persisted(
        self, session: AsyncSession, session_factory: Any
    ) -> None:
        await create_chat_user(session, "dnc@example.com")
        await ChatUserRepository(session).delete("dnc@example.com")
        await session.rollback()

        async with session_factory() as other:
            assert await ChatUserRepository(other).get("dnc@example.com")

    async def test_deleting_a_chat_with_webhooks(
        self, session: AsyncSession, is_postgres: bool
    ) -> None:
        """У ``webhooks.chat_id`` объявлен ``ON DELETE CASCADE``.

        PostgreSQL применяет каскад и удаляет вебхуки вместе с чатом; SQLite
        по умолчанию не проверяет внешние ключи, поэтому строка остаётся.
        """
        from vkt_bot.core.models import Webhook

        await create_chat_user(session, "owner@example.com")
        session.add(Chat(id="chat-1", type=ChatType.GROUP))
        await session.commit()
        session.add(
            Webhook(
                id="wh-1",
                name="hook",
                chat_id="chat-1",
                api_key_hash="hash",
                created_by="owner@example.com",
            )
        )
        await session.commit()

        await ChatRepository(session).delete("chat-1", commit=True)

        expected = 0 if is_postgres else 1
        assert await table_count(session, Webhook) == expected


class TestChatRepository:
    """``ChatRepository`` — enum-поле."""

    async def test_create_with_enum(self, session: AsyncSession) -> None:
        chat = await ChatRepository(session).create(
            CreateChatSchema(id="c1@chat.agent", type=ChatType.GROUP), commit=True
        )
        assert chat.type is ChatType.GROUP

    async def test_enum_survives_reload(
        self, session: AsyncSession, session_factory: Any
    ) -> None:
        await ChatRepository(session).create(
            CreateChatSchema(id="c2@chat.agent", type=ChatType.CHANNEL), commit=True
        )
        async with session_factory() as other:
            chat = await ChatRepository(other).get("c2@chat.agent")
            assert chat.type is ChatType.CHANNEL

    async def test_schema_accepts_enum_value(self) -> None:
        schema = CreateChatSchema.model_validate({"id": "x", "type": "private"})
        assert schema.type is ChatType.PRIVATE
