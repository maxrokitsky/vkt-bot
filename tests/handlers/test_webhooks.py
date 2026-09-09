"""Хендлеры управления вебхуками из чата."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from vkt_bot.core.handlers.callback import WebhookCallbackData
from vkt_bot.core.handlers.webhooks import (
    CreateWebhookHandler,
    DeleteWebhookHandler,
    ListWebhooksHandler,
    RegenerateWebhookKeyHandler,
    ToggleWebhookHandler,
    WebhookConfirmationHandler,
    WebhookInfoHandler,
)
from vkt_bot.core.models import Webhook
from vkt_bot.core.repositories.webhook import WebhookRepository
from vkt_bot.webapp.schemas.webhook import WebhookCreateSchema

from tests.conftest import table_count
from tests.factories import create_chat, create_chat_user, make_event

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from vkt_dispatcher import Dispatcher
    from vkteams_client.types import Event

    from tests.conftest import FakeBot
    from vkt_bot.config import VktSettings
    from vkt_bot.core.models import Chat

CHAT_ID = "681869378@chat.agent"


def owner_message(text: str, owner_id: str) -> Event:
    """Сообщение от владельца бота."""
    return make_event("new_message", text=text, **{"from": {"userId": owner_id}})


@pytest.fixture
async def chat(session: AsyncSession) -> Chat:
    """Чат, из которого приходят команды."""
    return await create_chat(session, CHAT_ID)


@pytest.fixture
async def webhook(
    session: AsyncSession, chat: Chat, owner_id: str
) -> tuple[Webhook, str]:
    """Вебхук в этом чате."""
    await create_chat_user(session, owner_id)
    return await WebhookRepository(session).create_with_api_key(
        WebhookCreateSchema(name="Мои уведомления", chat_id=chat.id), owner_id
    )


class TestCreateWebhook:
    """``/createwebhook``."""

    async def test_creates_webhook(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        chat: Chat,
        owner_id: str,
    ) -> None:
        await CreateWebhookHandler.handle(
            owner_message("/createwebhook Мои уведомления", owner_id), dispatcher
        )

        webhooks = await WebhookRepository(session).list_by_chat(CHAT_ID)
        assert [w.name for w in webhooks] == ["Мои уведомления"]

    async def test_reply_contains_url_and_key(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        chat: Chat,
        owner_id: str,
        settings: VktSettings,
    ) -> None:
        await CreateWebhookHandler.handle(
            owner_message("/createwebhook Хук", owner_id), dispatcher
        )

        (webhook,) = await WebhookRepository(session).list_by_chat(CHAT_ID)
        call = fake_bot.sent[-1]
        assert f"{settings.public_url}/webhooks/{webhook.id}" in call.text
        assert call.kwargs["parse_mode"] == "MarkdownV2"
        assert call.kwargs["reply_msg_id"] == "6752739791872001111"

    async def test_name_can_contain_spaces(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        chat: Chat,
        owner_id: str,
    ) -> None:
        await CreateWebhookHandler.handle(
            owner_message("/createwebhook Отчёты по продажам", owner_id), dispatcher
        )

        (webhook,) = await WebhookRepository(session).list_by_chat(CHAT_ID)
        assert webhook.name == "Отчёты по продажам"

    async def test_duplicate_name_is_rejected(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        webhook: tuple[Webhook, str],
        owner_id: str,
    ) -> None:
        await CreateWebhookHandler.handle(
            owner_message("/createwebhook мои уведомления", owner_id), dispatcher
        )

        assert "уже существует" in fake_bot.texts[-1]
        assert await table_count(session, Webhook) == 1

    async def test_without_name(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session_factory: object,
        owner_id: str,
    ) -> None:
        await CreateWebhookHandler.handle(
            owner_message("/createwebhook", owner_id), dispatcher
        )

        assert "укажите название" in fake_bot.texts[-1]

    async def test_requires_admin(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        chat: Chat,
    ) -> None:
        await CreateWebhookHandler.handle(
            make_event("new_message", text="/createwebhook Хук"), dispatcher
        )

        assert "нет доступа" in fake_bot.texts[-1]
        assert await table_count(session, Webhook) == 0

    async def test_falls_back_to_localhost_without_public_url(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        chat: Chat,
        owner_id: str,
        settings: VktSettings,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings, "public_url", None)

        await CreateWebhookHandler.handle(
            owner_message("/createwebhook Хук", owner_id), dispatcher
        )

        assert "http://localhost:8765/webhooks/" in fake_bot.texts[-1]


class TestListWebhooks:
    """``/listwebhooks``."""

    async def test_lists_webhooks(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        webhook: tuple[Webhook, str],
    ) -> None:
        await ListWebhooksHandler.handle(
            make_event("new_message", text="/listwebhooks"), dispatcher
        )

        text = fake_bot.texts[-1]
        assert "Мои уведомления" in text
        assert webhook[0].id in text
        assert "✅" in text

    async def test_inactive_webhook_is_marked(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        webhook: tuple[Webhook, str],
    ) -> None:
        webhook[0].is_active = False
        session.add(webhook[0])
        await session.commit()

        await ListWebhooksHandler.handle(
            make_event("new_message", text="/listwebhooks"), dispatcher
        )

        assert "❌" in fake_bot.texts[-1]

    async def test_empty_chat(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session_factory: object
    ) -> None:
        await ListWebhooksHandler.handle(
            make_event("new_message", text="/listwebhooks"), dispatcher
        )

        assert "нет вебхуков" in fake_bot.texts[-1]

    async def test_other_chat_webhooks_are_hidden(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        owner_id: str,
    ) -> None:
        other = await create_chat(session, "other@chat.agent")
        await create_chat_user(session, owner_id)
        await WebhookRepository(session).create_with_api_key(
            WebhookCreateSchema(name="Чужой", chat_id=other.id), owner_id
        )

        await ListWebhooksHandler.handle(
            make_event("new_message", text="/listwebhooks"), dispatcher
        )

        assert "нет вебхуков" in fake_bot.texts[-1]

    async def test_does_not_require_admin(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        webhook: tuple[Webhook, str],
    ) -> None:
        await ListWebhooksHandler.handle(
            make_event("new_message", text="/listwebhooks"), dispatcher
        )
        assert "нет доступа" not in fake_bot.texts[-1]


class TestWebhookInfo:
    """``/webhookinfo``."""

    async def test_shows_details(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        webhook: tuple[Webhook, str],
        settings: VktSettings,
    ) -> None:
        model, _ = webhook

        await WebhookInfoHandler.handle(
            make_event("new_message", text=f"/webhookinfo {model.id}"), dispatcher
        )

        text = fake_bot.texts[-1]
        assert "Мои уведомления" in text
        assert f"{settings.public_url}/webhooks/{model.id}" in text
        assert "Активен" in text

    async def test_api_key_is_not_shown(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        webhook: tuple[Webhook, str],
    ) -> None:
        model, api_key = webhook

        await WebhookInfoHandler.handle(
            make_event("new_message", text=f"/webhookinfo {model.id}"), dispatcher
        )

        assert api_key not in fake_bot.texts[-1]

    async def test_without_argument(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session_factory: object
    ) -> None:
        await WebhookInfoHandler.handle(
            make_event("new_message", text="/webhookinfo"), dispatcher
        )
        assert "укажите ID" in fake_bot.texts[-1]

    async def test_unknown_webhook(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session_factory: object
    ) -> None:
        await WebhookInfoHandler.handle(
            make_event("new_message", text="/webhookinfo nope"), dispatcher
        )
        assert "не найден" in fake_bot.texts[-1]

    async def test_webhook_from_another_chat(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        owner_id: str,
    ) -> None:
        other = await create_chat(session, "other@chat.agent")
        await create_chat_user(session, owner_id)
        model, _ = await WebhookRepository(session).create_with_api_key(
            WebhookCreateSchema(name="Чужой", chat_id=other.id), owner_id
        )

        await WebhookInfoHandler.handle(
            make_event("new_message", text=f"/webhookinfo {model.id}"), dispatcher
        )

        assert "не принадлежит текущему чату" in fake_bot.texts[-1]


class TestDeleteWebhook:
    """``/deletewebhook`` — запрос подтверждения."""

    async def test_asks_for_confirmation(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        webhook: tuple[Webhook, str],
        owner_id: str,
    ) -> None:
        model, _ = webhook

        await DeleteWebhookHandler.handle(
            owner_message(f"/deletewebhook {model.id}", owner_id), dispatcher
        )

        call = fake_bot.sent[-1]
        assert "Вы уверены" in call.text
        button = json.loads(call.kwargs["inline_keyboard_markup"])[0][0]
        data = WebhookCallbackData.model_validate_json(button["callbackData"])
        assert data.command == "deletewebhook"
        assert data.webhook_id == model.id
        assert await table_count(session, Webhook) == 1

    async def test_without_argument(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session_factory: object,
        owner_id: str,
    ) -> None:
        await DeleteWebhookHandler.handle(
            owner_message("/deletewebhook", owner_id), dispatcher
        )
        assert "укажите ID" in fake_bot.texts[-1]

    async def test_unknown_webhook(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session_factory: object,
        owner_id: str,
    ) -> None:
        await DeleteWebhookHandler.handle(
            owner_message("/deletewebhook nope", owner_id), dispatcher
        )
        assert "не найден" in fake_bot.texts[-1]

    async def test_requires_admin(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        webhook: tuple[Webhook, str],
    ) -> None:
        await DeleteWebhookHandler.handle(
            make_event("new_message", text=f"/deletewebhook {webhook[0].id}"),
            dispatcher,
        )
        assert "нет доступа" in fake_bot.texts[-1]


class TestRegenerateWebhookKey:
    """``/regeneratewebhookkey`` — запрос подтверждения."""

    async def test_asks_for_confirmation(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        webhook: tuple[Webhook, str],
        owner_id: str,
    ) -> None:
        model, _ = webhook

        await RegenerateWebhookKeyHandler.handle(
            owner_message(f"/regeneratewebhookkey {model.id}", owner_id), dispatcher
        )

        call = fake_bot.sent[-1]
        assert "перестанет работать" in call.text
        button = json.loads(call.kwargs["inline_keyboard_markup"])[0][0]
        data = WebhookCallbackData.model_validate_json(button["callbackData"])
        assert data.command == "regeneratewebhookkey"

    async def test_key_is_not_changed_yet(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        webhook: tuple[Webhook, str],
        owner_id: str,
    ) -> None:
        model, api_key = webhook

        await RegenerateWebhookKeyHandler.handle(
            owner_message(f"/regeneratewebhookkey {model.id}", owner_id), dispatcher
        )

        repo = WebhookRepository(session)
        assert await repo.get_by_id_and_api_key(model.id, api_key) is not None

    async def test_without_argument(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session_factory: object,
        owner_id: str,
    ) -> None:
        await RegenerateWebhookKeyHandler.handle(
            owner_message("/regeneratewebhookkey", owner_id), dispatcher
        )
        assert "укажите ID" in fake_bot.texts[-1]


class TestToggleWebhook:
    """``/togglewebhook``."""

    async def test_command_is_broken(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        webhook: tuple[Webhook, str],
        owner_id: str,
    ) -> None:
        """Известный дефект: команда падает на коммите.

        ``WebhookUpdateSchema(is_active=...)`` уходит в
        ``AsyncRepository.update`` целиком, поэтому в ``UPDATE`` попадают
        ``name=NULL`` и ``webhook_metadata=NULL``. Колонка ``name`` —
        ``NOT NULL``, так что вебхук нельзя ни включить, ни выключить.
        """
        import sqlalchemy as sa

        model, _ = webhook

        with pytest.raises(sa.exc.IntegrityError):
            await ToggleWebhookHandler.handle(
                owner_message(f"/togglewebhook {model.id}", owner_id), dispatcher
            )

    async def test_unknown_webhook(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session_factory: object,
        owner_id: str,
    ) -> None:
        await ToggleWebhookHandler.handle(
            owner_message("/togglewebhook nope", owner_id), dispatcher
        )
        assert "не найден" in fake_bot.texts[-1]

    async def test_requires_admin(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        webhook: tuple[Webhook, str],
    ) -> None:
        await ToggleWebhookHandler.handle(
            make_event("new_message", text=f"/togglewebhook {webhook[0].id}"),
            dispatcher,
        )
        assert "нет доступа" in fake_bot.texts[-1]


class TestWebhookConfirmation:
    """Кнопки подтверждения операций с вебхуками."""

    def callback_event(
        self, command: str, webhook_id: str, requested_by: str, sender: str
    ) -> Event:
        """Callback-событие подтверждения."""
        return make_event(
            "callback_query",
            **{
                "from": {"userId": sender},
                "callbackData": WebhookCallbackData(
                    command=command,  # type: ignore[arg-type]
                    webhook_id=webhook_id,
                    webhook_name="Мои уведомления",
                    requested_by=requested_by,
                ).model_dump_json(),
            },
        )

    async def test_deletes_webhook(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        webhook: tuple[Webhook, str],
    ) -> None:
        model, _ = webhook

        await WebhookConfirmationHandler.handle(
            self.callback_event("deletewebhook", model.id, "1234567890", "1234567890"),
            dispatcher,
        )

        assert await table_count(session, Webhook) == 0
        (answer,) = fake_bot.calls_of("answer_callback_query")
        assert "удален" in answer.kwargs["text"]
        assert fake_bot.calls_of("edit_text")

    async def test_regenerates_key(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        webhook: tuple[Webhook, str],
    ) -> None:
        import bcrypt

        model, old_key = webhook
        old_hash = model.api_key_hash

        await WebhookConfirmationHandler.handle(
            self.callback_event(
                "regeneratewebhookkey", model.id, "1234567890", "1234567890"
            ),
            dispatcher,
        )

        await session.refresh(model)
        assert model.api_key_hash != old_hash
        assert not bcrypt.checkpw(old_key.encode(), model.api_key_hash.encode())
        (edit,) = fake_bot.calls_of("edit_text")
        assert "Новый API ключ" in edit.kwargs["text"]

    async def test_only_requester_can_confirm(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        webhook: tuple[Webhook, str],
    ) -> None:
        model, _ = webhook

        await WebhookConfirmationHandler.handle(
            self.callback_event("deletewebhook", model.id, "1234567890", "9999999999"),
            dispatcher,
        )

        (answer,) = fake_bot.calls_of("answer_callback_query")
        assert answer.kwargs["show_alert"] is True
        assert await table_count(session, Webhook) == 1

    async def test_already_deleted_webhook(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session_factory: object
    ) -> None:
        await WebhookConfirmationHandler.handle(
            self.callback_event("deletewebhook", "nope", "1234567890", "1234567890"),
            dispatcher,
        )

        (answer,) = fake_bot.calls_of("answer_callback_query")
        assert "уже не существует" in answer.kwargs["text"]

    async def test_ignores_foreign_callback_data(
        self, dispatcher: Dispatcher, fake_bot: FakeBot
    ) -> None:
        event = make_event(
            "callback_query",
            callbackData=json.dumps(
                {"command": "start__showcommands", "requested_by": "1234567890"}
            ),
        )
        await WebhookConfirmationHandler.handle(event, dispatcher)
        assert fake_bot.calls == []
