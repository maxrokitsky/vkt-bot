"""Плагин ``vkt_gitlab``."""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING, Any

import pytest

from vkt_bot.core.security import get_password_hash, get_random_string
from vkt_gitlab import install
from vkt_gitlab.api import construct_messsage, fail_message, success_message
from vkt_gitlab.handlers import (
    CreateGlWebhook,
    DeleteGlWebhookHandler,
    ListGlWebhooksHandler,
)
from vkt_gitlab.models import GlWebhook
from vkt_gitlab.queries import GlWebhookByChatId, GlWebhookById
from vkt_gitlab.repositories import CreateGlWebhookSchema, GlWebhookRepository

from tests.conftest import table_count
from tests.factories import create_chat, create_chat_user, make_event

if TYPE_CHECKING:
    import httpx
    from sqlalchemy.ext.asyncio import AsyncSession
    from vkt_dispatcher import Dispatcher
    from vkteams_client.types import Event

    from tests.conftest import FakeBot
    from vkt_bot.config import VktSettings
    from vkt_bot.core.models import Chat

CHAT_ID = "681869378@chat.agent"


def pipeline_payload(status: str = "success") -> dict[str, Any]:
    """Payload события ``Pipeline Hook``."""
    return {
        "object_kind": "pipeline",
        "object_attributes": {
            "id": 31,
            "ref": "feature/login",
            "sha": "bcbb5ec396a2c0f828686f14fac9b80b780504f2",
            "status": status,
            "url": "https://gitlab.example.com/group/project/-/pipelines/31",
        },
        "user": {"name": "Иван Иванов", "username": "ivanov"},
        "project": {
            "name": "project",
            "path_with_namespace": "group/project",
            "web_url": "https://gitlab.example.com/group/project",
        },
        "commit": {
            "id": "bcbb5ec396a2c0f828686f14fac9b80b780504f2",
            "message": "fix: поправил логин\n\nподробности",
            "url": "https://gitlab.example.com/group/project/-/commit/bcbb5ec",
        },
    }


def owner_message(text: str, owner_id: str) -> Event:
    """Сообщение от владельца бота."""
    return make_event("new_message", text=text, **{"from": {"userId": owner_id}})


@pytest.fixture
async def chat(session: AsyncSession) -> Chat:
    """Чат для вебхуков GitLab."""
    return await create_chat(session, CHAT_ID)


@pytest.fixture
async def gl_webhook(
    session: AsyncSession, chat: Chat, owner_id: str
) -> tuple[GlWebhook, str]:
    """Вебхук GitLab и его секрет."""
    await create_chat_user(session, owner_id)
    secret = get_random_string()
    webhook = await GlWebhookRepository(session).create(
        CreateGlWebhookSchema(
            id=uuid.uuid4(),
            name="Пайплайны",
            chat_id=chat.id,
            created_by_id=owner_id,
            hashed_secret=get_password_hash(secret),
        ),
        commit=True,
    )
    return webhook, secret


class TestInstall:
    """Точка входа плагина."""

    def test_registers_router(self) -> None:
        from fastapi import FastAPI

        app = FastAPI()
        install(app)

        paths = {route.path for route in app.routes if hasattr(route, "path")}
        assert "/gl/webhooks" in paths
        assert "/gl/webhooks/{webhook_id}/trigger" in paths


