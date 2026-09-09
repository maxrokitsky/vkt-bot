"""Методы отправки и правки сообщений."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from vkteams_client.types import Response

from tests.client.conftest import request_method, requests_to, single_query, url_for

if TYPE_CHECKING:
    from aioresponses import aioresponses
    from vkteams_client import VKTeams

SEND_TEXT = "/bot/v1/messages/sendText"
EDIT_TEXT = "/bot/v1/messages/editText"
ANSWER_CALLBACK = "/bot/v1/messages/answerCallbackQuery"
DELETE_MESSAGES = "/bot/v1/messages/deleteMessages"
GET_MEMBERS = "/bot/v1/chats/getMembers"
GET_SELF = "/bot/v1/self/get"


@pytest.fixture
def ok_send_text(mock_api: aioresponses) -> aioresponses:
    """Успешный ответ ``sendText``."""
    mock_api.get(
        url_for("/messages/sendText"), payload={"ok": True, "msgId": "1"}, repeat=True
    )
    return mock_api


class TestSendText:
    """``send_text``."""

    async def test_required_params(
        self, vkteams: VKTeams, ok_send_text: aioresponses
    ) -> None:
        await vkteams.send_text("681869378@chat.agent", "Привет!")

        params = single_query(ok_send_text, SEND_TEXT)
        assert params == {
            "token": vkteams.token,
            "chatId": "681869378@chat.agent",
            "text": "Привет!",
        }

    async def test_uses_get(self, vkteams: VKTeams, ok_send_text: aioresponses) -> None:
        await vkteams.send_text("chat", "text")
        assert request_method(ok_send_text, SEND_TEXT) == "GET"

    async def test_timeout_is_30_seconds(
        self, vkteams: VKTeams, ok_send_text: aioresponses
    ) -> None:
        await vkteams.send_text("chat", "text")
        (request,) = requests_to(ok_send_text, SEND_TEXT)
        assert request.kwargs["timeout"].total == 30

    async def test_reply_msg_id(
        self, vkteams: VKTeams, ok_send_text: aioresponses
    ) -> None:
        await vkteams.send_text("chat", "text", reply_msg_id=[123, 456])

        from tests.client.conftest import query_of

        assert query_of(ok_send_text, SEND_TEXT)["replyMsgId"] == ["123", "456"]

    async def test_parse_mode(
        self, vkteams: VKTeams, ok_send_text: aioresponses
    ) -> None:
        await vkteams.send_text("chat", "text", parse_mode="MarkdownV2")
        assert single_query(ok_send_text, SEND_TEXT)["parseMode"] == "MarkdownV2"

    async def test_inline_keyboard_is_passed_through_as_is(
        self, vkteams: VKTeams, ok_send_text: aioresponses
    ) -> None:
        """Клавиатура не сериализуется клиентом — см. ROADMAP 3.4."""
        keyboard = '[[{"text": "Кнопка", "url": "https://example.com"}]]'
        await vkteams.send_text("chat", "text", inline_keyboard_markup=keyboard)
        assert single_query(ok_send_text, SEND_TEXT)["inlineKeyboardMarkup"] == keyboard

    async def test_forward_requires_both_params(
        self, vkteams: VKTeams, ok_send_text: aioresponses
    ) -> None:
        await vkteams.send_text("chat", "text", forward_chat_id="from@chat.agent")
        params = single_query(ok_send_text, SEND_TEXT)
        assert "forwardChatId" not in params
        assert "forwardMsgId" not in params

    async def test_forward_msg_id_alone_is_ignored(
        self, vkteams: VKTeams, ok_send_text: aioresponses
    ) -> None:
        await vkteams.send_text("chat", "text", forward_msg_id="123")
        params = single_query(ok_send_text, SEND_TEXT)
        assert "forwardMsgId" not in params

    async def test_forward_pair_is_sent(
        self, vkteams: VKTeams, ok_send_text: aioresponses
    ) -> None:
        await vkteams.send_text(
            "chat", "text", forward_chat_id="from@chat.agent", forward_msg_id="123"
        )
        params = single_query(ok_send_text, SEND_TEXT)
        assert params["forwardChatId"] == "from@chat.agent"
        assert params["forwardMsgId"] == "123"

    async def test_empty_optional_values_are_skipped(
        self, vkteams: VKTeams, ok_send_text: aioresponses
    ) -> None:
        await vkteams.send_text(
            "chat",
            "text",
            reply_msg_id=[],
            parse_mode=None,
            inline_keyboard_markup=None,
        )
        assert set(single_query(ok_send_text, SEND_TEXT)) == {
            "token",
            "chatId",
            "text",
        }

    async def test_returns_none(
        self, vkteams: VKTeams, ok_send_text: aioresponses
    ) -> None:
        """``msgId`` из ответа теряется — см. ROADMAP 3.3."""
        assert await vkteams.send_text("chat", "text") is None

    async def test_error_response_does_not_raise(
        self, vkteams: VKTeams, mock_api: aioresponses
    ) -> None:
        """Клиент не проверяет ``ok`` — ошибка отправки проходит незамеченной."""
        mock_api.get(
            url_for("/messages/sendText"),
            payload={"ok": False, "description": "Chat not found"},
        )
        assert await vkteams.send_text("chat", "text") is None

    async def test_logs_truncated_text(
        self,
        vkteams: VKTeams,
        ok_send_text: aioresponses,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level("INFO", logger="vkteams_client.send_message"):
            await vkteams.send_text("chat", "x" * 100)
        (record,) = [
            r for r in caplog.records if r.name == "vkteams_client.send_message"
        ]
        assert "x" * 50 in record.getMessage()
        assert "x" * 51 not in record.getMessage()


class TestEditText:
    """``edit_text``."""

    @pytest.fixture
    def ok_edit(self, mock_api: aioresponses) -> aioresponses:
        mock_api.get(url_for("/messages/editText"), payload={"ok": True}, repeat=True)
        return mock_api

    async def test_required_params(
        self, vkteams: VKTeams, ok_edit: aioresponses
    ) -> None:
        await vkteams.edit_text("chat", "msg-1", "новый текст")
        assert single_query(ok_edit, EDIT_TEXT) == {
            "token": vkteams.token,
            "chatId": "chat",
            "msgId": "msg-1",
            "text": "новый текст",
        }

    async def test_parse_mode_and_keyboard(
        self, vkteams: VKTeams, ok_edit: aioresponses
    ) -> None:
        await vkteams.edit_text(
            "chat",
            "msg-1",
            "текст",
            parse_mode="HTML",
            inline_keyboard_markup="[[]]",
        )
        params = single_query(ok_edit, EDIT_TEXT)
        assert params["parseMode"] == "HTML"
        assert params["inlineKeyboardMarkup"] == "[[]]"

    async def test_timeout_is_30_seconds(
        self, vkteams: VKTeams, ok_edit: aioresponses
    ) -> None:
        await vkteams.edit_text("chat", "msg-1", "текст")
        (request,) = requests_to(ok_edit, EDIT_TEXT)
        assert request.kwargs["timeout"].total == 30

    async def test_returns_none(self, vkteams: VKTeams, ok_edit: aioresponses) -> None:
        """``msgId`` не возвращается — см. ROADMAP 3.3."""
        assert await vkteams.edit_text("chat", "msg-1", "текст") is None


class TestAnswerCallbackQuery:
    """``answer_callback_query``."""

    @pytest.fixture
    def ok_answer(self, mock_api: aioresponses) -> aioresponses:
        mock_api.get(
            url_for("/messages/answerCallbackQuery"),
            payload={"ok": True},
            repeat=True,
        )
        return mock_api

    async def test_only_query_id_by_default(
        self, vkteams: VKTeams, ok_answer: aioresponses
    ) -> None:
        await vkteams.answer_callback_query("SVR:1")
        assert single_query(ok_answer, ANSWER_CALLBACK) == {
            "token": vkteams.token,
            "queryId": "SVR:1",
        }

    async def test_show_alert_becomes_string_true(
        self, vkteams: VKTeams, ok_answer: aioresponses
    ) -> None:
        await vkteams.answer_callback_query("SVR:1", text="Нельзя", show_alert=True)
        params = single_query(ok_answer, ANSWER_CALLBACK)
        assert params["showAlert"] == "true"
        assert params["text"] == "Нельзя"

    async def test_show_alert_false_is_omitted(
        self, vkteams: VKTeams, ok_answer: aioresponses
    ) -> None:
        await vkteams.answer_callback_query("SVR:1", show_alert=False)
        assert "showAlert" not in single_query(ok_answer, ANSWER_CALLBACK)

    async def test_empty_text_is_sent(
        self, vkteams: VKTeams, ok_answer: aioresponses
    ) -> None:
        """Пустая строка — не то же самое, что ``None``."""
        await vkteams.answer_callback_query("SVR:1", text="")
        assert single_query(ok_answer, ANSWER_CALLBACK)["text"] == ""

    async def test_url(self, vkteams: VKTeams, ok_answer: aioresponses) -> None:
        await vkteams.answer_callback_query("SVR:1", url="https://example.com")
        assert single_query(ok_answer, ANSWER_CALLBACK)["url"] == "https://example.com"


class TestDeleteMessages:
    """``delete_messages``."""

    async def test_params_and_result(
        self, vkteams: VKTeams, mock_api: aioresponses
    ) -> None:
        mock_api.get(url_for("/messages/deleteMessages"), payload={"ok": True})
        result = await vkteams.delete_messages("chat", "msg-1")

        assert isinstance(result, Response)
        assert result.ok is True
        assert single_query(mock_api, DELETE_MESSAGES) == {
            "token": vkteams.token,
            "chatId": "chat",
            "msgId": "msg-1",
        }

    async def test_not_ok_is_returned_as_is(
        self, vkteams: VKTeams, mock_api: aioresponses
    ) -> None:
        mock_api.get(
            url_for("/messages/deleteMessages"),
            payload={"ok": False, "description": "Message not found"},
        )
        result = await vkteams.delete_messages("chat", "msg-1")
        assert result.ok is False

    async def test_invalid_json_raises(
        self, vkteams: VKTeams, mock_api: aioresponses
    ) -> None:
        from pydantic import ValidationError

        mock_api.get(url_for("/messages/deleteMessages"), body="<html>oops</html>")
        with pytest.raises(ValidationError):
            await vkteams.delete_messages("chat", "msg-1")


class TestGetMembers:
    """``get_members``."""

    async def test_parses_members(
        self, vkteams: VKTeams, mock_api: aioresponses
    ) -> None:
        mock_api.get(
            url_for("/chats/getMembers"),
            payload={
                "ok": True,
                "members": [
                    {"userId": "1234567890", "creator": True, "admin": True},
                    {"userId": "9876543210"},
                ],
            },
        )
        result = await vkteams.get_members("681869378@chat.agent")

        assert [m.userId for m in result.members] == ["1234567890", "9876543210"]
        assert result.members[0].creator is True
        assert result.members[1].creator is False
        assert result.members[1].admin is False

    async def test_params(self, vkteams: VKTeams, mock_api: aioresponses) -> None:
        mock_api.get(url_for("/chats/getMembers"), payload={"ok": True, "members": []})
        await vkteams.get_members("chat")
        assert single_query(mock_api, GET_MEMBERS) == {
            "token": vkteams.token,
            "chatId": "chat",
        }

    async def test_cursor_is_ignored(
        self, vkteams: VKTeams, mock_api: aioresponses
    ) -> None:
        """``cursor`` из ответа не читается — см. ROADMAP 3.6."""
        mock_api.get(
            url_for("/chats/getMembers"),
            payload={"ok": True, "members": [], "cursor": "next-page"},
        )
        result = await vkteams.get_members("chat")
        assert not hasattr(result, "cursor")


class TestGetSelf:
    """``get_self``."""

    async def test_parses_response(
        self, vkteams: VKTeams, mock_api: aioresponses
    ) -> None:
        mock_api.get(
            url_for("/self/get"),
            payload={
                "ok": True,
                "firstName": "Ассистент",
                "nick": "assistant_bot",
                "userId": "123456789:bot",
            },
        )
        info = await vkteams.get_self()

        assert info.nick == "assistant_bot"
        assert info.firstName == "Ассистент"
        assert info.userId == "123456789:bot"

    async def test_token_is_the_only_param(
        self, vkteams: VKTeams, mock_api: aioresponses
    ) -> None:
        mock_api.get(
            url_for("/self/get"),
            payload={
                "ok": True,
                "firstName": "b",
                "nick": "n",
                "userId": "u",
            },
        )
        await vkteams.get_self()
        assert single_query(mock_api, GET_SELF) == {"token": vkteams.token}

    async def test_missing_fields_raise(
        self, vkteams: VKTeams, mock_api: aioresponses
    ) -> None:
        from pydantic import ValidationError

        mock_api.get(url_for("/self/get"), payload={"ok": False})
        with pytest.raises(ValidationError):
            await vkteams.get_self()


class TestSession:
    """Жизненный цикл ``aiohttp.ClientSession``."""

    async def test_session_is_created_lazily(self) -> None:
        from vkteams_client import VKTeams

        client = VKTeams("token")
        assert client._session is None
        try:
            assert client.session is client.session
        finally:
            await client.close()

    async def test_close_without_session_is_safe(self) -> None:
        from vkteams_client import VKTeams

        await VKTeams("token").close()

    async def test_close_closes_session(self) -> None:
        from vkteams_client import VKTeams

        client = VKTeams("token")
        session = client.session
        await client.close()
        assert session.closed
