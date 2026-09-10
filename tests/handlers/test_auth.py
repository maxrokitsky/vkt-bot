"""Хендлер ``/login``."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vkt_bot.core.handlers.auth import LoginHandler
from vkt_bot.core.models import ChatUser, LogEntry, LoginToken
from vkt_bot.core.repositories.log_entry import LogEntryRepository
from vkt_bot.core.repositories.login_token import LoginTokenRepository
from vkt_bot.core.repositories.user import ChatUserRepository

from tests.conftest import table_count
from tests.factories import create_chat_user, make_event

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from vkt_dispatcher import Dispatcher
    from vkteams_client.types import Event

    from tests.conftest import FakeBot
    from vkt_bot.config import VktSettings


class TestLoginHandler:
    """``/login``."""

    def test_matches_login_command(self, dispatcher: Dispatcher) -> None:
        assert LoginHandler.check(make_event("new_message", text="/login"), dispatcher)

    def test_rejects_other_commands(self, dispatcher: Dispatcher) -> None:
        assert not LoginHandler.check(
            make_event("new_message", text="/logout"), dispatcher
        )

    async def test_creates_token(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        await LoginHandler.handle(make_event("new_message", text="/login"), dispatcher)

        assert await table_count(session, LoginToken) == 1

    async def test_creates_user_if_missing(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        await LoginHandler.handle(make_event("new_message", text="/login"), dispatcher)

        assert await ChatUserRepository(session).get_or_none("1234567890")

    async def test_stores_sender_name(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        """Вход — первая точка, где мы узнаём имя владельца."""
        await LoginHandler.handle(make_event("new_message", text="/login"), dispatcher)

        user = await ChatUserRepository(session).get("1234567890")
        assert user.display_name == "Иван Иванов"

    async def test_reuses_existing_user(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        await create_chat_user(session, "1234567890")

        await LoginHandler.handle(make_event("new_message", text="/login"), dispatcher)

        assert await table_count(session, ChatUser) == 1

    async def test_sends_link_when_public_url_is_set(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        settings: VktSettings,
    ) -> None:
        await LoginHandler.handle(make_event("new_message", text="/login"), dispatcher)

        token = (await LoginTokenRepository(session).list())[0]
        text = fake_bot.texts[-1]
        assert f"{settings.public_url}/login?token={token.token}" in text
        assert "5 минут" in text

    async def test_sends_token_only_without_public_url(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        settings: VktSettings,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "public_url", None)

        await LoginHandler.handle(make_event("new_message", text="/login"), dispatcher)

        token = (await LoginTokenRepository(session).list())[0]
        text = fake_bot.texts[-1]
        assert "http" not in text
        assert token.token in text
        assert "@[1234567890]" in text

    async def test_message_goes_to_the_same_chat(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session_factory: object
    ) -> None:
        await LoginHandler.handle(make_event("new_message", text="/login"), dispatcher)

        assert fake_bot.sent[0].kwargs["chat_id"] == "681869378@chat.agent"

    async def test_token_expires_in_five_minutes(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        is_postgres: bool,
    ) -> None:
        """Срок жизни токена — 5 минут по часам базы.

        Колонка ``expires_at`` без таймзоны, поэтому сравнивать надо с
        «сейчас» той же базы: PostgreSQL приводит значение к своей TimeZone,
        SQLite хранит как есть (UTC).
        """
        import datetime

        import sqlalchemy as sa

        await LoginHandler.handle(make_event("new_message", text="/login"), dispatcher)

        token = (await LoginTokenRepository(session).list())[0]
        if is_postgres:
            db_now = await session.scalar(sa.select(sa.func.localtimestamp()))
        else:
            db_now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)

        delta = token.expires_at - db_now
        # Часы приложения и базы расходятся на миллисекунды, отсюда допуск.
        assert (
            datetime.timedelta(minutes=4)
            < delta
            < datetime.timedelta(minutes=5, seconds=1)
        )

    async def test_expires_at_is_naive(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        """Известная мина: ``expires_at`` хранится без таймзоны.

        ``webapp/api/auth.py`` при логине делает
        ``expires_at.replace(tzinfo=timezone.utc)``. Если TimeZone базы не
        UTC, срок жизни токена поедет на её смещение.
        """
        await LoginHandler.handle(make_event("new_message", text="/login"), dispatcher)

        token = (await LoginTokenRepository(session).list())[0]
        assert token.expires_at.tzinfo is None

    async def test_two_calls_create_two_tokens(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        event = make_event("new_message", text="/login")
        await LoginHandler.handle(event, dispatcher)
        await LoginHandler.handle(event, dispatcher)

        assert await table_count(session, LoginToken) == 2

    async def test_logs_creation(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session_factory: object,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level("INFO", logger="vkt_bot.handlers.auth"):
            await LoginHandler.handle(
                make_event("new_message", text="/login"), dispatcher
            )

        assert "auth.login_token_created" in caplog.text


def owner_login(owner_id: str) -> Event:
    """Событие ``/login`` от владельца бота."""
    return make_event("new_message", text="/login", **{"from": {"userId": owner_id}})


class TestOwnerPromotion:
    """Владелец получает права суперпользователя при входе."""

    async def test_grants_superuser_on_first_login(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        owner_id: str,
    ) -> None:
        await LoginHandler.handle(owner_login(owner_id), dispatcher)

        user = await ChatUserRepository(session).get(owner_id)
        assert user.is_superuser

    async def test_promotes_user_created_earlier(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        owner_id: str,
    ) -> None:
        """Строка владельца могла появиться раньше — например, из чата."""
        await create_chat_user(session, owner_id)

        await LoginHandler.handle(owner_login(owner_id), dispatcher)

        user = await ChatUserRepository(session).get(owner_id)
        assert user.is_superuser

    async def test_leaves_other_users_alone(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        await LoginHandler.handle(make_event("new_message", text="/login"), dispatcher)

        user = await ChatUserRepository(session).get("1234567890")
        assert not user.is_superuser

    async def test_no_promotion_without_owner_id(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        settings: VktSettings,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "owner_id", None)

        await LoginHandler.handle(make_event("new_message", text="/login"), dispatcher)

        user = await ChatUserRepository(session).get("1234567890")
        assert not user.is_superuser

    async def test_promotion_is_audited(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        owner_id: str,
    ) -> None:
        await LoginHandler.handle(owner_login(owner_id), dispatcher)

        entries = await LogEntryRepository(session).list()
        assert [(e.entity_id, e.action_type.value) for e in entries] == [
            (owner_id, "update")
        ]

    async def test_repeated_login_does_not_re_audit(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        owner_id: str,
    ) -> None:
        """Повышение идемпотентно: второй вход не пишет ещё одну запись."""
        event = owner_login(owner_id)
        await LoginHandler.handle(event, dispatcher)
        await LoginHandler.handle(event, dispatcher)

        assert await table_count(session, LogEntry) == 1

    async def test_no_audit_when_already_superuser(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        owner_id: str,
    ) -> None:
        await create_chat_user(session, owner_id, is_superuser=True)

        await LoginHandler.handle(owner_login(owner_id), dispatcher)

        assert await table_count(session, LogEntry) == 0

    async def test_logs_promotion(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session_factory: object,
        owner_id: str,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level("INFO", logger="vkt_bot.handlers.auth"):
            await LoginHandler.handle(owner_login(owner_id), dispatcher)

        assert "auth.superuser_granted" in caplog.text