class TestConstructMessage:
    """``construct_messsage``."""

    def test_success_template(self) -> None:
        text = construct_messsage(pipeline_payload("success"))
        assert text.startswith("✅ Пайплайн прошёл")

    def test_failure_template(self) -> None:
        text = construct_messsage(pipeline_payload("failed"))
        assert text.startswith("❌ Пайплайн упал")

    def test_any_non_success_status_is_a_failure(self) -> None:
        text = construct_messsage(pipeline_payload("canceled"))
        assert text.startswith("❌")

    def test_includes_project_branch_and_author(self) -> None:
        text = construct_messsage(pipeline_payload())
        assert "group/project" in text
        assert "feature/login" in text
        assert "ivanov" in text

    def test_sha_is_truncated_to_eight_chars(self) -> None:
        text = construct_messsage(pipeline_payload())
        assert "[bcbb5ec3]" in text
        assert "bcbb5ec396a2" not in text

    def test_only_first_commit_line_is_used(self) -> None:
        text = construct_messsage(pipeline_payload())
        assert "fix: поправил логин" in text
        assert "подробности" not in text

    def test_commit_message_is_truncated(self) -> None:
        payload = pipeline_payload()
        payload["commit"]["message"] = "x" * 300
        text = construct_messsage(payload)
        assert "x" * 160 in text
        assert "x" * 161 not in text

    def test_markdown_is_not_escaped(self) -> None:
        """Известный дефект: текст уходит с ``MarkdownV2`` без экранирования.

        Спецсимволы из имени ветки или коммита ломают разметку — см.
        ROADMAP 1.5 / раздел про ``api.py``.
        """
        payload = pipeline_payload()
        payload["commit"]["message"] = "fix: [важно] (срочно) _тут_"
        text = construct_messsage(payload)
        assert "[важно] (срочно) _тут_" in text

    def test_templates_have_the_same_placeholders(self) -> None:
        import string

        def fields(template: str) -> set[str]:
            return {
                name for _, name, _, _ in string.Formatter().parse(template) if name
            }

        assert fields(success_message) == fields(fail_message)


class TestTriggerEndpoint:
    """``POST /gl/webhooks/{id}/trigger``."""

    async def test_sends_message(
        self,
        client: httpx.AsyncClient,
        gl_webhook: tuple[GlWebhook, str],
        patched_bot: FakeBot,
    ) -> None:
        webhook, secret = gl_webhook

        response = await client.post(
            f"/gl/webhooks/{webhook.id}/trigger",
            json=pipeline_payload("success"),
            headers={"X-Gitlab-Token": secret, "X-Gitlab-Event": "Pipeline Hook"},
        )

        assert response.status_code == 200
        (call,) = patched_bot.sent
        assert call.chat_id == CHAT_ID
        assert call.kwargs["parse_mode"] == "MarkdownV2"

    async def test_attaches_open_button(
        self,
        client: httpx.AsyncClient,
        gl_webhook: tuple[GlWebhook, str],
        patched_bot: FakeBot,
    ) -> None:
        webhook, secret = gl_webhook

        await client.post(
            f"/gl/webhooks/{webhook.id}/trigger",
            json=pipeline_payload(),
            headers={"X-Gitlab-Token": secret, "X-Gitlab-Event": "Pipeline Hook"},
        )

        keyboard = json.loads(patched_bot.sent[0].kwargs["inline_keyboard_markup"])
        assert keyboard == [
            [
                {
                    "text": "Открыть",
                    "url": "https://gitlab.example.com/group/project/-/pipelines/31",
                }
            ]
        ]

    async def test_updates_last_used_at(
        self,
        client: httpx.AsyncClient,
        session: AsyncSession,
        gl_webhook: tuple[GlWebhook, str],
        patched_bot: FakeBot,
    ) -> None:
        webhook, secret = gl_webhook
        assert webhook.last_used_at is None

        await client.post(
            f"/gl/webhooks/{webhook.id}/trigger",
            json=pipeline_payload(),
            headers={"X-Gitlab-Token": secret, "X-Gitlab-Event": "Pipeline Hook"},
        )

        await session.refresh(webhook)
        assert webhook.last_used_at is not None

    @pytest.mark.parametrize("status", ["running", "pending", "created", "canceled"])
    async def test_intermediate_statuses_send_nothing(
        self,
        status: str,
        client: httpx.AsyncClient,
        gl_webhook: tuple[GlWebhook, str],
        patched_bot: FakeBot,
    ) -> None:
        webhook, secret = gl_webhook

        response = await client.post(
            f"/gl/webhooks/{webhook.id}/trigger",
            json=pipeline_payload(status),
            headers={"X-Gitlab-Token": secret, "X-Gitlab-Event": "Pipeline Hook"},
        )

        assert response.status_code == 200
        assert patched_bot.calls == []

    async def test_other_events_are_ignored(
        self,
        client: httpx.AsyncClient,
        gl_webhook: tuple[GlWebhook, str],
        patched_bot: FakeBot,
    ) -> None:
        webhook, secret = gl_webhook

        response = await client.post(
            f"/gl/webhooks/{webhook.id}/trigger",
            json={},
            headers={"X-Gitlab-Token": secret, "X-Gitlab-Event": "Push Hook"},
        )

        assert response.status_code == 200
        assert patched_bot.calls == []

    async def test_wrong_token(
        self,
        client: httpx.AsyncClient,
        gl_webhook: tuple[GlWebhook, str],
        patched_bot: FakeBot,
    ) -> None:
        webhook, _ = gl_webhook

        response = await client.post(
            f"/gl/webhooks/{webhook.id}/trigger",
            json=pipeline_payload(),
            headers={"X-Gitlab-Token": "wrong", "X-Gitlab-Event": "Pipeline Hook"},
        )

        assert response.status_code == 403
        assert patched_bot.calls == []

    async def test_unknown_webhook(
        self, client: httpx.AsyncClient, patched_bot: FakeBot
    ) -> None:
        response = await client.post(
            f"/gl/webhooks/{uuid.uuid4()}/trigger",
            json=pipeline_payload(),
            headers={"X-Gitlab-Token": "any", "X-Gitlab-Event": "Pipeline Hook"},
        )

        assert response.status_code == 404

    async def test_missing_headers(
        self, client: httpx.AsyncClient, gl_webhook: tuple[GlWebhook, str]
    ) -> None:
        response = await client.post(
            f"/gl/webhooks/{gl_webhook[0].id}/trigger", json=pipeline_payload()
        )
        assert response.status_code == 422

    async def test_invalid_uuid(self, client: httpx.AsyncClient) -> None:
        response = await client.post(
            "/gl/webhooks/not-a-uuid/trigger",
            json=pipeline_payload(),
            headers={"X-Gitlab-Token": "any", "X-Gitlab-Event": "Pipeline Hook"},
        )
        assert response.status_code == 422


