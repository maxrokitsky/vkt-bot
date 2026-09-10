"""``/api/webhooks`` и публичный ``/webhooks/{id}``."""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING

import pytest

from vkt_bot.core.models import Webhook
from vkt_bot.core.repositories.webhook import WebhookRepository
from vkt_bot.webapp.schemas.webhook import WebhookCreateSchema, WebhookFileSchema

from tests.conftest import auth_headers, table_count
from tests.factories import create_chat, create_chat_user

if TYPE_CHECKING:
    import httpx
    from sqlalchemy.ext.asyncio import AsyncSession

    from tests.conftest import FakeBot
    from vkt_bot.core.models import Chat, ChatUser


@pytest.fixture
async def chat(session: AsyncSession) -> Chat:
    """Чат для вебхуков."""
    return await create_chat(session, "wh@chat.agent")


@pytest.fixture
async def webhook(
    session: AsyncSession, user: ChatUser, chat: Chat
) -> tuple[Webhook, str]:
    """Вебхук пользователя ``user`` и его API-ключ."""
    return await WebhookRepository(session).create_with_api_key(
        WebhookCreateSchema(name="хук", chat_id=chat.id), user.id
    )


class TestListWebhooks:
    """``GET /api/webhooks``."""

    async def test_empty(self, client: httpx.AsyncClient, user: ChatUser) -> None:
        response = await client.get("/api/webhooks", headers=auth_headers(user.id))

        assert response.status_code == 200
        assert response.json() == {"webhooks": [], "total": 0}

    async def test_only_own_webhooks(
        self,
        client: httpx.AsyncClient,
        session: AsyncSession,
        user: ChatUser,
        chat: Chat,
        webhook: tuple[Webhook, str],
    ) -> None:
        other = await create_chat_user(session, "other@example.com")
        await WebhookRepository(session).create_with_api_key(
            WebhookCreateSchema(name="чужой", chat_id=chat.id), other.id
        )

        body = (await client.get("/api/webhooks", headers=auth_headers(user.id))).json()

        assert body["total"] == 1
        assert body["webhooks"][0]["name"] == "хук"

    async def test_api_key_is_not_returned(
        self,
        client: httpx.AsyncClient,
        user: ChatUser,
        webhook: tuple[Webhook, str],
    ) -> None:
        body = (await client.get("/api/webhooks", headers=auth_headers(user.id))).json()
        assert "api_key" not in body["webhooks"][0]
        assert "api_key_hash" not in body["webhooks"][0]

    async def test_requires_authentication(self, client: httpx.AsyncClient) -> None:
        assert (await client.get("/api/webhooks")).status_code == 403


