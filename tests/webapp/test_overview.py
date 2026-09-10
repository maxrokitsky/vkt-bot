"""``/api/overview``."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from vkt_bot.core.models.log_entry import ActionType, ActorType, EntityType, LogEntry

from tests.conftest import auth_headers
from tests.factories import create_chat, create_chat_user, create_role

if TYPE_CHECKING:
    import httpx
    from sqlalchemy.ext.asyncio import AsyncSession

    from vkt_bot.core.models import ChatUser


async def add_log(
    session: AsyncSession, *, timestamp: datetime.datetime, entity_id: str = "x"
) -> None:
    """Запись аудита с заданным временем."""
    session.add(
        LogEntry(
            timestamp=timestamp,
            actor_type=ActorType.SYSTEM,
            action_type=ActionType.CREATE,
            entity_type=EntityType.ROLE,
            entity_id=entity_id,
        )
    )
    await session.commit()


class TestCounts:
    """Счётчики для плиток."""

    async def test_counts_entities(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        await create_chat(session, "a@chat.agent")
        await create_chat(session, "b@chat.agent")
        await create_chat_user(session, "second@example.com")
        await create_role(session, "dev")

        body = (await client.get("/api/overview", headers=auth_headers(user.id))).json()

        assert body["counts"] == {
            "chats": 2,
            "chat_users": 2,
            "roles": 1,
            "webhooks": 0,
            "webhooks_active": 0,
        }

    async def test_counts_only_own_webhooks(
        self,
        client: httpx.AsyncClient,
        session: AsyncSession,
        user: ChatUser,
        patched_bot: object,  # noqa: ARG002
    ) -> None:
        from vkt_bot.core.models import Webhook

        chat = await create_chat(session, "a@chat.agent")
        other = await create_chat_user(session, "other@example.com")
        session.add_all(
            [
                Webhook(
                    name="мой",
                    chat_id=chat.id,
                    api_key_hash="hash-1",
                    created_by=user.id,
                ),
                Webhook(
                    name="мой выключенный",
                    chat_id=chat.id,
                    api_key_hash="hash-2",
                    created_by=user.id,
                    is_active=False,
                ),
                Webhook(
                    name="чужой",
                    chat_id=chat.id,
                    api_key_hash="hash-3",
                    created_by=other.id,
                ),
            ]
        )
        await session.commit()

        body = (await client.get("/api/overview", headers=auth_headers(user.id))).json()

        assert body["counts"]["webhooks"] == 2
        assert body["counts"]["webhooks_active"] == 1

    async def test_requires_auth(self, client: httpx.AsyncClient) -> None:
        assert (await client.get("/api/overview")).status_code == 403


class TestActivity:
    """Активность по дням."""

    async def test_fills_days_without_actions(
        self, client: httpx.AsyncClient, session: AsyncSession, superuser: ChatUser
    ) -> None:
        today = datetime.date.today()
        await add_log(
            session, timestamp=datetime.datetime.combine(today, datetime.time(12))
        )

        body = (
            await client.get(
                "/api/overview",
                params={"days": 3},
                headers=auth_headers(superuser.id),
            )
        ).json()

        assert body["activity_days"] == 3
        assert [point["date"] for point in body["activity"]] == [
            (today - datetime.timedelta(days=2)).isoformat(),
            (today - datetime.timedelta(days=1)).isoformat(),
            today.isoformat(),
        ]
        assert [point["count"] for point in body["activity"]] == [0, 0, 1]

    async def test_groups_by_day(
        self, client: httpx.AsyncClient, session: AsyncSession, superuser: ChatUser
    ) -> None:
        today = datetime.date.today()
        yesterday = today - datetime.timedelta(days=1)
        for hour in (9, 13, 21):
            await add_log(
                session,
                timestamp=datetime.datetime.combine(today, datetime.time(hour)),
            )
        await add_log(
            session, timestamp=datetime.datetime.combine(yesterday, datetime.time(10))
        )

        body = (
            await client.get(
                "/api/overview",
                params={"days": 2},
                headers=auth_headers(superuser.id),
            )
        ).json()

        assert [point["count"] for point in body["activity"]] == [1, 3]

    async def test_ignores_older_than_window(
        self, client: httpx.AsyncClient, session: AsyncSession, superuser: ChatUser
    ) -> None:
        long_ago = datetime.datetime.combine(
            datetime.date.today() - datetime.timedelta(days=30), datetime.time(12)
        )
        await add_log(session, timestamp=long_ago)

        body = (
            await client.get(
                "/api/overview",
                params={"days": 7},
                headers=auth_headers(superuser.id),
            )
        ).json()

        assert sum(point["count"] for point in body["activity"]) == 0

    async def test_hidden_from_non_admin(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        await add_log(
            session,
            timestamp=datetime.datetime.combine(
                datetime.date.today(), datetime.time(12)
            ),
        )

        body = (await client.get("/api/overview", headers=auth_headers(user.id))).json()

        assert body["activity"] == []

    async def test_rejects_out_of_range_days(
        self, client: httpx.AsyncClient, superuser: ChatUser
    ) -> None:
        response = await client.get(
            "/api/overview", params={"days": 0}, headers=auth_headers(superuser.id)
        )
        assert response.status_code == 422