class TestCreateGlWebhookCommand:
    """``/glwebhookadd``."""

    async def test_creates_webhook(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        chat: Chat,
        owner_id: str,
    ) -> None:
        await create_chat_user(session, owner_id)

        await CreateGlWebhook.handle(
            owner_message("/glwebhookadd Пайплайны", owner_id), dispatcher
        )

        webhooks = await GlWebhookRepository(session).list()
        assert [w.name for w in webhooks] == ["Пайплайны"]

    async def test_reply_contains_url_and_secret(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        chat: Chat,
        owner_id: str,
        settings: VktSettings,
    ) -> None:
        await create_chat_user(session, owner_id)

        await CreateGlWebhook.handle(
            owner_message("/glwebhookadd Пайплайны", owner_id), dispatcher
        )

        (webhook,) = await GlWebhookRepository(session).list()
        text = fake_bot.texts[-1]
        assert f"{settings.public_url}/gl/webhooks/{webhook.id}" in text
        assert "Secret token:" in text
        assert "События сборочной линии" in text

    async def test_secret_is_hashed(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        chat: Chat,
        owner_id: str,
    ) -> None:
        from vkt_bot.core.security import verify_password

        await create_chat_user(session, owner_id)
        await CreateGlWebhook.handle(
            owner_message("/glwebhookadd Пайплайны", owner_id), dispatcher
        )

        (webhook,) = await GlWebhookRepository(session).list()
        secret = fake_bot.texts[-1].split("Secret token: ")[1].split("\n")[0]
        assert secret not in webhook.hashed_secret
        assert verify_password(secret, webhook.hashed_secret)

    async def test_name_keeps_spaces(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        chat: Chat,
        owner_id: str,
    ) -> None:
        await create_chat_user(session, owner_id)
        await CreateGlWebhook.handle(
            owner_message("/glwebhookadd Пайплайны бэкенда", owner_id), dispatcher
        )

        (webhook,) = await GlWebhookRepository(session).list()
        assert webhook.name == "Пайплайны бэкенда"

    async def test_without_name(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session_factory: object,
        owner_id: str,
    ) -> None:
        await CreateGlWebhook.handle(
            owner_message("/glwebhookadd", owner_id), dispatcher
        )
        assert "укажите название вебхука" in fake_bot.texts[-1]

    async def test_requires_admin(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        chat: Chat,
    ) -> None:
        await CreateGlWebhook.handle(
            make_event("new_message", text="/glwebhookadd Пайплайны"), dispatcher
        )

        assert "нет доступа" in fake_bot.texts[-1]
        assert await table_count(session, GlWebhook) == 0


