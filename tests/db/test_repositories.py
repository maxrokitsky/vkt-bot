"""Конкретные репозитории ``vkt_bot.core.repositories``."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import bcrypt
import pytest

from vkt_bot.core.models import LoginToken
from vkt_bot.core.repositories.bot_settings import (
    BotSettingsRepository,
    CreateBotSettingsSchema,
)
from vkt_bot.core.repositories.log_entry import (
    CreateLogEntrySchema,
    LogEntryRepository,
)
from vkt_bot.core.repositories.login_history import LoginHistoryRepository
from vkt_bot.core.repositories.login_token import LoginTokenRepository
from vkt_bot.core.repositories.role import CreateRoleSchema, RoleRepository
from vkt_bot.core.repositories.user import ChatUserRepository
from vkt_bot.core.repositories.webhook import WebhookRepository
from vkt_bot.db.exceptions import NotFoundError
from vkt_bot.webapp.schemas.webhook import WebhookCreateSchema, WebhookUpdateSchema

from tests.conftest import table_count
from tests.factories import assign_role, create_chat, create_chat_user, create_role

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from vkt_bot.core.models import Chat, ChatUser


class TestChatUserRepository:
    """``ChatUserRepository``."""

    async def test_get_or_create_creates(self, session: AsyncSession) -> None:
        user = await ChatUserRepository(session).get_or_create("new@example.com")
        assert user.id == "new@example.com"

    async def test_get_or_create_returns_existing(self, session: AsyncSession) -> None:
        existing = await create_chat_user(session, "old@example.com", is_superuser=True)
        user = await ChatUserRepository(session).get_or_create("old@example.com")

        assert user is existing
        assert user.is_superuser is True
        assert await table_count(session, type(existing)) == 1

    async def test_list_by_roles(self, session: AsyncSession) -> None:
        devs = await create_role(session, "devs")
        qa = await create_role(session, "qa")
        dev = await create_chat_user(session, "dev@example.com")
        tester = await create_chat_user(session, "qa@example.com")
        await create_chat_user(session, "nobody@example.com")
        await assign_role(session, dev.id, devs.id)
        await assign_role(session, tester.id, qa.id)

        users = await ChatUserRepository(session).list_by_roles(["devs"])
        assert [u.id for u in users] == ["dev@example.com"]

    async def test_list_by_roles_is_case_insensitive(
        self, session: AsyncSession
    ) -> None:
        role = await create_role(session, "DevOps")
        user = await create_chat_user(session, "dev@example.com")
        await assign_role(session, user.id, role.id)

        users = await ChatUserRepository(session).list_by_roles(["DEVOPS"])
        assert [u.id for u in users] == ["dev@example.com"]

    async def test_list_by_roles_multiple(self, session: AsyncSession) -> None:
        devs = await create_role(session, "devs")
        qa = await create_role(session, "qa")
        dev = await create_chat_user(session, "dev@example.com")
        tester = await create_chat_user(session, "qa@example.com")
        await assign_role(session, dev.id, devs.id)
        await assign_role(session, tester.id, qa.id)

        users = await ChatUserRepository(session).list_by_roles(["devs", "qa"])
        assert {u.id for u in users} == {"dev@example.com", "qa@example.com"}

    async def test_list_by_roles_unknown_role(self, session: AsyncSession) -> None:
        users = await ChatUserRepository(session).list_by_roles(["nope"])
        assert list(users) == []


class TestRoleRepository:
    """``RoleRepository``."""

    async def test_get_by_name(self, session: AsyncSession) -> None:
        await create_role(session, "devs")
        assert (await RoleRepository(session).get_by_name("devs")).name == "devs"

    async def test_get_by_name_is_case_insensitive(self, session: AsyncSession) -> None:
        await create_role(session, "DevOps")
        assert (await RoleRepository(session).get_by_name("devops")).name == "DevOps"

    async def test_get_by_name_missing_raises(self, session: AsyncSession) -> None:
        with pytest.raises(NotFoundError):
            await RoleRepository(session).get_by_name("nope")

    async def test_name_is_unique_case_insensitively(
        self, session: AsyncSession
    ) -> None:
        import sqlalchemy as sa

        repo = RoleRepository(session)
        await repo.create(CreateRoleSchema(name="devs"), commit=True)
        await repo.create(CreateRoleSchema(name="DEVS"))
        with pytest.raises(sa.exc.IntegrityError):
            await session.commit()
        await session.rollback()


class TestBotSettingsRepository:
    """``BotSettingsRepository``."""

    async def test_get_by_key_missing(self, session: AsyncSession) -> None:
        assert await BotSettingsRepository(session).get_by_key("nope") is None

    async def test_set_value_creates(self, session: AsyncSession) -> None:
        repo = BotSettingsRepository(session)
        setting = await repo.set_value("start_message", "Привет", "Приветствие")
        await session.commit()

        assert setting.key == "start_message"
        assert setting.value == "Привет"
        assert setting.description == "Приветствие"

    async def test_set_value_updates_existing(self, session: AsyncSession) -> None:
        repo = BotSettingsRepository(session)
        await repo.create(CreateBotSettingsSchema(key="k", value="старое"), commit=True)

        setting = await repo.set_value("k", "новое")
        await session.commit()

        assert setting.value == "новое"
        assert await table_count(session, type(setting)) == 1

    async def test_set_value_clears_description(self, session: AsyncSession) -> None:
        """``set_value`` без описания перезаписывает его на ``None``."""
        repo = BotSettingsRepository(session)
        await repo.create(
            CreateBotSettingsSchema(key="k", value="v", description="было"),
            commit=True,
        )

        setting = await repo.set_value("k", "v2")
        await session.commit()
        assert setting.description is None

    async def test_get_by_key_returns_saved(self, session: AsyncSession) -> None:
        repo = BotSettingsRepository(session)
        await repo.set_value("k", "v")
        await session.commit()
        assert (await repo.get_by_key("k")).value == "v"


class TestLoginTokenRepository:
    """``LoginTokenRepository``."""

    async def test_create_token(self, session: AsyncSession, user: ChatUser) -> None:
        repo = LoginTokenRepository(session)
        token = await repo.create_token(user.id)
        await session.commit()

        assert len(token.token) > 20
        assert token.user_id == user.id
        assert token.used is False

    async def test_create_token_expiry(
        self, session: AsyncSession, user: ChatUser
    ) -> None:
        token = await LoginTokenRepository(session).create_token(
            user.id, expires_minutes=10
        )
        await session.commit()

        delta = token.expires_at.replace(tzinfo=datetime.UTC) - datetime.datetime.now(
            datetime.UTC
        )
        assert datetime.timedelta(minutes=9) < delta <= datetime.timedelta(minutes=10)

    async def test_tokens_are_unique(
        self, session: AsyncSession, user: ChatUser
    ) -> None:
        repo = LoginTokenRepository(session)
        first = await repo.create_token(user.id)
        second = await repo.create_token(user.id)
        await session.commit()
        assert first.token != second.token

    async def test_get_by_token(self, session: AsyncSession, user: ChatUser) -> None:
        repo = LoginTokenRepository(session)
        token = await repo.create_token(user.id)
        await session.commit()

        found = await repo.get_by_token(token.token)
        assert found is not None
        assert found.id == token.id

    async def test_get_by_token_missing(self, session: AsyncSession) -> None:
        assert await LoginTokenRepository(session).get_by_token("nope") is None

    async def test_mark_used(self, session: AsyncSession, user: ChatUser) -> None:
        repo = LoginTokenRepository(session)
        token = await repo.create_token(user.id)
        await session.commit()

        await repo.mark_used(token)
        await session.commit()

        assert (await repo.get_by_token(token.token)).used is True

    async def test_cleanup_removes_used_tokens(
        self, session: AsyncSession, user: ChatUser
    ) -> None:
        repo = LoginTokenRepository(session)
        token = await repo.create_token(user.id)
        await repo.mark_used(token)
        await session.commit()

        removed = await repo.cleanup_expired()
        await session.commit()

        assert removed == 1
        assert await table_count(session, LoginToken) == 0

    async def test_cleanup_removes_expired_tokens(
        self, session: AsyncSession, user: ChatUser
    ) -> None:
        repo = LoginTokenRepository(session)
        session.add(
            LoginToken(
                token="expired",
                user_id=user.id,
                expires_at=datetime.datetime.now(datetime.UTC)
                - datetime.timedelta(minutes=1),
            )
        )
        await session.commit()

        assert await repo.cleanup_expired() == 1
        await session.commit()

    async def test_cleanup_keeps_fresh_tokens(
        self, session: AsyncSession, user: ChatUser
    ) -> None:
        repo = LoginTokenRepository(session)
        await repo.create_token(user.id, expires_minutes=60)
        await session.commit()

        assert await repo.cleanup_expired() == 0
        await session.commit()
        assert await table_count(session, LoginToken) == 1


class TestLoginHistoryRepository:
    """``LoginHistoryRepository``."""

    async def test_log_login(self, session: AsyncSession, user: ChatUser) -> None:
        record = await LoginHistoryRepository(session).log_login(
            user.id, "10.0.0.1", "pytest"
        )
        await session.commit()

        assert record.user_id == user.id
        assert record.ip_address == "10.0.0.1"
        assert record.user_agent == "pytest"
        assert record.created_at is not None

    async def test_log_login_without_ip(
        self, session: AsyncSession, user: ChatUser
    ) -> None:
        record = await LoginHistoryRepository(session).log_login(user.id, None, None)
        await session.commit()
        assert record.ip_address is None


class TestLogEntryRepository:
    """``LogEntryRepository``."""

    async def test_create_with_json_details(self, session: AsyncSession) -> None:
        from vkt_bot.core.models.log_entry import ActionType, ActorType, EntityType

        entry = await LogEntryRepository(session).create(
            CreateLogEntrySchema(
                actor_type=ActorType.WEB_USER,
                actor_id="admin@example.com",
                action_type=ActionType.CREATE,
                entity_type=EntityType.ROLE,
                entity_id="role-1",
                description="Создана роль",
                details={"name": "devs", "nested": {"a": 1}},
            ),
            commit=True,
        )

        assert entry.details == {"name": "devs", "nested": {"a": 1}}
        assert entry.timestamp is not None

    async def test_details_can_be_none(self, session: AsyncSession) -> None:
        from vkt_bot.core.models.log_entry import ActionType, ActorType, EntityType

        entry = await LogEntryRepository(session).create(
            CreateLogEntrySchema(
                actor_type=ActorType.SYSTEM,
                actor_id=None,
                action_type=ActionType.UPDATE,
                entity_type=EntityType.CHAT,
                entity_id="chat-1",
            ),
            commit=True,
        )
        assert entry.details is None


class TestWebhookRepository:
    """``WebhookRepository``."""

    @pytest.fixture
    async def webhook_owner(self, session: AsyncSession) -> ChatUser:
        return await create_chat_user(session, "wh-owner@example.com")

    @pytest.fixture
    async def webhook_chat(self, session: AsyncSession) -> Chat:
        return await create_chat(session, "wh-chat@chat.agent")

    async def test_create_with_api_key(
        self, session: AsyncSession, webhook_owner: ChatUser, webhook_chat: Chat
    ) -> None:
        repo = WebhookRepository(session)
        webhook, api_key = await repo.create_with_api_key(
            WebhookCreateSchema(name="хук", chat_id=webhook_chat.id),
            webhook_owner.id,
        )

        assert webhook.name == "хук"
        assert webhook.created_by == webhook_owner.id
        assert webhook.is_active is True
        assert webhook.webhook_metadata == {}
        assert len(api_key) > 20

    async def test_api_key_is_hashed(
        self, session: AsyncSession, webhook_owner: ChatUser, webhook_chat: Chat
    ) -> None:
        repo = WebhookRepository(session)
        webhook, api_key = await repo.create_with_api_key(
            WebhookCreateSchema(name="хук", chat_id=webhook_chat.id),
            webhook_owner.id,
        )

        assert api_key not in webhook.api_key_hash
        assert bcrypt.checkpw(api_key.encode(), webhook.api_key_hash.encode())

    async def test_get_by_id_and_api_key(
        self, session: AsyncSession, webhook_owner: ChatUser, webhook_chat: Chat
    ) -> None:
        repo = WebhookRepository(session)
        webhook, api_key = await repo.create_with_api_key(
            WebhookCreateSchema(name="хук", chat_id=webhook_chat.id),
            webhook_owner.id,
        )

        found = await repo.get_by_id_and_api_key(webhook.id, api_key)
        assert found is not None
        assert found.id == webhook.id

    async def test_get_by_id_and_wrong_api_key(
        self, session: AsyncSession, webhook_owner: ChatUser, webhook_chat: Chat
    ) -> None:
        repo = WebhookRepository(session)
        webhook, _ = await repo.create_with_api_key(
            WebhookCreateSchema(name="хук", chat_id=webhook_chat.id),
            webhook_owner.id,
        )

        assert await repo.get_by_id_and_api_key(webhook.id, "wrong") is None

    async def test_get_by_unknown_id(self, session: AsyncSession) -> None:
        assert (
            await WebhookRepository(session).get_by_id_and_api_key("nope", "k") is None
        )

    async def test_regenerate_api_key(
        self, session: AsyncSession, webhook_owner: ChatUser, webhook_chat: Chat
    ) -> None:
        repo = WebhookRepository(session)
        webhook, old_key = await repo.create_with_api_key(
            WebhookCreateSchema(name="хук", chat_id=webhook_chat.id),
            webhook_owner.id,
        )

        _, new_key = await repo.regenerate_api_key(webhook.id)

        assert new_key != old_key
        assert await repo.get_by_id_and_api_key(webhook.id, old_key) is None
        assert await repo.get_by_id_and_api_key(webhook.id, new_key) is not None

    async def test_regenerate_unknown_webhook_raises(
        self, session: AsyncSession
    ) -> None:
        with pytest.raises(NotFoundError):
            await WebhookRepository(session).regenerate_api_key("nope")

    async def test_list_by_creator(
        self, session: AsyncSession, webhook_owner: ChatUser, webhook_chat: Chat
    ) -> None:
        other = await create_chat_user(session, "other@example.com")
        repo = WebhookRepository(session)
        await repo.create_with_api_key(
            WebhookCreateSchema(name="мой", chat_id=webhook_chat.id), webhook_owner.id
        )
        await repo.create_with_api_key(
            WebhookCreateSchema(name="чужой", chat_id=webhook_chat.id), other.id
        )

        mine = await repo.list_by_creator(webhook_owner.id)
        assert [w.name for w in mine] == ["мой"]

    async def test_list_by_chat(
        self, session: AsyncSession, webhook_owner: ChatUser, webhook_chat: Chat
    ) -> None:
        other_chat = await create_chat(session, "other@chat.agent")
        repo = WebhookRepository(session)
        await repo.create_with_api_key(
            WebhookCreateSchema(name="здесь", chat_id=webhook_chat.id),
            webhook_owner.id,
        )
        await repo.create_with_api_key(
            WebhookCreateSchema(name="там", chat_id=other_chat.id), webhook_owner.id
        )

        assert [w.name for w in await repo.list_by_chat(webhook_chat.id)] == ["здесь"]

    async def test_update(
        self, session: AsyncSession, webhook_owner: ChatUser, webhook_chat: Chat
    ) -> None:
        repo = WebhookRepository(session)
        webhook, _ = await repo.create_with_api_key(
            WebhookCreateSchema(name="хук", chat_id=webhook_chat.id),
            webhook_owner.id,
        )

        updated = await repo.update(
            webhook.id,
            WebhookUpdateSchema(name="новое имя", is_active=False),
            commit=True,
        )
        assert updated.name == "новое имя"
        assert updated.is_active is False

    async def test_update_wipes_omitted_fields(
        self, session: AsyncSession, webhook_owner: ChatUser, webhook_chat: Chat
    ) -> None:
        """Известный дефект: частичное обновление затирает незаданные поля.

        ``AsyncRepository.update`` делает полный ``model_dump()``, поэтому
        ``WebhookUpdateSchema(name=...)`` записывает ``is_active=None`` и
        ``webhook_metadata=None``. Колонка ``is_active`` — ``NOT NULL``, так
        что переименование вебхука через ``PUT /api/webhooks/{id}`` падает на
        коммите.
        """
        import sqlalchemy as sa

        repo = WebhookRepository(session)
        webhook, _ = await repo.create_with_api_key(
            WebhookCreateSchema(
                name="хук", chat_id=webhook_chat.id, webhook_metadata={"a": 1}
            ),
            webhook_owner.id,
        )

        updated = await repo.update(webhook.id, WebhookUpdateSchema(name="новое имя"))
        assert updated.is_active is None
        assert updated.webhook_metadata is None
        with pytest.raises(sa.exc.IntegrityError):
            await session.commit()
        await session.rollback()

    async def test_check_rate_limit_is_a_stub(self, session: AsyncSession) -> None:
        assert await WebhookRepository(session).check_rate_limit("any") is True

    async def test_log_webhook_call_is_a_stub(self, session: AsyncSession) -> None:
        assert (
            await WebhookRepository(session).log_webhook_call(
                webhook_id="any", success=True, request_data={}, response_data={}
            )
            is None
        )
