"""``/api/logs``."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import pytest

from vkt_bot.core.models.log_entry import ActionType, ActorType, EntityType, LogEntry

from tests.conftest import auth_headers

if TYPE_CHECKING:
    import httpx
    from sqlalchemy.ext.asyncio import AsyncSession

    from vkt_bot.core.models import ChatUser


@pytest.fixture
async def entries(session: AsyncSession) -> list[LogEntry]:
    """Три записи аудита."""
    rows = [
        LogEntry(
            timestamp=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
            actor_type=ActorType.WEB_USER,
            actor_id="admin@example.com",
            action_type=ActionType.CREATE,
            entity_type=EntityType.ROLE,
            entity_id="role-1",
            description="Created role devs",
            details={"name": "devs"},
        ),
        LogEntry(
            timestamp=datetime.datetime(2026, 2, 1, tzinfo=datetime.UTC),
            actor_type=ActorType.SYSTEM,
            actor_id=None,
            action_type=ActionType.DELETE,
            entity_type=EntityType.CHAT_USER,
            entity_id="user-1",
            description="Deleted user",
        ),
        LogEntry(
            timestamp=datetime.datetime(2026, 3, 1, tzinfo=datetime.UTC),
            actor_type=ActorType.WEB_USER,
            actor_id="admin@example.com",
            action_type=ActionType.ASSIGN,
            entity_type=EntityType.ROLE_ASSIGNMENT,
            entity_id="ra-1",
            description="Assigned role",
        ),
    ]
    session.add_all(rows)
    await session.commit()
    return rows


class TestListLogs:
    """``GET /api/logs``."""

    async def test_empty(self, client: httpx.AsyncClient, superuser: ChatUser) -> None:
        response = await client.get("/api/logs", headers=auth_headers(superuser.id))

        assert response.status_code == 200
        assert response.json() == {
            "items": [],
            "total": 0,
            "page": 1,
            "size": 20,
            "pages": 0,
        }

    async def test_newest_first(
        self,
        client: httpx.AsyncClient,
        superuser: ChatUser,
        entries: list[LogEntry],
    ) -> None:
        body = (
            await client.get("/api/logs", headers=auth_headers(superuser.id))
        ).json()

        assert [item["entity_id"] for item in body["items"]] == [
            "ra-1",
            "user-1",
            "role-1",
        ]

    async def test_details_are_returned(
        self,
        client: httpx.AsyncClient,
        superuser: ChatUser,
        entries: list[LogEntry],
    ) -> None:
        body = (
            await client.get("/api/logs", headers=auth_headers(superuser.id))
        ).json()
        entry = next(i for i in body["items"] if i["entity_id"] == "role-1")
        assert entry["details"] == {"name": "devs"}

    async def test_filter_by_actor_type(
        self,
        client: httpx.AsyncClient,
        superuser: ChatUser,
        entries: list[LogEntry],
    ) -> None:
        body = (
            await client.get(
                "/api/logs",
                params={"actor_type": "system"},
                headers=auth_headers(superuser.id),
            )
        ).json()

        assert [item["entity_id"] for item in body["items"]] == ["user-1"]

    async def test_filter_by_actor_id(
        self,
        client: httpx.AsyncClient,
        superuser: ChatUser,
        entries: list[LogEntry],
    ) -> None:
        body = (
            await client.get(
                "/api/logs",
                params={"actor_id": "admin@example.com"},
                headers=auth_headers(superuser.id),
            )
        ).json()

        assert len(body["items"]) == 2

    async def test_filter_by_action_type(
        self,
        client: httpx.AsyncClient,
        superuser: ChatUser,
        entries: list[LogEntry],
    ) -> None:
        body = (
            await client.get(
                "/api/logs",
                params={"action_type": "assign"},
                headers=auth_headers(superuser.id),
            )
        ).json()

        assert [item["entity_id"] for item in body["items"]] == ["ra-1"]

    async def test_filter_by_entity_type(
        self,
        client: httpx.AsyncClient,
        superuser: ChatUser,
        entries: list[LogEntry],
    ) -> None:
        body = (
            await client.get(
                "/api/logs",
                params={"entity_type": "role"},
                headers=auth_headers(superuser.id),
            )
        ).json()

        assert [item["entity_id"] for item in body["items"]] == ["role-1"]

    async def test_filter_by_entity_id(
        self,
        client: httpx.AsyncClient,
        superuser: ChatUser,
        entries: list[LogEntry],
    ) -> None:
        body = (
            await client.get(
                "/api/logs",
                params={"entity_id": "user-1"},
                headers=auth_headers(superuser.id),
            )
        ).json()

        assert [item["entity_id"] for item in body["items"]] == ["user-1"]

    async def test_filter_by_date_range(
        self,
        client: httpx.AsyncClient,
        superuser: ChatUser,
        entries: list[LogEntry],
    ) -> None:
        body = (
            await client.get(
                "/api/logs",
                params={
                    "start_date": "2026-01-15T00:00:00Z",
                    "end_date": "2026-02-15T00:00:00Z",
                },
                headers=auth_headers(superuser.id),
            )
        ).json()

        assert [item["entity_id"] for item in body["items"]] == ["user-1"]

    async def test_search_by_description(
        self,
        client: httpx.AsyncClient,
        superuser: ChatUser,
        entries: list[LogEntry],
    ) -> None:
        body = (
            await client.get(
                "/api/logs",
                params={"search_query": "role devs"},
                headers=auth_headers(superuser.id),
            )
        ).json()

        assert [item["entity_id"] for item in body["items"]] == ["role-1"]

    async def test_combined_filters(
        self,
        client: httpx.AsyncClient,
        superuser: ChatUser,
        entries: list[LogEntry],
    ) -> None:
        body = (
            await client.get(
                "/api/logs",
                params={"actor_type": "web_user", "action_type": "create"},
                headers=auth_headers(superuser.id),
            )
        ).json()

        assert [item["entity_id"] for item in body["items"]] == ["role-1"]

    async def test_unknown_enum_value_is_422(
        self, client: httpx.AsyncClient, superuser: ChatUser
    ) -> None:
        response = await client.get(
            "/api/logs",
            params={"actor_type": "alien"},
            headers=auth_headers(superuser.id),
        )
        assert response.status_code == 422

    async def test_pagination(
        self,
        client: httpx.AsyncClient,
        superuser: ChatUser,
        entries: list[LogEntry],
    ) -> None:
        body = (
            await client.get(
                "/api/logs",
                params={"page": 2, "size": 2},
                headers=auth_headers(superuser.id),
            )
        ).json()

        assert len(body["items"]) == 1
        assert body["page"] == 2
        assert body["pages"] == 2

    async def test_plain_user_is_forbidden(
        self, client: httpx.AsyncClient, user: ChatUser
    ) -> None:
        assert (
            await client.get("/api/logs", headers=auth_headers(user.id))
        ).status_code == 403


class TestGetLog:
    """``GET /api/logs/{log_id}``."""

    async def test_returns_entry(
        self,
        client: httpx.AsyncClient,
        superuser: ChatUser,
        entries: list[LogEntry],
    ) -> None:
        response = await client.get(
            f"/api/logs/{entries[0].id}", headers=auth_headers(superuser.id)
        )

        assert response.status_code == 200
        assert response.json()["entity_id"] == "role-1"

    async def test_unknown_id_leaks_not_found_error(
        self, client: httpx.AsyncClient, superuser: ChatUser
    ) -> None:
        """Известный дефект: ``NotFoundError`` не превращается в 404.

        У ручки нет ``get_or_none``/обработчика исключения, поэтому ошибка
        доходит до ASGI-слоя (в проде — 500).
        """
        from vkt_bot.db.exceptions import NotFoundError

        with pytest.raises(NotFoundError):
            await client.get("/api/logs/99999", headers=auth_headers(superuser.id))

    async def test_invalid_id_is_422(
        self, client: httpx.AsyncClient, superuser: ChatUser
    ) -> None:
        response = await client.get(
            "/api/logs/not-a-number", headers=auth_headers(superuser.id)
        )
        assert response.status_code == 422

    async def test_plain_user_is_forbidden(
        self, client: httpx.AsyncClient, user: ChatUser, entries: list[LogEntry]
    ) -> None:
        response = await client.get(
            f"/api/logs/{entries[0].id}", headers=auth_headers(user.id)
        )
        assert response.status_code == 403
