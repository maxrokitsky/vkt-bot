"""``/api/roles``."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING


from vkt_bot.core.models import Role, RoleAssignment
from vkt_bot.core.models.event import ActorType, EntityType, EventSource
from vkt_bot.core.repositories.event import EventRepository
from vkt_bot.core.repositories.role import RoleRepository

from tests.conftest import auth_headers, table_count
from tests.factories import assign_role, create_chat_user, create_role

if TYPE_CHECKING:
    import httpx
    from sqlalchemy.ext.asyncio import AsyncSession

    from vkt_bot.core.models import ChatUser


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

    async def test_creates_role(
        self, client: httpx.AsyncClient, session: AsyncSession, superuser: ChatUser
    ) -> None:
        response = await client.post(
            "/api/roles", json={"name": "devs"}, headers=auth_headers(superuser.id)
        )

        assert response.status_code == 201
        assert response.json()["name"] == "devs"
        assert await table_count(session, Role) == 1

    async def test_creation_is_audited(
        self, client: httpx.AsyncClient, session: AsyncSession, superuser: ChatUser
    ) -> None:
        """Создание роли попадает в журнал событий."""
        response = await client.post(
            "/api/roles", json={"name": "devs"}, headers=auth_headers(superuser.id)
        )

        assert response.status_code == 201
        entry = (await EventRepository(session).list())[0]
        assert entry.type == "role.created"
        assert entry.entity_type == EntityType.ROLE
        assert entry.actor_type is ActorType.USER
        assert entry.source is EventSource.PANEL
        assert entry.actor_id == superuser.id
        assert entry.summary == f"{superuser.display_name} создал роль devs"
        # Запись должна указывать на созданную роль, а не на "None".
        assert entry.entity_id == response.json()["id"]

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

    async def test_rename_is_audited(
        self, client: httpx.AsyncClient, session: AsyncSession, superuser: ChatUser
    ) -> None:
        role = await create_role(session, "devs")

        await client.patch(
            f"/api/roles/{role.id}",
            json={"name": "developers"},
            headers=auth_headers(superuser.id),
        )

        entry = (await EventRepository(session).list())[0]
        assert entry.type == "role.updated"
        assert entry.actor_id == superuser.id
        assert entry.payload["old_name"] == "devs"

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

    async def test_deletes_role(
        self, client: httpx.AsyncClient, session: AsyncSession, superuser: ChatUser
    ) -> None:
        role = await create_role(session, "devs")

        response = await client.delete(
            f"/api/roles/{role.id}", headers=auth_headers(superuser.id)
        )

        assert response.status_code == 204
        assert await table_count(session, Role) == 0

    async def test_deletion_is_audited(
        self, client: httpx.AsyncClient, session: AsyncSession, superuser: ChatUser
    ) -> None:
        role = await create_role(session, "devs")

        await client.delete(f"/api/roles/{role.id}", headers=auth_headers(superuser.id))

        entry = (await EventRepository(session).list())[0]
        assert entry.type == "role.deleted"
        assert entry.actor_id == superuser.id

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


class TestRoleMemberCount:
    """Число участников в списке ролей."""

    async def test_zero_without_members(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        await create_role(session, "devs")

        body = (await client.get("/api/roles", headers=auth_headers(user.id))).json()

        assert body["items"][0]["member_count"] == 0

    async def test_counts_members(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        role = await create_role(session, "devs")
        empty = await create_role(session, "qa")
        for i in range(3):
            member = await create_chat_user(session, f"dev-{i}@example.com")
            await assign_role(session, member.id, role.id)

        body = (await client.get("/api/roles", headers=auth_headers(user.id))).json()
        counts = {item["name"]: item["member_count"] for item in body["items"]}

        assert counts == {"devs": 3, "qa": 0}
        assert empty.name == "qa"


class TestGetRole:
    """``GET /api/roles/{role_id}``."""

    async def test_returns_members(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        role = await create_role(session, "devs")
        member = await create_chat_user(
            session, "ivan@example.com", first_name="Иван", last_name="Иванов"
        )
        await assign_role(session, member.id, role.id)

        response = await client.get(
            f"/api/roles/{role.id}", headers=auth_headers(user.id)
        )

        assert response.status_code == 200
        assert response.json() == {
            "id": str(role.id),
            "name": "devs",
            "member_count": 1,
            "members": [
                {
                    "user_id": "ivan@example.com",
                    "display_name": "Иван Иванов",
                    "is_bot": False,
                    "photo_url": None,
                }
            ],
        }

    async def test_members_sorted_by_name(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        role = await create_role(session, "devs")
        for name in ("Ярослав", "Антон", "Мария"):
            member = await create_chat_user(
                session, f"{len(name)}-{name}@example.com", first_name=name
            )
            await assign_role(session, member.id, role.id)

        body = (
            await client.get(f"/api/roles/{role.id}", headers=auth_headers(user.id))
        ).json()

        assert [member["display_name"] for member in body["members"]] == [
            "Антон",
            "Мария",
            "Ярослав",
        ]

    async def test_empty_role(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        role = await create_role(session, "devs")

        body = (
            await client.get(f"/api/roles/{role.id}", headers=auth_headers(user.id))
        ).json()

        assert body["members"] == []
        assert body["member_count"] == 0

    async def test_unknown_role(
        self, client: httpx.AsyncClient, user: ChatUser
    ) -> None:
        response = await client.get(
            f"/api/roles/{uuid.uuid4()}", headers=auth_headers(user.id)
        )
        assert response.status_code == 404

    async def test_requires_authentication(
        self, client: httpx.AsyncClient, session: AsyncSession
    ) -> None:
        role = await create_role(session, "devs")
        assert (await client.get(f"/api/roles/{role.id}")).status_code == 403


class TestAddRoleMember:
    """``POST /api/roles/{role_id}/members``."""

    async def test_adds_member(
        self, client: httpx.AsyncClient, session: AsyncSession, superuser: ChatUser
    ) -> None:
        role = await create_role(session, "devs")
        member = await create_chat_user(session, "ivan@example.com", first_name="Иван")

        response = await client.post(
            f"/api/roles/{role.id}/members",
            json={"user_id": member.id},
            headers=auth_headers(superuser.id),
        )

        assert response.status_code == 201
        assert response.json() == {
            "user_id": member.id,
            "display_name": "Иван",
            "is_bot": False,
            "photo_url": None,
        }
        assert await table_count(session, RoleAssignment) == 1

    async def test_writes_audit_log(
        self, client: httpx.AsyncClient, session: AsyncSession, superuser: ChatUser
    ) -> None:
        role = await create_role(session, "devs")
        member = await create_chat_user(session, "ivan@example.com")

        await client.post(
            f"/api/roles/{role.id}/members",
            json={"user_id": member.id},
            headers=auth_headers(superuser.id),
        )

        entries = await EventRepository(session).list()
        assert [entry.type for entry in entries] == ["role.assigned"]
        entry = entries[0]
        assert entry.entity_type == EntityType.ROLE_ASSIGNMENT
        assert entry.actor_type is ActorType.USER
        assert entry.payload["role"] == "devs"
        assert entry.payload["target_id"] == member.id
        # id назначения известен только после flush — иначе в журнале "None".
        assert entry.entity_id != "None"

    async def test_rejects_duplicate(
        self, client: httpx.AsyncClient, session: AsyncSession, superuser: ChatUser
    ) -> None:
        role = await create_role(session, "devs")
        member = await create_chat_user(session, "ivan@example.com")
        await assign_role(session, member.id, role.id)

        response = await client.post(
            f"/api/roles/{role.id}/members",
            json={"user_id": member.id},
            headers=auth_headers(superuser.id),
        )

        assert response.status_code == 400
        assert await table_count(session, RoleAssignment) == 1

    async def test_unknown_role(
        self, client: httpx.AsyncClient, session: AsyncSession, superuser: ChatUser
    ) -> None:
        member = await create_chat_user(session, "ivan@example.com")

        response = await client.post(
            f"/api/roles/{uuid.uuid4()}/members",
            json={"user_id": member.id},
            headers=auth_headers(superuser.id),
        )

        assert response.status_code == 404

    async def test_unknown_user(
        self, client: httpx.AsyncClient, session: AsyncSession, superuser: ChatUser
    ) -> None:
        role = await create_role(session, "devs")

        response = await client.post(
            f"/api/roles/{role.id}/members",
            json={"user_id": "nobody@example.com"},
            headers=auth_headers(superuser.id),
        )

        assert response.status_code == 404

    async def test_forbidden_for_plain_user(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        role = await create_role(session, "devs")

        response = await client.post(
            f"/api/roles/{role.id}/members",
            json={"user_id": user.id},
            headers=auth_headers(user.id),
        )

        assert response.status_code == 403
        assert await table_count(session, RoleAssignment) == 0


class TestRemoveRoleMember:
    """``DELETE /api/roles/{role_id}/members/{user_id}``."""

    async def test_removes_member(
        self, client: httpx.AsyncClient, session: AsyncSession, superuser: ChatUser
    ) -> None:
        role = await create_role(session, "devs")
        member = await create_chat_user(session, "ivan@example.com")
        await assign_role(session, member.id, role.id)

        response = await client.delete(
            f"/api/roles/{role.id}/members/{member.id}",
            headers=auth_headers(superuser.id),
        )

        assert response.status_code == 204
        assert await table_count(session, RoleAssignment) == 0

    async def test_writes_audit_log(
        self, client: httpx.AsyncClient, session: AsyncSession, superuser: ChatUser
    ) -> None:
        role = await create_role(session, "devs")
        member = await create_chat_user(session, "ivan@example.com")
        await assign_role(session, member.id, role.id)

        await client.delete(
            f"/api/roles/{role.id}/members/{member.id}",
            headers=auth_headers(superuser.id),
        )

        entries = await EventRepository(session).list()
        assert [entry.type for entry in entries] == ["role.unassigned"]

    async def test_member_without_role(
        self, client: httpx.AsyncClient, session: AsyncSession, superuser: ChatUser
    ) -> None:
        role = await create_role(session, "devs")
        member = await create_chat_user(session, "ivan@example.com")

        response = await client.delete(
            f"/api/roles/{role.id}/members/{member.id}",
            headers=auth_headers(superuser.id),
        )

        assert response.status_code == 404

    async def test_forbidden_for_plain_user(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        role = await create_role(session, "devs")
        await assign_role(session, user.id, role.id)

        response = await client.delete(
            f"/api/roles/{role.id}/members/{user.id}",
            headers=auth_headers(user.id),
        )

        assert response.status_code == 403
        assert await table_count(session, RoleAssignment) == 1
