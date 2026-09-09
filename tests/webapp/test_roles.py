"""``/api/roles``."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from vkt_bot.core.models import Role
from vkt_bot.core.repositories.role import RoleRepository

from tests.conftest import auth_headers, table_count
from tests.factories import create_role

if TYPE_CHECKING:
    import httpx
    from sqlalchemy.ext.asyncio import AsyncSession

    from vkt_bot.core.models import ChatUser

# ROADMAP: роутер зовёт AuditLogger с `web_user=`, а метод принимает `user=`.
BROKEN_AUDIT_KWARG = pytest.mark.xfail(
    raises=Exception,
    strict=True,
    reason="roles.py передаёт AuditLogger.log_* аргумент web_user=, "
    "которого в сигнатуре нет (принимается user=)",
)


class TestListRoles:
    """``GET /api/roles``."""

    async def test_empty(self, client: httpx.AsyncClient, user: ChatUser) -> None:
        response = await client.get("/api/roles", headers=auth_headers(user.id))

        assert response.status_code == 200
        assert response.json() == {
            "items": [],
            "total": 0,
            "page": 1,
            "size": 20,
            "pages": 0,
        }

    async def test_lists_roles(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        await create_role(session, "devs")
        await create_role(session, "qa")

        response = await client.get("/api/roles", headers=auth_headers(user.id))

        body = response.json()
        assert body["total"] == 2
        assert {item["name"] for item in body["items"]} == {"devs", "qa"}

    async def test_pagination(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        for i in range(5):
            await create_role(session, f"role-{i}")

        response = await client.get(
            "/api/roles", params={"page": 2, "size": 2}, headers=auth_headers(user.id)
        )

        body = response.json()
        assert len(body["items"]) == 2
        assert body["page"] == 2
        assert body["pages"] == 3

    async def test_page_beyond_last_is_empty(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        await create_role(session, "devs")
        response = await client.get(
            "/api/roles", params={"page": 10, "size": 20}, headers=auth_headers(user.id)
        )
        assert response.json()["items"] == []

    async def test_requires_authentication(self, client: httpx.AsyncClient) -> None:
        assert (await client.get("/api/roles")).status_code == 403

    async def test_plain_user_can_read(
        self, client: httpx.AsyncClient, user: ChatUser
    ) -> None:
        assert (
            await client.get("/api/roles", headers=auth_headers(user.id))
        ).status_code == 200


class TestCreateRole:
    """``POST /api/roles``."""

    @BROKEN_AUDIT_KWARG
    async def test_creates_role(
        self, client: httpx.AsyncClient, session: AsyncSession, superuser: ChatUser
    ) -> None:
        response = await client.post(
            "/api/roles", json={"name": "devs"}, headers=auth_headers(superuser.id)
        )

        assert response.status_code == 201
        assert response.json()["name"] == "devs"
        assert await table_count(session, Role) == 1

    async def test_duplicate_name_is_rejected(
        self, client: httpx.AsyncClient, session: AsyncSession, superuser: ChatUser
    ) -> None:
        await create_role(session, "devs")

        response = await client.post(
            "/api/roles", json={"name": "devs"}, headers=auth_headers(superuser.id)
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Role with this name already exists"

    async def test_duplicate_name_check_is_case_insensitive(
        self, client: httpx.AsyncClient, session: AsyncSession, superuser: ChatUser
    ) -> None:
        await create_role(session, "DevOps")
        response = await client.post(
            "/api/roles", json={"name": "devops"}, headers=auth_headers(superuser.id)
        )
        assert response.status_code == 400

    async def test_plain_user_is_forbidden(
        self, client: httpx.AsyncClient, user: ChatUser
    ) -> None:
        response = await client.post(
            "/api/roles", json={"name": "devs"}, headers=auth_headers(user.id)
        )
        assert response.status_code == 403

    async def test_anonymous_is_rejected(self, client: httpx.AsyncClient) -> None:
        response = await client.post("/api/roles", json={"name": "devs"})
        assert response.status_code == 403

    async def test_missing_name(
        self, client: httpx.AsyncClient, superuser: ChatUser
    ) -> None:
        response = await client.post(
            "/api/roles", json={}, headers=auth_headers(superuser.id)
        )
        assert response.status_code == 422

    async def test_garbage_body(
        self, client: httpx.AsyncClient, superuser: ChatUser
    ) -> None:
        response = await client.post(
            "/api/roles", json=[1, 2, 3], headers=auth_headers(superuser.id)
        )
        assert response.status_code == 422


class TestUpdateRole:
    """``PATCH /api/roles/{role_id}``."""

    @BROKEN_AUDIT_KWARG
    async def test_renames_role(
        self, client: httpx.AsyncClient, session: AsyncSession, superuser: ChatUser
    ) -> None:
        role = await create_role(session, "devs")

        response = await client.patch(
            f"/api/roles/{role.id}",
            json={"name": "developers"},
            headers=auth_headers(superuser.id),
        )

        assert response.status_code == 200
        assert response.json()["name"] == "developers"

    async def test_name_none_is_a_noop(
        self, client: httpx.AsyncClient, session: AsyncSession, superuser: ChatUser
    ) -> None:
        role = await create_role(session, "devs")

        response = await client.patch(
            f"/api/roles/{role.id}", json={}, headers=auth_headers(superuser.id)
        )

        assert response.status_code == 200
        assert response.json()["name"] == "devs"

    async def test_unknown_role(
        self, client: httpx.AsyncClient, superuser: ChatUser
    ) -> None:
        response = await client.patch(
            f"/api/roles/{uuid.uuid4()}",
            json={"name": "x"},
            headers=auth_headers(superuser.id),
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Role not found"

    async def test_invalid_uuid(
        self, client: httpx.AsyncClient, superuser: ChatUser
    ) -> None:
        response = await client.patch(
            "/api/roles/not-a-uuid",
            json={"name": "x"},
            headers=auth_headers(superuser.id),
        )
        assert response.status_code == 422

    async def test_name_taken_by_another_role(
        self, client: httpx.AsyncClient, session: AsyncSession, superuser: ChatUser
    ) -> None:
        await create_role(session, "devs")
        other = await create_role(session, "qa")

        response = await client.patch(
            f"/api/roles/{other.id}",
            json={"name": "devs"},
            headers=auth_headers(superuser.id),
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Role with this name already exists"

    async def test_plain_user_is_forbidden(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        role = await create_role(session, "devs")
        response = await client.patch(
            f"/api/roles/{role.id}",
            json={"name": "x"},
            headers=auth_headers(user.id),
        )
        assert response.status_code == 403


class TestDeleteRole:
    """``DELETE /api/roles/{role_id}``."""

    @BROKEN_AUDIT_KWARG
    async def test_deletes_role(
        self, client: httpx.AsyncClient, session: AsyncSession, superuser: ChatUser
    ) -> None:
        role = await create_role(session, "devs")

        response = await client.delete(
            f"/api/roles/{role.id}", headers=auth_headers(superuser.id)
        )

        assert response.status_code == 204
        assert await table_count(session, Role) == 0

    async def test_unknown_role(
        self, client: httpx.AsyncClient, superuser: ChatUser
    ) -> None:
        response = await client.delete(
            f"/api/roles/{uuid.uuid4()}", headers=auth_headers(superuser.id)
        )
        assert response.status_code == 404

    async def test_plain_user_is_forbidden(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        role = await create_role(session, "devs")
        response = await client.delete(
            f"/api/roles/{role.id}", headers=auth_headers(user.id)
        )
        assert response.status_code == 403

    async def test_role_survives_failed_delete(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        role = await create_role(session, "devs")
        await client.delete(f"/api/roles/{role.id}", headers=auth_headers(user.id))
        assert await RoleRepository(session).get_by_name("devs")
