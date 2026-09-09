"""Хендлер ``/login``."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vkt_bot.core.handlers.auth import LoginHandler
from vkt_bot.core.models import ChatUser, LoginToken
from vkt_bot.core.repositories.login_token import LoginTokenRepository

from tests.conftest import table_count
from tests.factories import create_chat_user, make_event

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from vkt_dispatcher import Dispatcher

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

        from vkt_bot.core.repositories.user import ChatUserRepository

        assert await ChatUserRepository(session).get_or_none("1234567890")

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
        with caplog.at_level("INFO", logger="vkt_bot.core.handlers.auth"):
            await LoginHandler.handle(
                make_event("new_message", text="/login"), dispatcher
            )

        assert "Created login token" in caplog.text
