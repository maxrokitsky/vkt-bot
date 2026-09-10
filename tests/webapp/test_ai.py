"""``/api/ai``: сессии агента и расход токенов.

Диалог с агентом — это вопрос человека и подложенная в промпт переписка
его чата. Поэтому здесь проверяется не столько формат ответа, сколько кто
что видит.
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import pytest

from vkt_ai.models import AgentMessage, AgentSession, SessionStatus
from vkt_ai.prompts import build_prompt

from tests.conftest import auth_headers
from tests.factories import create_chat, create_chat_user

if TYPE_CHECKING:
    import httpx
    from sqlalchemy.ext.asyncio import AsyncSession

    from vkt_bot.core.models import ChatUser

CHAT = "111@chat.agent"
SECRET = "999@chat.agent"


async def make_session(
    session: AsyncSession,
    *,
    user_id: str,
    chat_id: str = CHAT,
    question: str = "кто дежурный?",
    history: str | None = None,
    tokens: tuple[int, int] = (100, 20),
    status: SessionStatus = SessionStatus.DONE,
    created_at: datetime.datetime | None = None,
    answer: str = "Дежурный — Иван.",
) -> AgentSession:
    """Готовый диалог: вопрос и ответ."""
    row = AgentSession(
        chat_id=chat_id,
        user_id=user_id,
        status=status,
        tokens_in=tokens[0],
        tokens_out=tokens[1],
    )
    if created_at is not None:
        row.created_at = created_at
        row.updated_at = created_at
    session.add(row)
    await session.flush()
    session.add(
        AgentMessage(
            session_id=row.id, role="user", content=build_prompt(question, history)
        )
    )
    session.add(AgentMessage(session_id=row.id, role="assistant", content=answer))
    await session.commit()
    return row


@pytest.fixture
async def people(session: AsyncSession) -> None:
    await create_chat(session, CHAT, title="Поддержка")
    await create_chat_user(session, "member@example.com", first_name="Иван")
    await create_chat_user(session, "other@example.com", first_name="Пётр")


@pytest.mark.usefixtures("people")
class TestListSessions:
    """``GET /api/ai/sessions``."""

    async def test_user_sees_only_own(
        self, client: httpx.AsyncClient, session: AsyncSession
    ) -> None:
        await make_session(session, user_id="member@example.com", question="мой вопрос")
        await make_session(
            session, user_id="other@example.com", question="чужой вопрос"
        )

        response = await client.get(
            "/api/ai/sessions", headers=auth_headers("member@example.com")
        )

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["user_id"] == "member@example.com"
        assert "чужой вопрос" not in response.text

    async def test_admin_sees_everything(
        self,
        client: httpx.AsyncClient,
        session: AsyncSession,
        superuser: ChatUser,
    ) -> None:
        await make_session(session, user_id="member@example.com")
        await make_session(session, user_id="other@example.com")

        response = await client.get(
            "/api/ai/sessions", headers=auth_headers(superuser.id)
        )

        assert response.json()["total"] == 2

    async def test_question_preview_without_chat_history(
        self, client: httpx.AsyncClient, session: AsyncSession
    ) -> None:
        """Автоконтекст наружу не отдаётся: панель — не способ читать чаты."""
        await make_session(
            session,
            user_id="member@example.com",
            question="о чём тут договорились?",
            history="Иван: КОДОВОЕ-СЛОВО-АРБУЗ",
        )

        response = await client.get(
            "/api/ai/sessions", headers=auth_headers("member@example.com")
        )

        item = response.json()["items"][0]
        assert "о чём тут договорились?" in item["question"]
        assert "АРБУЗ" not in response.text
        assert "история чата" in item["question"]

    async def test_shows_tokens_and_chat_title(
        self, client: httpx.AsyncClient, session: AsyncSession
    ) -> None:
        await make_session(session, user_id="member@example.com", tokens=(300, 45))

        item = (
            await client.get(
                "/api/ai/sessions", headers=auth_headers("member@example.com")
            )
        ).json()["items"][0]

        assert item["tokens_in"] == 300
        assert item["tokens_out"] == 45
        assert item["chat_title"] == "Поддержка"
        assert item["user_name"] == "Иван"

    async def test_filter_by_status(
        self, client: httpx.AsyncClient, session: AsyncSession
    ) -> None:
        await make_session(session, user_id="member@example.com")
        await make_session(
            session, user_id="member@example.com", status=SessionStatus.FAILED
        )

        response = await client.get(
            "/api/ai/sessions",
            params={"session_status": "failed"},
            headers=auth_headers("member@example.com"),
        )

        assert response.json()["total"] == 1

    async def test_admin_filter_by_user(
        self, client: httpx.AsyncClient, session: AsyncSession, superuser: ChatUser
    ) -> None:
        await make_session(session, user_id="member@example.com")
        await make_session(session, user_id="other@example.com")

        response = await client.get(
            "/api/ai/sessions",
            params={"user_id": "other@example.com"},
            headers=auth_headers(superuser.id),
        )

        assert response.json()["total"] == 1

    async def test_user_filter_does_not_widen_access(
        self, client: httpx.AsyncClient, session: AsyncSession
    ) -> None:
        """Фильтр по чужому id не должен становиться способом их прочитать."""
        await make_session(session, user_id="other@example.com")

        response = await client.get(
            "/api/ai/sessions",
            params={"user_id": "other@example.com"},
            headers=auth_headers("member@example.com"),
        )

        assert response.json()["total"] == 0

    async def test_filter_by_chat(
        self, client: httpx.AsyncClient, session: AsyncSession
    ) -> None:
        await make_session(session, user_id="member@example.com", chat_id=CHAT)
        await make_session(session, user_id="member@example.com", chat_id=SECRET)

        response = await client.get(
            "/api/ai/sessions",
            params={"chat_id": SECRET},
            headers=auth_headers("member@example.com"),
        )

        assert response.json()["total"] == 1

    async def test_filter_by_date_range(
        self, client: httpx.AsyncClient, session: AsyncSession
    ) -> None:
        now = datetime.datetime.now()
        await make_session(
            session,
            user_id="member@example.com",
            created_at=now - datetime.timedelta(days=30),
        )
        await make_session(session, user_id="member@example.com", created_at=now)

        response = await client.get(
            "/api/ai/sessions",
            params={"start_date": (now - datetime.timedelta(days=1)).isoformat()},
            headers=auth_headers("member@example.com"),
        )

        assert response.json()["total"] == 1

    async def test_empty_list(self, client: httpx.AsyncClient) -> None:
        response = await client.get(
            "/api/ai/sessions", headers=auth_headers("member@example.com")
        )

        assert response.status_code == 200
        assert response.json() == {
            "items": [],
            "total": 0,
            "page": 1,
            "size": 20,
            "pages": 0,
        }

    async def test_requires_auth(self, client: httpx.AsyncClient) -> None:
        assert (await client.get("/api/ai/sessions")).status_code == 403


@pytest.mark.usefixtures("people")
class TestSessionDetail:
    """``GET /api/ai/sessions/{id}``."""

    async def test_own_session(
        self, client: httpx.AsyncClient, session: AsyncSession
    ) -> None:
        row = await make_session(session, user_id="member@example.com")

        response = await client.get(
            f"/api/ai/sessions/{row.id}", headers=auth_headers("member@example.com")
        )

        assert response.status_code == 200
        body = response.json()
        assert [m["role"] for m in body["messages"]] == ["user", "assistant"]
        assert body["messages"][1]["content"] == "Дежурный — Иван."

    async def test_foreign_session_is_not_found(
        self, client: httpx.AsyncClient, session: AsyncSession
    ) -> None:
        """404, а не 403: иначе по кодам перебирается чужая активность."""
        row = await make_session(session, user_id="other@example.com")

        response = await client.get(
            f"/api/ai/sessions/{row.id}", headers=auth_headers("member@example.com")
        )

        assert response.status_code == 404

    async def test_admin_reads_any_session(
        self, client: httpx.AsyncClient, session: AsyncSession, superuser: ChatUser
    ) -> None:
        row = await make_session(session, user_id="other@example.com")

        response = await client.get(
            f"/api/ai/sessions/{row.id}", headers=auth_headers(superuser.id)
        )

        assert response.status_code == 200

    async def test_history_is_stripped_from_messages(
        self, client: httpx.AsyncClient, session: AsyncSession, superuser: ChatUser
    ) -> None:
        """Даже админу: читать чаты через карточку сессии — обход проверок."""
        row = await make_session(
            session,
            user_id="member@example.com",
            history="Иван: КОДОВОЕ-СЛОВО-АРБУЗ",
        )

        response = await client.get(
            f"/api/ai/sessions/{row.id}", headers=auth_headers(superuser.id)
        )

        assert "АРБУЗ" not in response.text

    async def test_session_without_messages(
        self, client: httpx.AsyncClient, session: AsyncSession
    ) -> None:
        """Сессия могла сорваться до первого сообщения — карточка не падает."""
        row = AgentSession(chat_id=CHAT, user_id="member@example.com")
        session.add(row)
        await session.commit()

        response = await client.get(
            f"/api/ai/sessions/{row.id}", headers=auth_headers("member@example.com")
        )

        assert response.status_code == 200
        assert response.json()["session"]["question"] is None
        assert response.json()["messages"] == []

    async def test_missing_session(
        self, client: httpx.AsyncClient, superuser: ChatUser
    ) -> None:
        response = await client.get(
            "/api/ai/sessions/0f1e6a4c-0000-4000-8000-000000000000",
            headers=auth_headers(superuser.id),
        )

        assert response.status_code == 404


@pytest.mark.usefixtures("people")
class TestUsage:
    """``GET /api/ai/usage``."""

    async def test_totals_for_admin(
        self, client: httpx.AsyncClient, session: AsyncSession, superuser: ChatUser
    ) -> None:
        await make_session(session, user_id="member@example.com", tokens=(100, 10))
        await make_session(session, user_id="other@example.com", tokens=(200, 20))

        body = (
            await client.get("/api/ai/usage", headers=auth_headers(superuser.id))
        ).json()

        assert body["totals"]["sessions"] == 2
        assert body["totals"]["tokens_in"] == 300
        assert body["totals"]["tokens_out"] == 30
        assert body["totals"]["users"] == 2

    async def test_user_sees_only_own_spend(
        self, client: httpx.AsyncClient, session: AsyncSession
    ) -> None:
        await make_session(session, user_id="member@example.com", tokens=(100, 10))
        await make_session(session, user_id="other@example.com", tokens=(999, 99))

        body = (
            await client.get(
                "/api/ai/usage", headers=auth_headers("member@example.com")
            )
        ).json()

        assert body["totals"]["sessions"] == 1
        assert body["totals"]["tokens_in"] == 100
        # Чужой расход — чужая активность, поэтому топ участников пуст.
        assert body["top_users"] == []

    async def test_top_users_for_admin(
        self, client: httpx.AsyncClient, session: AsyncSession, superuser: ChatUser
    ) -> None:
        await make_session(session, user_id="member@example.com", tokens=(10, 1))
        await make_session(session, user_id="other@example.com", tokens=(500, 50))

        body = (
            await client.get("/api/ai/usage", headers=auth_headers(superuser.id))
        ).json()

        assert [row["id"] for row in body["top_users"]] == [
            "other@example.com",
            "member@example.com",
        ]
        assert body["top_users"][0]["name"] == "Пётр"
        assert body["top_users"][0]["tokens"] == 550

    async def test_by_day_covers_every_day(
        self, client: httpx.AsyncClient, session: AsyncSession, superuser: ChatUser
    ) -> None:
        """Дни без обращений тоже в ряду — иначе график рвётся."""
        await make_session(session, user_id="member@example.com")

        body = (
            await client.get(
                "/api/ai/usage", params={"days": 7}, headers=auth_headers(superuser.id)
            )
        ).json()

        assert len(body["by_day"]) == 7
        assert sum(point["sessions"] for point in body["by_day"]) == 1

    async def test_old_sessions_are_out_of_the_window(
        self, client: httpx.AsyncClient, session: AsyncSession, superuser: ChatUser
    ) -> None:
        await make_session(
            session,
            user_id="member@example.com",
            created_at=datetime.datetime.now() - datetime.timedelta(days=40),
        )

        body = (
            await client.get(
                "/api/ai/usage", params={"days": 7}, headers=auth_headers(superuser.id)
            )
        ).json()

        assert body["totals"]["sessions"] == 0

    async def test_failed_sessions_are_counted(
        self, client: httpx.AsyncClient, session: AsyncSession, superuser: ChatUser
    ) -> None:
        await make_session(
            session, user_id="member@example.com", status=SessionStatus.FAILED
        )

        body = (
            await client.get("/api/ai/usage", headers=auth_headers(superuser.id))
        ).json()

        assert body["totals"]["failed"] == 1

    async def test_top_chats_name_falls_back_to_id(
        self, client: httpx.AsyncClient, session: AsyncSession, superuser: ChatUser
    ) -> None:
        """У обсуждения своего чата в таблице нет — показываем id."""
        await make_session(session, user_id="member@example.com", chat_id=SECRET)

        body = (
            await client.get("/api/ai/usage", headers=auth_headers(superuser.id))
        ).json()

        assert body["top_chats"][0]["name"] == SECRET

    async def test_empty(self, client: httpx.AsyncClient, superuser: ChatUser) -> None:
        body = (
            await client.get("/api/ai/usage", headers=auth_headers(superuser.id))
        ).json()

        assert body["totals"]["sessions"] == 0
        assert body["top_users"] == []


@pytest.mark.usefixtures("people")
class TestStatus:
    """``GET /api/ai/status``."""

    async def test_reports_settings(self, client: httpx.AsyncClient) -> None:
        """Панель должна отличать «выключен» от «никто не спрашивал»."""
        response = await client.get(
            "/api/ai/status", headers=auth_headers("member@example.com")
        )

        assert response.status_code == 200
        body = response.json()
        assert body["configured"] is False
        assert body["enabled"] is False
        assert body["max_steps"] > 0
        assert "model" in body

    async def test_requires_auth(self, client: httpx.AsyncClient) -> None:
        assert (await client.get("/api/ai/status")).status_code == 403