class TestCreateWebhook:
    """``POST /api/webhooks``."""

    async def test_creates_and_returns_api_key_once(
        self,
        client: httpx.AsyncClient,
        session: AsyncSession,
        user: ChatUser,
        chat: Chat,
    ) -> None:
        response = await client.post(
            "/api/webhooks",
            json={"name": "хук", "chat_id": chat.id},
            headers=auth_headers(user.id),
        )

        assert response.status_code == 200
        body = response.json()
        assert body["webhook"]["name"] == "хук"
        assert body["webhook"]["created_by"] == user.id
        assert len(body["api_key"]) > 20
        assert await table_count(session, Webhook) == 1

    async def test_metadata_is_stored(
        self, client: httpx.AsyncClient, user: ChatUser, chat: Chat
    ) -> None:
        response = await client.post(
            "/api/webhooks",
            json={
                "name": "хук",
                "chat_id": chat.id,
                "webhook_metadata": {"default_parse_mode": "HTML"},
            },
            headers=auth_headers(user.id),
        )

        assert response.json()["webhook"]["webhook_metadata"] == {
            "default_parse_mode": "HTML"
        }

    async def test_unknown_chat(
        self, client: httpx.AsyncClient, user: ChatUser
    ) -> None:
        response = await client.post(
            "/api/webhooks",
            json={"name": "хук", "chat_id": "nope@chat.agent"},
            headers=auth_headers(user.id),
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Chat not found"

    async def test_empty_name_is_rejected(
        self, client: httpx.AsyncClient, user: ChatUser, chat: Chat
    ) -> None:
        response = await client.post(
            "/api/webhooks",
            json={"name": "", "chat_id": chat.id},
            headers=auth_headers(user.id),
        )
        assert response.status_code == 422

    async def test_missing_chat_id(
        self, client: httpx.AsyncClient, user: ChatUser
    ) -> None:
        response = await client.post(
            "/api/webhooks", json={"name": "хук"}, headers=auth_headers(user.id)
        )
        assert response.status_code == 422


class TestGetWebhook:
    """``GET /api/webhooks/{id}``."""

    async def test_owner_can_read(
        self,
        client: httpx.AsyncClient,
        user: ChatUser,
        webhook: tuple[Webhook, str],
    ) -> None:
        response = await client.get(
            f"/api/webhooks/{webhook[0].id}", headers=auth_headers(user.id)
        )

        assert response.status_code == 200
        assert response.json()["id"] == webhook[0].id

    async def test_stranger_is_forbidden(
        self,
        client: httpx.AsyncClient,
        session: AsyncSession,
        webhook: tuple[Webhook, str],
    ) -> None:
        stranger = await create_chat_user(session, "stranger@example.com")

        response = await client.get(
            f"/api/webhooks/{webhook[0].id}", headers=auth_headers(stranger.id)
        )

        assert response.status_code == 403

    async def test_superuser_can_read_any(
        self,
        client: httpx.AsyncClient,
        superuser: ChatUser,
        webhook: tuple[Webhook, str],
    ) -> None:
        response = await client.get(
            f"/api/webhooks/{webhook[0].id}", headers=auth_headers(superuser.id)
        )
        assert response.status_code == 200

    async def test_unknown_webhook(
        self, client: httpx.AsyncClient, user: ChatUser
    ) -> None:
        response = await client.get("/api/webhooks/nope", headers=auth_headers(user.id))
        assert response.status_code == 404


class TestUpdateWebhook:
    """``PUT /api/webhooks/{id}``."""

    async def test_full_update(
        self,
        client: httpx.AsyncClient,
        user: ChatUser,
        webhook: tuple[Webhook, str],
    ) -> None:
        response = await client.put(
            f"/api/webhooks/{webhook[0].id}",
            json={"name": "новое имя", "is_active": False, "webhook_metadata": {}},
            headers=auth_headers(user.id),
        )

        assert response.status_code == 200
        assert response.json()["name"] == "новое имя"
        assert response.json()["is_active"] is False

    async def test_partial_update_keeps_other_fields(
        self,
        client: httpx.AsyncClient,
        user: ChatUser,
        webhook: tuple[Webhook, str],
    ) -> None:
        """``PUT`` только с ``name`` не должен обнулять остальное.

        ``AsyncRepository.update`` пишет весь переданный словарь, поэтому
        ручка отдаёт ему только заполненные поля.
        """
        response = await client.put(
            f"/api/webhooks/{webhook[0].id}",
            json={"name": "новое имя"},
            headers=auth_headers(user.id),
        )

        assert response.status_code == 200
        body = response.json()
        assert body["name"] == "новое имя"
        assert body["is_active"] is True

    async def test_stranger_is_forbidden(
        self,
        client: httpx.AsyncClient,
        session: AsyncSession,
        webhook: tuple[Webhook, str],
    ) -> None:
        stranger = await create_chat_user(session, "stranger@example.com")
        response = await client.put(
            f"/api/webhooks/{webhook[0].id}",
            json={"name": "x", "is_active": True, "webhook_metadata": {}},
            headers=auth_headers(stranger.id),
        )
        assert response.status_code == 403

    async def test_unknown_webhook(
        self, client: httpx.AsyncClient, user: ChatUser
    ) -> None:
        response = await client.put(
            "/api/webhooks/nope",
            json={"name": "x", "is_active": True, "webhook_metadata": {}},
            headers=auth_headers(user.id),
        )
        assert response.status_code == 404


class TestDeleteWebhook:
    """``DELETE /api/webhooks/{id}``."""

    async def test_deletion_is_persisted(
        self,
        client: httpx.AsyncClient,
        session: AsyncSession,
        user: ChatUser,
        webhook: tuple[Webhook, str],
    ) -> None:
        response = await client.delete(
            f"/api/webhooks/{webhook[0].id}", headers=auth_headers(user.id)
        )

        assert response.status_code == 204
        assert await table_count(session, Webhook) == 0

    async def test_stranger_is_forbidden(
        self,
        client: httpx.AsyncClient,
        session: AsyncSession,
        webhook: tuple[Webhook, str],
    ) -> None:
        stranger = await create_chat_user(session, "stranger@example.com")
        response = await client.delete(
            f"/api/webhooks/{webhook[0].id}", headers=auth_headers(stranger.id)
        )
        assert response.status_code == 403

    async def test_unknown_webhook(
        self, client: httpx.AsyncClient, user: ChatUser
    ) -> None:
        response = await client.delete(
            "/api/webhooks/nope", headers=auth_headers(user.id)
        )
        assert response.status_code == 404


class TestRegenerateApiKey:
    """``POST /api/webhooks/{id}/regenerate``."""

    async def test_returns_new_key(
        self,
        client: httpx.AsyncClient,
        user: ChatUser,
        webhook: tuple[Webhook, str],
    ) -> None:
        model, old_key = webhook

        response = await client.post(
            f"/api/webhooks/{model.id}/regenerate", headers=auth_headers(user.id)
        )

        assert response.status_code == 200
        assert response.json()["api_key"] != old_key

    async def test_old_key_stops_working(
        self,
        client: httpx.AsyncClient,
        session: AsyncSession,
        user: ChatUser,
        webhook: tuple[Webhook, str],
        patched_bot: FakeBot,
    ) -> None:
        model, old_key = webhook
        await client.post(
            f"/api/webhooks/{model.id}/regenerate", headers=auth_headers(user.id)
        )

        response = await client.post(
            f"/webhooks/{model.id}",
            json={"text": "привет"},
            headers={"Authorization": f"Bearer {old_key}"},
        )
        assert response.status_code == 404

    async def test_stranger_is_forbidden(
        self,
        client: httpx.AsyncClient,
        session: AsyncSession,
        webhook: tuple[Webhook, str],
    ) -> None:
        stranger = await create_chat_user(session, "stranger@example.com")
        response = await client.post(
            f"/api/webhooks/{webhook[0].id}/regenerate",
            headers=auth_headers(stranger.id),
        )
        assert response.status_code == 403

    async def test_unknown_webhook(
        self, client: httpx.AsyncClient, user: ChatUser
    ) -> None:
        response = await client.post(
            "/api/webhooks/nope/regenerate", headers=auth_headers(user.id)
        )
        assert response.status_code == 404


class TestPublicWebhook:
    """``POST /webhooks/{id}`` — входящий вебхук."""

    async def test_sends_text(
        self,
        client: httpx.AsyncClient,
        webhook: tuple[Webhook, str],
        patched_bot: FakeBot,
    ) -> None:
        model, api_key = webhook

        response = await client.post(
            f"/webhooks/{model.id}",
            json={"text": "привет из n8n"},
            headers={"Authorization": f"Bearer {api_key}"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["chat_id"] == model.chat_id
        (call,) = patched_bot.sent
        assert call.kwargs["text"] == "привет из n8n"

    async def test_default_parse_mode_from_metadata(
        self,
        client: httpx.AsyncClient,
        session: AsyncSession,
        user: ChatUser,
        chat: Chat,
        patched_bot: FakeBot,
    ) -> None:
        model, api_key = await WebhookRepository(session).create_with_api_key(
            WebhookCreateSchema(
                name="хук",
                chat_id=chat.id,
                webhook_metadata={"default_parse_mode": "MarkdownV2"},
            ),
            user.id,
        )

        await client.post(
            f"/webhooks/{model.id}",
            json={"text": "привет"},
            headers={"Authorization": f"Bearer {api_key}"},
        )

        assert patched_bot.sent[0].kwargs["parse_mode"] == "MarkdownV2"

    async def test_explicit_parse_mode_wins(
        self,
        client: httpx.AsyncClient,
        session: AsyncSession,
        user: ChatUser,
        chat: Chat,
        patched_bot: FakeBot,
    ) -> None:
        model, api_key = await WebhookRepository(session).create_with_api_key(
            WebhookCreateSchema(
                name="хук",
                chat_id=chat.id,
                webhook_metadata={"default_parse_mode": "MarkdownV2"},
            ),
            user.id,
        )

        await client.post(
            f"/webhooks/{model.id}",
            json={"text": "привет", "parse_mode": "HTML"},
            headers={"Authorization": f"Bearer {api_key}"},
        )

        assert patched_bot.sent[0].kwargs["parse_mode"] == "HTML"

    async def test_sends_base64_file(
        self,
        client: httpx.AsyncClient,
        webhook: tuple[Webhook, str],
        patched_bot: FakeBot,
    ) -> None:
        from vkteams_client.types import MsgLoadFileResponse

        model, api_key = webhook
        patched_bot.results["send_file"] = MsgLoadFileResponse(
            ok=True, msgId="m1", fileId="f1"
        )

        response = await client.post(
            f"/webhooks/{model.id}",
            json={
                "file": {
                    "content": base64.b64encode(b"payload").decode(),
                    "filename": "report.csv",
                    "caption": "Отчёт",
                }
            },
            headers={"Authorization": f"Bearer {api_key}"},
        )

        assert response.status_code == 200
        body = response.json()
        assert (body["msg_id"], body["file_id"]) == ("m1", "f1")
        (call,) = patched_bot.calls_of("send_file")
        assert call.kwargs["file"] == b"payload"
        assert call.kwargs["filename"] == "report.csv"

    async def test_sends_data_url_file(
        self,
        client: httpx.AsyncClient,
        webhook: tuple[Webhook, str],
        patched_bot: FakeBot,
    ) -> None:
        from vkteams_client.types import MsgLoadFileResponse

        model, api_key = webhook
        patched_bot.results["send_file"] = MsgLoadFileResponse(
            ok=True, msgId="m1", fileId="f1"
        )
        encoded = base64.b64encode(b"payload").decode()

        response = await client.post(
            f"/webhooks/{model.id}",
            json={
                "file": {
                    "data_url": f"data:text/csv;base64,{encoded}",
                    "filename": "report.csv",
                }
            },
            headers={"Authorization": f"Bearer {api_key}"},
        )

        assert response.status_code == 200
        assert patched_bot.calls_of("send_file")[0].kwargs["file"] == b"payload"

    async def test_missing_authorization(
        self, client: httpx.AsyncClient, webhook: tuple[Webhook, str]
    ) -> None:
        response = await client.post(
            f"/webhooks/{webhook[0].id}", json={"text": "привет"}
        )

        assert response.status_code == 401
        assert "Bearer" in response.json()["detail"]

    async def test_non_bearer_authorization(
        self, client: httpx.AsyncClient, webhook: tuple[Webhook, str]
    ) -> None:
        response = await client.post(
            f"/webhooks/{webhook[0].id}",
            json={"text": "привет"},
            headers={"Authorization": webhook[1]},
        )
        assert response.status_code == 401

    async def test_wrong_api_key(
        self, client: httpx.AsyncClient, webhook: tuple[Webhook, str]
    ) -> None:
        response = await client.post(
            f"/webhooks/{webhook[0].id}",
            json={"text": "привет"},
            headers={"Authorization": "Bearer wrong"},
        )

        assert response.status_code == 404
        assert "invalid API key" in response.json()["detail"]

    async def test_unknown_webhook_id(self, client: httpx.AsyncClient) -> None:
        response = await client.post(
            "/webhooks/nope",
            json={"text": "привет"},
            headers={"Authorization": "Bearer any"},
        )
        assert response.status_code == 404

    async def test_inactive_webhook(
        self,
        client: httpx.AsyncClient,
        session: AsyncSession,
        webhook: tuple[Webhook, str],
    ) -> None:
        model, api_key = webhook
        model.is_active = False
        session.add(model)
        await session.commit()

        response = await client.post(
            f"/webhooks/{model.id}",
            json={"text": "привет"},
            headers={"Authorization": f"Bearer {api_key}"},
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "Webhook is inactive"

    async def test_bot_error_becomes_500(
        self,
        client: httpx.AsyncClient,
        webhook: tuple[Webhook, str],
        patched_bot: FakeBot,
    ) -> None:
        model, api_key = webhook
        patched_bot.errors["send_text"] = RuntimeError("нет сети")

        response = await client.post(
            f"/webhooks/{model.id}",
            json={"text": "привет"},
            headers={"Authorization": f"Bearer {api_key}"},
        )

        assert response.status_code == 500
        assert "нет сети" in response.json()["detail"]

    async def test_empty_payload_is_rejected(
        self, client: httpx.AsyncClient, webhook: tuple[Webhook, str]
    ) -> None:
        response = await client.post(
            f"/webhooks/{webhook[0].id}",
            json={},
            headers={"Authorization": f"Bearer {webhook[1]}"},
        )
        assert response.status_code == 422

    async def test_text_and_file_together_are_rejected(
        self, client: httpx.AsyncClient, webhook: tuple[Webhook, str]
    ) -> None:
        response = await client.post(
            f"/webhooks/{webhook[0].id}",
            json={
                "text": "привет",
                "file": {
                    "content": base64.b64encode(b"x").decode(),
                    "filename": "f.txt",
                },
            },
            headers={"Authorization": f"Bearer {webhook[1]}"},
        )
        assert response.status_code == 422

    async def test_too_long_text_is_rejected(
        self, client: httpx.AsyncClient, webhook: tuple[Webhook, str]
    ) -> None:
        response = await client.post(
            f"/webhooks/{webhook[0].id}",
            json={"text": "x" * 4001},
            headers={"Authorization": f"Bearer {webhook[1]}"},
        )
        assert response.status_code == 422

    async def test_invalid_base64_becomes_500(
        self,
        client: httpx.AsyncClient,
        webhook: tuple[Webhook, str],
        patched_bot: FakeBot,
    ) -> None:
        """``HTTPException(400)`` внутри ``try`` перехватывается и станет 500."""
        response = await client.post(
            f"/webhooks/{webhook[0].id}",
            json={"file": {"content": "abc", "filename": "f.txt"}},
            headers={"Authorization": f"Bearer {webhook[1]}"},
        )
        assert response.status_code == 500


class TestWebhookFileSchema:
    """Разбор содержимого файла."""

    def test_base64_content(self) -> None:
        schema = WebhookFileSchema(
            content=base64.b64encode(b"payload").decode(), filename="f.bin"
        )
        assert schema.get_file_content() == b"payload"

    def test_data_url(self) -> None:
        encoded = base64.b64encode(b"payload").decode()
        schema = WebhookFileSchema(
            data_url=f"data:application/pdf;base64,{encoded}", filename="f.pdf"
        )
        assert schema.get_file_content() == b"payload"

    def test_data_url_without_base64_marker(self) -> None:
        schema = WebhookFileSchema(data_url="data:text/plain,hello", filename="f.txt")
        with pytest.raises(ValueError, match="base64"):
            schema.get_file_content()

    def test_data_url_with_wrong_scheme(self) -> None:
        schema = WebhookFileSchema(
            data_url="https://example.com/f.pdf", filename="f.pdf"
        )
        with pytest.raises(ValueError, match="[Dd]ata URL"):
            schema.get_file_content()

    def test_invalid_base64(self) -> None:
        schema = WebhookFileSchema(content="abc", filename="f.bin")
        with pytest.raises(ValueError, match="base64"):
            schema.get_file_content()

    def test_non_alphabet_characters_are_silently_dropped(self) -> None:
        """``b64decode`` без ``validate=True`` игнорирует лишние символы."""
        schema = WebhookFileSchema(content="!!!", filename="f.bin")
        assert schema.get_file_content() == b""

    def test_neither_content_nor_data_url(self) -> None:
        with pytest.raises(ValueError, match="content or data_url"):
            WebhookFileSchema(filename="f.bin")

    def test_both_content_and_data_url(self) -> None:
        with pytest.raises(ValueError, match="both"):
            WebhookFileSchema(
                content="aGk=", data_url="data:text/plain;base64,aGk=", filename="f"
            )

    def test_caption_length_limit(self) -> None:
        with pytest.raises(ValueError, match="caption"):
            WebhookFileSchema(content="aGk=", filename="f", caption="x" * 4001)
