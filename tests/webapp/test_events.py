"""``/api/events`` и лента событий чата."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import pytest

from vkt_bot.core.models.event import (
    ActorType,
    EntityType,
    EventRecord,
    EventSeverity,
    EventSource,
)

from tests.conftest import auth_headers
from tests.factories import create_chat, create_chat_user

if TYPE_CHECKING:
    import httpx
    from sqlalchemy.ext.asyncio import AsyncSession

    from vkt_bot.core.models import ChatUser

CHAT = "chat-1@chat.agent"
OTHER_CHAT = "chat-2@chat.agent"


def make_record(
    *,
    type_: str = "role.created",
    ts: datetime.datetime | None = None,
    source: EventSource = EventSource.PANEL,
    severity: EventSeverity = EventSeverity.INFO,
    actor_id: str | None = "admin@example.com",
    chat_id: str | None = None,
    entity_id: str = "role-1",
    summary: str = "Создана роль devs",
    payload: dict | None = None,
) -> EventRecord:
    """Строка журнала с разумными значениями по умолчанию."""
    return EventRecord(
        ts=ts or datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        type=type_,
        source=source,
        severity=severity,
        actor_type=ActorType.USER,
        actor_id=actor_id,
        chat_id=chat_id,
        entity_type=EntityType.ROLE,
        entity_id=entity_id,
        summary=summary,
        payload=payload,
    )


@pytest.fixture
async def events(session: AsyncSession) -> list[EventRecord]:
    """Три события: без чата, в чате и в чужом чате."""
    rows = [
        make_record(),
        make_record(
            type_="role.assigned",
            ts=datetime.datetime(2026, 2, 1, tzinfo=datetime.UTC),
            chat_id=CHAT,
            entity_id="assignment-1",
            summary="Роль devs назначена",
            payload={"role": "devs", "text": "секретный текст"},
        ),
        make_record(
            type_="chat.bot_added",
            ts=datetime.datetime(2026, 3, 1, tzinfo=datetime.UTC),
            source=EventSource.API,
            severity=EventSeverity.WARNING,
            chat_id=OTHER_CHAT,
            entity_id="chat-2",
            summary="Бота добавили в чат",
        ),
    ]
    session.add_all(rows)
    await session.commit()
    return rows


class TestListEvents:
    """``GET /api/events`` для админа."""

    async def test_requires_authentication(self, client: httpx.AsyncClient) -> None:
        assert (await client.get("/api/events")).status_code == 403

    async def test_returns_everything_newest_first(
        self,
        client: httpx.AsyncClient,
        superuser: ChatUser,
        events: list[EventRecord],  # noqa: ARG002
    ) -> None:
        response = await client.get("/api/events", headers=auth_headers(superuser.id))

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 3
        assert [item["type"] for item in body["items"]] == [
            "chat.bot_added",
            "role.assigned",
            "role.created",
        ]

    async def test_filter_by_exact_type(
        self,
        client: httpx.AsyncClient,
        superuser: ChatUser,
        events: list[EventRecord],  # noqa: ARG002
    ) -> None:
        response = await client.get(
            "/api/events",
            params={"type": "role.created"},
            headers=auth_headers(superuser.id),
        )

        assert [item["type"] for item in response.json()["items"]] == ["role.created"]

    async def test_filter_by_domain(
        self,
        client: httpx.AsyncClient,
        superuser: ChatUser,
        events: list[EventRecord],  # noqa: ARG002
    ) -> None:
        response = await client.get(
            "/api/events",
            params={"type": "role.*"},
            headers=auth_headers(superuser.id),
        )

        assert response.json()["total"] == 2

    async def test_filter_by_source(
        self,
        client: httpx.AsyncClient,
        superuser: ChatUser,
        events: list[EventRecord],  # noqa: ARG002
    ) -> None:
        response = await client.get(
            "/api/events", params={"source": "api"}, headers=auth_headers(superuser.id)
        )

        assert [item["type"] for item in response.json()["items"]] == ["chat.bot_added"]

    async def test_filter_by_severity(
        self,
        client: httpx.AsyncClient,
        superuser: ChatUser,
        events: list[EventRecord],  # noqa: ARG002
    ) -> None:
        response = await client.get(
            "/api/events",
            params={"severity": "warning"},
            headers=auth_headers(superuser.id),
        )

        assert response.json()["total"] == 1

    async def test_filter_by_chat(
        self,
        client: httpx.AsyncClient,
        superuser: ChatUser,
        events: list[EventRecord],  # noqa: ARG002
    ) -> None:
        response = await client.get(
            "/api/events", params={"chat_id": CHAT}, headers=auth_headers(superuser.id)
        )

        assert [item["entity_id"] for item in response.json()["items"]] == [
            "assignment-1"
        ]

    async def test_filter_by_date_range(
        self,
        client: httpx.AsyncClient,
        superuser: ChatUser,
        events: list[EventRecord],  # noqa: ARG002
    ) -> None:
        response = await client.get(
            "/api/events",
            params={"start_date": "2026-02-15T00:00:00Z"},
            headers=auth_headers(superuser.id),
        )

        assert response.json()["total"] == 1

    async def test_search_by_summary(
        self,
        client: httpx.AsyncClient,
        superuser: ChatUser,
        events: list[EventRecord],  # noqa: ARG002
    ) -> None:
        response = await client.get(
            "/api/events",
            params={"search_query": "назначена"},
            headers=auth_headers(superuser.id),
        )

        assert response.json()["total"] == 1

    async def test_pagination_total_matches_the_filter(
        self,
        client: httpx.AsyncClient,
        superuser: ChatUser,
        events: list[EventRecord],  # noqa: ARG002
    ) -> None:
        """``total`` — сколько нашлось, а не сколько строк в таблице."""
        response = await client.get(
            "/api/events",
            params={"type": "role.*", "size": 1},
            headers=auth_headers(superuser.id),
        )

        body = response.json()
        assert body["total"] == 2
        assert body["pages"] == 2
        assert len(body["items"]) == 1


class TestAccess:
    """Кто что видит."""

    @pytest.fixture
    async def member(self, session: AsyncSession) -> ChatUser:
        """Участник чата ``CHAT``."""
        user = await create_chat_user(session, "member@example.com")
        chat = await create_chat(session, CHAT)
        from vkt_bot.core.repositories.chat import ChatMembershipRepository

        await ChatMembershipRepository(session).add(chat.id, user.id)
        await session.commit()
        return user

    async def test_member_sees_only_their_chats(
        self,
        client: httpx.AsyncClient,
        member: ChatUser,
        events: list[EventRecord],  # noqa: ARG002
    ) -> None:
        response = await client.get("/api/events", headers=auth_headers(member.id))

        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["chat_id"] == CHAT

    async def test_member_does_not_see_message_texts(
        self,
        client: httpx.AsyncClient,
        member: ChatUser,
        events: list[EventRecord],  # noqa: ARG002
    ) -> None:
        """Роль в payload остаётся, переписка — нет."""
        response = await client.get("/api/events", headers=auth_headers(member.id))

        payload = response.json()["items"][0]["payload"]
        assert payload == {"role": "devs"}

    async def test_admin_sees_texts(
        self,
        client: httpx.AsyncClient,
        superuser: ChatUser,
        events: list[EventRecord],  # noqa: ARG002
    ) -> None:
        response = await client.get(
            "/api/events", params={"chat_id": CHAT}, headers=auth_headers(superuser.id)
        )

        assert response.json()["items"][0]["payload"]["text"] == "секретный текст"

    async def test_single_event_is_hidden_from_outsiders(
        self,
        client: httpx.AsyncClient,
        user: ChatUser,
        events: list[EventRecord],
    ) -> None:
        """Чужое событие отвечает 404, а не 403: иначе их можно перебирать."""
        response = await client.get(
            f"/api/events/{events[1].id}", headers=auth_headers(user.id)
        )

        assert response.status_code == 404

    async def test_member_reads_a_single_event(
        self,
        client: httpx.AsyncClient,
        member: ChatUser,
        events: list[EventRecord],
    ) -> None:
        response = await client.get(
            f"/api/events/{events[1].id}", headers=auth_headers(member.id)
        )

        assert response.status_code == 200
        assert response.json()["payload"] == {"role": "devs"}

    async def test_admin_reads_a_single_event(
        self,
        client: httpx.AsyncClient,
        superuser: ChatUser,
        events: list[EventRecord],
    ) -> None:
        response = await client.get(
            f"/api/events/{events[0].id}", headers=auth_headers(superuser.id)
        )

        assert response.json()["type"] == "role.created"

    async def test_missing_event(
        self, client: httpx.AsyncClient, superuser: ChatUser
    ) -> None:
        response = await client.get(
            "/api/events/999999", headers=auth_headers(superuser.id)
        )

        assert response.status_code == 404


class TestEventTypes:
    """``GET /api/events/types`` — реестр для панели."""

    async def test_returns_registry(
        self, client: httpx.AsyncClient, user: ChatUser
    ) -> None:
        response = await client.get("/api/events/types", headers=auth_headers(user.id))

        assert response.status_code == 200
        types = {item["type"]: item for item in response.json()}
        assert types["role.assigned"]["title"] == "Роль назначена"
        assert types["role.assigned"]["chat_scoped"] is True

    async def test_requires_authentication(self, client: httpx.AsyncClient) -> None:
        assert (await client.get("/api/events/types")).status_code == 403


class TestChatEvents:
    """``GET /api/chats/{id}/events``."""

    @pytest.fixture
    async def chat_with_events(self, session: AsyncSession) -> None:
        await create_chat(session, CHAT)
        session.add_all(
            [
                make_record(
                    type_="role.assigned",
                    chat_id=CHAT,
                    payload={"role": "devs", "text": "секрет"},
                ),
                # Тип без ``chat_scoped``: чат у события есть, но в ленте
                # чата ему не место.
                make_record(type_="role.created", chat_id=CHAT),
            ]
        )
        await session.commit()

    async def test_only_chat_scoped_types(
        self,
        client: httpx.AsyncClient,
        superuser: ChatUser,
        chat_with_events: None,  # noqa: ARG002
    ) -> None:
        response = await client.get(
            f"/api/chats/{CHAT}/events", headers=auth_headers(superuser.id)
        )

        assert response.status_code == 200
        assert [item["type"] for item in response.json()["items"]] == ["role.assigned"]

    async def test_unknown_chat(
        self, client: httpx.AsyncClient, superuser: ChatUser
    ) -> None:
        response = await client.get(
            "/api/chats/nope@chat.agent/events", headers=auth_headers(superuser.id)
        )

        assert response.status_code == 404

    async def test_outsider_gets_404(
        self,
        client: httpx.AsyncClient,
        user: ChatUser,
        chat_with_events: None,  # noqa: ARG002
    ) -> None:
        """Посторонний не должен отличать закрытый чат от несуществующего."""
        response = await client.get(
            f"/api/chats/{CHAT}/events", headers=auth_headers(user.id)
        )

        assert response.status_code == 404

    async def test_member_sees_the_feed_without_texts(
        self,
        client: httpx.AsyncClient,
        session: AsyncSession,
        chat_with_events: None,  # noqa: ARG002
    ) -> None:
        from vkt_bot.core.repositories.chat import ChatMembershipRepository

        member = await create_chat_user(session, "feed-member@example.com")
        await ChatMembershipRepository(session).add(CHAT, member.id)
        await session.commit()

        response = await client.get(
            f"/api/chats/{CHAT}/events", headers=auth_headers(member.id)
        )

        assert response.status_code == 200
        assert response.json()["items"][0]["payload"] == {"role": "devs"}
