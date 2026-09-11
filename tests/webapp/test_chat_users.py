"""``/api/chat-users``."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from vkt_bot.core.models import ChatMembership, EventRecord, RoleAssignment
from vkt_bot.core.repositories.event import EventRepository
from vkt_bot.core.repositories.user import ChatUserRepository

from tests.conftest import auth_headers, table_count
from tests.factories import assign_role, create_chat, create_chat_user, create_role

if TYPE_CHECKING:
    import httpx
    from sqlalchemy.ext.asyncio import AsyncSession

    from vkt_bot.config import VktSettings
    from vkt_bot.core.models import ChatUser


class TestListChatUsers:
    """``GET /api/chat-users``."""

    async def test_lists_users(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        await create_chat_user(session, "second@example.com")

        body = (
            await client.get("/api/chat-users", headers=auth_headers(user.id))
        ).json()

        assert body["total"] == 2
        assert {item["id"] for item in body["items"]} == {
            user.id,
            "second@example.com",
        }

    async def test_includes_photo_url(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        """Ссылка на аватар уходит в панель как есть: авторизации не нужно."""
        avatar = "https://rapi.icq.net/avatar/get?targetSn=ivan&size=1024"
        await create_chat_user(session, "ivan@example.com", photo_url=avatar)

        body = (
            await client.get(
                "/api/chat-users?search=ivan@example.com",
                headers=auth_headers(user.id),
            )
        ).json()

        assert body["items"][0]["photo_url"] == avatar

    async def test_includes_is_owner(
        self, client: httpx.AsyncClient, owner: ChatUser
    ) -> None:
        body = (
            await client.get("/api/chat-users", headers=auth_headers(owner.id))
        ).json()
        assert body["items"][0]["is_owner"] is True

    async def test_pagination(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        for i in range(5):
            await create_chat_user(session, f"u{i}@example.com")

        body = (
            await client.get(
                "/api/chat-users",
                params={"page": 1, "size": 2},
                headers=auth_headers(user.id),
            )
        ).json()

        assert len(body["items"]) == 2
        assert body["total"] == 6

    async def test_requires_authentication(self, client: httpx.AsyncClient) -> None:
        assert (await client.get("/api/chat-users")).status_code == 403


class TestFilterChatUsersByChat:
    """``GET /api/chat-users?chat_id=...``."""

    async def test_only_members_of_the_chat(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        chat = await create_chat(session, "a@chat.agent")
        member = await create_chat_user(session, "member@example.com")
        await create_chat_user(session, "stranger@example.com")
        session.add(ChatMembership(chat_id=chat.id, user_id=member.id))
        await session.commit()

        body = (
            await client.get(
                "/api/chat-users",
                params={"chat_id": chat.id},
                headers=auth_headers(user.id),
            )
        ).json()

        assert body["total"] == 1
        assert [item["id"] for item in body["items"]] == ["member@example.com"]

    async def test_left_member_disappears(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        """Строка ``ChatUser`` после ухода остаётся, а членство — нет."""
        chat = await create_chat(session, "a@chat.agent")
        membership = ChatMembership(chat_id=chat.id, user_id=user.id)
        session.add(membership)
        await session.commit()
        await session.delete(membership)
        await session.commit()

        body = (
            await client.get(
                "/api/chat-users",
                params={"chat_id": chat.id},
                headers=auth_headers(user.id),
            )
        ).json()

        assert body["items"] == []

    async def test_combines_with_search(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        chat = await create_chat(session, "a@chat.agent")
        ivan = await create_chat_user(session, "ivan@example.com", first_name="Иван")
        petr = await create_chat_user(session, "petr@example.com", first_name="Пётр")
        session.add_all(
            [
                ChatMembership(chat_id=chat.id, user_id=ivan.id),
                ChatMembership(chat_id=chat.id, user_id=petr.id),
            ]
        )
        await session.commit()

        body = (
            await client.get(
                "/api/chat-users",
                params={"chat_id": chat.id, "search": "Иван"},
                headers=auth_headers(user.id),
            )
        ).json()

        assert body["total"] == 1
        assert body["items"][0]["id"] == "ivan@example.com"

    async def test_unknown_chat_is_empty(
        self, client: httpx.AsyncClient, user: ChatUser
    ) -> None:
        body = (
            await client.get(
                "/api/chat-users",
                params={"chat_id": "nope@chat.agent"},
                headers=auth_headers(user.id),
            )
        ).json()

        assert body == {"items": [], "total": 0, "page": 1, "size": 20, "pages": 0}


class TestGetChatUser:
    """``GET /api/chat-users/{user_id}``."""

    async def test_without_roles_and_chats(
        self, client: httpx.AsyncClient, user: ChatUser
    ) -> None:
        response = await client.get(
            f"/api/chat-users/{user.id}", headers=auth_headers(user.id)
        )

        assert response.status_code == 200
        assert response.json() == {
            "id": user.id,
            "is_superuser": False,
            "is_bot": False,
            "is_owner": False,
            "first_name": None,
            "last_name": None,
            "nick": None,
            "about": None,
            "photo_url": None,
            "display_name": user.id,
            "roles": [],
            "chats": [],
        }

    async def test_with_roles(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        role = await create_role(session, "devs")
        await assign_role(session, user.id, role.id)

        body = (
            await client.get(
                f"/api/chat-users/{user.id}", headers=auth_headers(user.id)
            )
        ).json()

        assert body["roles"] == [{"id": str(role.id), "name": "devs"}]

    async def test_with_chats(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        chat = await create_chat(session, "a@chat.agent")
        session.add(ChatMembership(chat_id=chat.id, user_id=user.id))
        await session.commit()

        body = (
            await client.get(
                f"/api/chat-users/{user.id}", headers=auth_headers(user.id)
            )
        ).json()

        assert body["chats"] == [{"id": "a@chat.agent", "type": "group", "title": None}]

    async def test_unknown_user(
        self, client: httpx.AsyncClient, user: ChatUser
    ) -> None:
        response = await client.get(
            "/api/chat-users/ghost@example.com", headers=auth_headers(user.id)
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Chat user not found"


class TestUpdateChatUser:
    """``PATCH /api/chat-users/{user_id}`` — только владелец."""

    async def test_grants_admin(
        self,
        client: httpx.AsyncClient,
        session: AsyncSession,
        owner: ChatUser,
        user: ChatUser,
    ) -> None:
        response = await client.patch(
            f"/api/chat-users/{user.id}",
            json={"is_superuser": True},
            headers=auth_headers(owner.id),
        )

        assert response.status_code == 200
        assert response.json()["is_superuser"] is True
        await session.refresh(user)
        assert user.is_superuser is True

    async def test_revokes_admin(
        self,
        client: httpx.AsyncClient,
        session: AsyncSession,
        owner: ChatUser,
        superuser: ChatUser,
    ) -> None:
        response = await client.patch(
            f"/api/chat-users/{superuser.id}",
            json={"is_superuser": False},
            headers=auth_headers(owner.id),
        )

        assert response.json()["is_superuser"] is False

    async def test_writes_audit_log(
        self,
        client: httpx.AsyncClient,
        session: AsyncSession,
        owner: ChatUser,
        user: ChatUser,
    ) -> None:
        await client.patch(
            f"/api/chat-users/{user.id}",
            json={"is_superuser": True},
            headers=auth_headers(owner.id),
        )

        assert await table_count(session, EventRecord) == 1

    async def test_same_value_is_a_noop(
        self,
        client: httpx.AsyncClient,
        session: AsyncSession,
        owner: ChatUser,
        user: ChatUser,
    ) -> None:
        response = await client.patch(
            f"/api/chat-users/{user.id}",
            json={"is_superuser": False},
            headers=auth_headers(owner.id),
        )

        assert response.status_code == 200
        assert await table_count(session, EventRecord) == 0

    async def test_owner_cannot_be_modified(
        self, client: httpx.AsyncClient, owner: ChatUser
    ) -> None:
        response = await client.patch(
            f"/api/chat-users/{owner.id}",
            json={"is_superuser": False},
            headers=auth_headers(owner.id),
        )

        assert response.status_code == 400
        assert "Owner is always admin" in response.json()["detail"]

    async def test_unknown_user(
        self, client: httpx.AsyncClient, owner: ChatUser
    ) -> None:
        response = await client.patch(
            "/api/chat-users/ghost@example.com",
            json={"is_superuser": True},
            headers=auth_headers(owner.id),
        )
        assert response.status_code == 404

    async def test_superuser_is_not_enough(
        self, client: httpx.AsyncClient, superuser: ChatUser, user: ChatUser
    ) -> None:
        response = await client.patch(
            f"/api/chat-users/{user.id}",
            json={"is_superuser": True},
            headers=auth_headers(superuser.id),
        )
        assert response.status_code == 403

    async def test_missing_field(
        self, client: httpx.AsyncClient, owner: ChatUser, user: ChatUser
    ) -> None:
        response = await client.patch(
            f"/api/chat-users/{user.id}", json={}, headers=auth_headers(owner.id)
        )
        assert response.status_code == 422

    async def test_owner_check_is_skipped_without_owner_id(
        self,
        client: httpx.AsyncClient,
        owner: ChatUser,
        user: ChatUser,
        monkeypatch: pytest.MonkeyPatch,
        settings: VktSettings,
    ) -> None:
        """Без ``OWNER_ID`` доступ к ручке не может получить никто."""
        monkeypatch.setattr(settings, "owner_id", None)
        response = await client.patch(
            f"/api/chat-users/{user.id}",
            json={"is_superuser": True},
            headers=auth_headers(owner.id),
        )
        assert response.status_code == 403


class TestAssignRole:
    """``POST /api/chat-users/{user_id}/roles/{role_id}``."""

    async def test_assigns_role(
        self,
        client: httpx.AsyncClient,
        session: AsyncSession,
        superuser: ChatUser,
        user: ChatUser,
    ) -> None:
        role = await create_role(session, "devs")

        response = await client.post(
            f"/api/chat-users/{user.id}/roles/{role.id}",
            headers=auth_headers(superuser.id),
        )

        assert response.status_code == 201
        assert response.json() == {"message": "Role assigned successfully"}
        assert await table_count(session, RoleAssignment) == 1

    async def test_writes_audit_log(
        self,
        client: httpx.AsyncClient,
        session: AsyncSession,
        superuser: ChatUser,
        user: ChatUser,
    ) -> None:
        role = await create_role(session, "devs")
        await client.post(
            f"/api/chat-users/{user.id}/roles/{role.id}",
            headers=auth_headers(superuser.id),
        )
        assert await table_count(session, EventRecord) == 1
        entry = (await EventRepository(session).list())[0]
        assert entry.type == "role.assigned"
        # id назначения известен только после flush — иначе в журнале "None".
        assert entry.entity_id != "None"
        assert entry.payload["role"] == "devs"

    async def test_duplicate_assignment_is_rejected(
        self,
        client: httpx.AsyncClient,
        session: AsyncSession,
        superuser: ChatUser,
        user: ChatUser,
    ) -> None:
        role = await create_role(session, "devs")
        await assign_role(session, user.id, role.id)

        response = await client.post(
            f"/api/chat-users/{user.id}/roles/{role.id}",
            headers=auth_headers(superuser.id),
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "User already has this role"

    async def test_unknown_user(
        self, client: httpx.AsyncClient, session: AsyncSession, superuser: ChatUser
    ) -> None:
        role = await create_role(session, "devs")
        response = await client.post(
            f"/api/chat-users/ghost@example.com/roles/{role.id}",
            headers=auth_headers(superuser.id),
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Chat user not found"

    async def test_unknown_role(
        self, client: httpx.AsyncClient, superuser: ChatUser, user: ChatUser
    ) -> None:
        response = await client.post(
            f"/api/chat-users/{user.id}/roles/{uuid.uuid4()}",
            headers=auth_headers(superuser.id),
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Role not found"

    async def test_invalid_role_uuid(
        self, client: httpx.AsyncClient, superuser: ChatUser, user: ChatUser
    ) -> None:
        response = await client.post(
            f"/api/chat-users/{user.id}/roles/not-a-uuid",
            headers=auth_headers(superuser.id),
        )
        assert response.status_code == 422

    async def test_plain_user_is_forbidden(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        role = await create_role(session, "devs")
        response = await client.post(
            f"/api/chat-users/{user.id}/roles/{role.id}",
            headers=auth_headers(user.id),
        )
        assert response.status_code == 403


class TestRemoveRole:
    """``DELETE /api/chat-users/{user_id}/roles/{role_id}``."""

    async def test_removes_assignment(
        self,
        client: httpx.AsyncClient,
        session: AsyncSession,
        superuser: ChatUser,
        user: ChatUser,
    ) -> None:
        role = await create_role(session, "devs")
        await assign_role(session, user.id, role.id)

        response = await client.delete(
            f"/api/chat-users/{user.id}/roles/{role.id}",
            headers=auth_headers(superuser.id),
        )

        assert response.status_code == 204
        assert await table_count(session, RoleAssignment) == 0

    async def test_user_keeps_other_roles(
        self,
        client: httpx.AsyncClient,
        session: AsyncSession,
        superuser: ChatUser,
        user: ChatUser,
    ) -> None:
        devs = await create_role(session, "devs")
        qa = await create_role(session, "qa")
        await assign_role(session, user.id, devs.id)
        await assign_role(session, user.id, qa.id)

        await client.delete(
            f"/api/chat-users/{user.id}/roles/{devs.id}",
            headers=auth_headers(superuser.id),
        )

        remaining = await ChatUserRepository(session).list_by_roles(["qa"])
        assert [u.id for u in remaining] == [user.id]

    async def test_writes_audit_log(
        self,
        client: httpx.AsyncClient,
        session: AsyncSession,
        superuser: ChatUser,
        user: ChatUser,
    ) -> None:
        role = await create_role(session, "devs")
        await assign_role(session, user.id, role.id)

        await client.delete(
            f"/api/chat-users/{user.id}/roles/{role.id}",
            headers=auth_headers(superuser.id),
        )

        assert await table_count(session, EventRecord) == 1

    async def test_missing_assignment(
        self, client: httpx.AsyncClient, session: AsyncSession, superuser: ChatUser
    ) -> None:
        role = await create_role(session, "devs")
        response = await client.delete(
            f"/api/chat-users/ghost@example.com/roles/{role.id}",
            headers=auth_headers(superuser.id),
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "User does not have this role"

    async def test_plain_user_is_forbidden(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        role = await create_role(session, "devs")
        await assign_role(session, user.id, role.id)

        response = await client.delete(
            f"/api/chat-users/{user.id}/roles/{role.id}",
            headers=auth_headers(user.id),
        )
        assert response.status_code == 403


class TestChatUserProfile:
    """Имя и роли в ответах о участнике."""

    async def test_list_includes_roles(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        role = await create_role(session, "devs")
        await assign_role(session, user.id, role.id)

        body = (
            await client.get("/api/chat-users", headers=auth_headers(user.id))
        ).json()

        assert body["items"][0]["roles"] == [{"id": str(role.id), "name": "devs"}]

    async def test_list_without_roles(
        self, client: httpx.AsyncClient, user: ChatUser
    ) -> None:
        body = (
            await client.get("/api/chat-users", headers=auth_headers(user.id))
        ).json()
        assert body["items"][0]["roles"] == []

    async def test_display_name_from_first_and_last_name(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        await create_chat_user(
            session, "ivan@example.com", first_name="Иван", last_name="Иванов"
        )

        body = (
            await client.get(
                "/api/chat-users",
                params={"search": "ivan@example.com"},
                headers=auth_headers(user.id),
            )
        ).json()

        assert body["items"][0]["display_name"] == "Иван Иванов"

    async def test_display_name_falls_back_to_nick(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        await create_chat_user(session, "nicky@example.com", nick="nicky")

        body = (
            await client.get(
                "/api/chat-users",
                params={"search": "nicky@example.com"},
                headers=auth_headers(user.id),
            )
        ).json()

        assert body["items"][0]["display_name"] == "nicky"

    async def test_detail_keeps_profile(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        """Деталка раньше теряла имя и флаг бота — оставались только id и права."""
        bot_user = await create_chat_user(
            session, "helper@example.com", is_bot=True, first_name="Хелпер"
        )

        body = (
            await client.get(
                f"/api/chat-users/{bot_user.id}", headers=auth_headers(user.id)
            )
        ).json()

        assert body["display_name"] == "Хелпер"
        assert body["first_name"] == "Хелпер"
        assert body["is_bot"] is True

    async def test_detail_includes_chat_title(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        chat = await create_chat(session, "a@chat.agent", title="Релизы")
        session.add(ChatMembership(chat_id=chat.id, user_id=user.id))
        await session.commit()

        body = (
            await client.get(
                f"/api/chat-users/{user.id}", headers=auth_headers(user.id)
            )
        ).json()

        assert body["chats"] == [
            {"id": "a@chat.agent", "type": "group", "title": "Релизы"}
        ]

    async def test_patch_returns_roles(
        self,
        client: httpx.AsyncClient,
        session: AsyncSession,
        owner: ChatUser,
        user: ChatUser,
    ) -> None:
        """Ответ на PATCH тоже со ролями — панель обновляет строку по нему."""
        role = await create_role(session, "devs")
        await assign_role(session, user.id, role.id)

        response = await client.patch(
            f"/api/chat-users/{user.id}",
            json={"is_superuser": True},
            headers=auth_headers(owner.id),
        )

        assert response.status_code == 200
        assert response.json()["roles"] == [{"id": str(role.id), "name": "devs"}]


class TestSearchChatUsers:
    """``GET /api/chat-users?search=``."""

    async def test_by_first_name(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        await create_chat_user(session, "ivan@example.com", first_name="Ivan")
        await create_chat_user(session, "petr@example.com", first_name="Petr")

        body = (
            await client.get(
                "/api/chat-users",
                params={"search": "iva"},
                headers=auth_headers(user.id),
            )
        ).json()

        assert [item["id"] for item in body["items"]] == ["ivan@example.com"]

    async def test_by_last_name(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        await create_chat_user(session, "a@example.com", last_name="Sidorov")

        body = (
            await client.get(
                "/api/chat-users",
                params={"search": "sidor"},
                headers=auth_headers(user.id),
            )
        ).json()

        assert [item["id"] for item in body["items"]] == ["a@example.com"]

    async def test_by_nick(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        await create_chat_user(session, "a@example.com", nick="sunshine")

        body = (
            await client.get(
                "/api/chat-users",
                params={"search": "shine"},
                headers=auth_headers(user.id),
            )
        ).json()

        assert [item["id"] for item in body["items"]] == ["a@example.com"]

    async def test_by_id(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        await create_chat_user(session, "unique-one@corp.example")

        body = (
            await client.get(
                "/api/chat-users",
                params={"search": "unique-one"},
                headers=auth_headers(user.id),
            )
        ).json()

        assert [item["id"] for item in body["items"]] == ["unique-one@corp.example"]

    async def test_total_counts_only_matches(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        for i in range(4):
            await create_chat_user(session, f"dev-{i}@corp.example")

        body = (
            await client.get(
                "/api/chat-users",
                params={"search": "dev-"},
                headers=auth_headers(user.id),
            )
        ).json()

        assert body["total"] == 4

    async def test_no_matches(self, client: httpx.AsyncClient, user: ChatUser) -> None:
        body = (
            await client.get(
                "/api/chat-users",
                params={"search": "zzz-nobody"},
                headers=auth_headers(user.id),
            )
        ).json()

        assert body["items"] == []
        assert body["total"] == 0

    async def test_cyrillic_is_case_insensitive(
        self,
        client: httpx.AsyncClient,
        session: AsyncSession,
        user: ChatUser,
        is_postgres: bool,
    ) -> None:
        """``ilike`` приводит регистр кириллицы только в PostgreSQL."""
        if not is_postgres:
            pytest.skip("SQLite не приводит регистр кириллицы в LIKE")
        await create_chat_user(session, "ivan@example.com", first_name="Иван")

        body = (
            await client.get(
                "/api/chat-users",
                params={"search": "ИВАН"},
                headers=auth_headers(user.id),
            )
        ).json()

        assert [item["id"] for item in body["items"]] == ["ivan@example.com"]