class TestDeleteGlWebhookCommand:
    """``/glwebhookdel``.

    Хендлер передаёт ``args[0]`` (строку) в ``GlWebhookRepository.get``,
    хотя первичный ключ — ``UUID``. PostgreSQL приводит тип сам, SQLite
    падает, поэтому тесты ветвятся по диалекту.
    """

    async def test_deletes_webhook(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        gl_webhook: tuple[GlWebhook, str],
        owner_id: str,
        is_postgres: bool,
    ) -> None:
        webhook, _ = gl_webhook
        event = owner_message(f"/glwebhookdel {webhook.id}", owner_id)

        if not is_postgres:
            with pytest.raises(Exception, match="hex"):
                await DeleteGlWebhookHandler.handle(event, dispatcher)
            return

        await DeleteGlWebhookHandler.handle(event, dispatcher)
        assert await table_count(session, GlWebhook) == 0
        assert "удалён" in fake_bot.texts[-1]

    async def test_unknown_webhook(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session_factory: object,
        owner_id: str,
        is_postgres: bool,
    ) -> None:
        event = owner_message(f"/glwebhookdel {uuid.uuid4()}", owner_id)

        if not is_postgres:
            with pytest.raises(Exception, match="hex"):
                await DeleteGlWebhookHandler.handle(event, dispatcher)
            return

        await DeleteGlWebhookHandler.handle(event, dispatcher)
        assert "не существует" in fake_bot.texts[-1]

    async def test_non_uuid_argument(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session_factory: object,
        owner_id: str,
    ) -> None:
        """Мусор вместо ID не превращается в понятное сообщение."""
        with pytest.raises(Exception, match="hex|invalid input"):
            await DeleteGlWebhookHandler.handle(
                owner_message("/glwebhookdel не-uuid", owner_id), dispatcher
            )

    async def test_webhook_from_another_chat(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        owner_id: str,
        is_postgres: bool,
    ) -> None:
        other = await create_chat(session, "other@chat.agent")
        await create_chat_user(session, owner_id)
        webhook = await GlWebhookRepository(session).create(
            CreateGlWebhookSchema(
                id=uuid.uuid4(),
                name="Чужой",
                chat_id=other.id,
                created_by_id=owner_id,
                hashed_secret="x",
            ),
            commit=True,
        )
        event = owner_message(f"/glwebhookdel {webhook.id}", owner_id)

        if not is_postgres:
            with pytest.raises(Exception, match="hex"):
                await DeleteGlWebhookHandler.handle(event, dispatcher)
            return

        await DeleteGlWebhookHandler.handle(event, dispatcher)
        assert "зарегестрирован в другом чате" in fake_bot.texts[-1]
        assert await table_count(session, GlWebhook) == 1

    async def test_requires_admin(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        gl_webhook: tuple[GlWebhook, str],
    ) -> None:
        await DeleteGlWebhookHandler.handle(
            make_event("new_message", text=f"/glwebhookdel {gl_webhook[0].id}"),
            dispatcher,
        )

        assert "нет доступа" in fake_bot.texts[-1]
        assert await table_count(session, GlWebhook) == 1


class TestListGlWebhooksCommand:
    """``/glwebhookls``."""

    async def test_lists_webhooks(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        gl_webhook: tuple[GlWebhook, str],
    ) -> None:
        webhook, _ = gl_webhook

        await ListGlWebhooksHandler.handle(
            make_event("new_message", text="/glwebhookls"), dispatcher
        )

        text = fake_bot.texts[-1]
        assert str(webhook.id) in text
        assert "Пайплайны" in text
        assert "не использовано" in text

    async def test_shows_last_used_at(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        gl_webhook: tuple[GlWebhook, str],
    ) -> None:
        import datetime

        webhook, _ = gl_webhook
        webhook.last_used_at = datetime.datetime.now(datetime.UTC) - datetime.timedelta(
            hours=2
        )
        session.add(webhook)
        await session.commit()

        await ListGlWebhooksHandler.handle(
            make_event("new_message", text="/glwebhookls"), dispatcher
        )

        assert "последний вызов" in fake_bot.texts[-1]

    async def test_empty_chat(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session_factory: object
    ) -> None:
        await ListGlWebhooksHandler.handle(
            make_event("new_message", text="/glwebhookls"), dispatcher
        )
        assert "не зарегистрировано ни одного вебхука" in fake_bot.texts[-1]

    async def test_other_chat_is_hidden(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        owner_id: str,
    ) -> None:
        other = await create_chat(session, "other@chat.agent")
        await create_chat_user(session, owner_id)
        await GlWebhookRepository(session).create(
            CreateGlWebhookSchema(
                id=uuid.uuid4(),
                name="Чужой",
                chat_id=other.id,
                created_by_id=owner_id,
                hashed_secret="x",
            ),
            commit=True,
        )

        await ListGlWebhooksHandler.handle(
            make_event("new_message", text="/glwebhookls"), dispatcher
        )

        assert "не зарегистрировано" in fake_bot.texts[-1]

    async def test_does_not_require_admin(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        gl_webhook: tuple[GlWebhook, str],
    ) -> None:
        await ListGlWebhooksHandler.handle(
            make_event("new_message", text="/glwebhookls"), dispatcher
        )
        assert "нет доступа" not in fake_bot.texts[-1]


class TestQueries:
    """Запросы плагина."""

    async def test_by_chat_id(
        self, session: AsyncSession, gl_webhook: tuple[GlWebhook, str]
    ) -> None:
        result = (
            await GlWebhookRepository(session)
            .query(GlWebhookByChatId(chat_id=CHAT_ID))
            .list()
        )
        assert [w.id for w in result] == [gl_webhook[0].id]

    async def test_by_id(
        self, session: AsyncSession, gl_webhook: tuple[GlWebhook, str]
    ) -> None:
        result = (
            await GlWebhookRepository(session)
            .query(GlWebhookById(id=gl_webhook[0].id))
            .one()
        )
        assert result.id == gl_webhook[0].id

    async def test_by_unknown_chat(
        self, session: AsyncSession, gl_webhook: tuple[GlWebhook, str]
    ) -> None:
        result = (
            await GlWebhookRepository(session)
            .query(GlWebhookByChatId(chat_id="nope"))
            .list()
        )
        assert list(result) == []


class TestRepository:
    """``GlWebhookRepository``."""

    def test_model_is_inferred(self) -> None:
        assert GlWebhookRepository.model is GlWebhook

    async def test_default_name_is_empty(
        self, session: AsyncSession, chat: Chat, owner_id: str
    ) -> None:
        await create_chat_user(session, owner_id)
        webhook = await GlWebhookRepository(session).create(
            CreateGlWebhookSchema(
                id=uuid.uuid4(),
                chat_id=chat.id,
                created_by_id=owner_id,
                hashed_secret="x",
            ),
            commit=True,
        )
        assert webhook.name == ""

    async def test_id_is_generated_when_omitted(
        self, session: AsyncSession, chat: Chat, owner_id: str
    ) -> None:
        await create_chat_user(session, owner_id)
        webhook = await GlWebhookRepository(session).create(
            CreateGlWebhookSchema(
                chat_id=chat.id, created_by_id=owner_id, hashed_secret="x"
            ),
            commit=True,
        )
        assert isinstance(webhook.id, uuid.UUID)


class TestBrokenAdminEndpoints:
    """CRUD-ручки ``/gl/webhooks`` для панели.

    Они ссылаются на поля, которых нет в моделях (``Chat.title``,
    ``ChatUser.name``, ``GlWebhook.created_at``/``updated_at``,
    ``ChatUser.chat_user_id``), поэтому не работают — см. ROADMAP 3.10.
    """

    async def test_list_is_broken(
        self, client: httpx.AsyncClient, superuser: Any, gl_webhook: Any
    ) -> None:
        with pytest.raises(AttributeError):
            await client.get(
                "/gl/webhooks",
                headers=__import__(
                    "tests.conftest", fromlist=["auth_headers"]
                ).auth_headers(superuser.id),
            )

    async def test_get_is_broken(
        self, client: httpx.AsyncClient, superuser: Any, gl_webhook: Any
    ) -> None:
        from tests.conftest import auth_headers

        with pytest.raises(AttributeError):
            await client.get(
                f"/gl/webhooks/{gl_webhook[0].id}",
                headers=auth_headers(superuser.id),
            )

    async def test_delete_works(
        self,
        client: httpx.AsyncClient,
        session: AsyncSession,
        superuser: Any,
        gl_webhook: Any,
    ) -> None:
        from tests.conftest import auth_headers

        response = await client.delete(
            f"/gl/webhooks/{gl_webhook[0].id}", headers=auth_headers(superuser.id)
        )

        assert response.status_code == 204
        assert await table_count(session, GlWebhook) == 0
