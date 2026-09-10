"""Отправка файлов: ``send_file`` и ``send_file_from_url``."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest
from vkteams_client.types import MsgLoadFileResponse, MsgResponse

from tests.client.conftest import (
    query_of,
    request_method,
    requests_to,
    single_query,
    url_for,
)

if TYPE_CHECKING:
    from aioresponses import aioresponses
    from vkteams_client import VKTeams

SEND_FILE = "/bot/v1/messages/sendFile"


def form_fields(mocked: aioresponses) -> dict[str, Any]:
    """Поля multipart-формы отправленного запроса."""
    (request,) = requests_to(mocked, SEND_FILE)
    data = request.kwargs["data"]
    return {field[0]["name"]: field[2] for field in data._fields}


def form_field_options(mocked: aioresponses, name: str) -> dict[str, str]:
    """Опции Content-Disposition конкретного поля формы."""
    (request,) = requests_to(mocked, SEND_FILE)
    for options, _headers, _value in request.kwargs["data"]._fields:
        if options["name"] == name:
            return options
    msg = f"В форме нет поля {name!r}"
    raise AssertionError(msg)


class TestSendFileById:
    """Отправка уже загруженного файла (GET по ``fileId``)."""

    @pytest.fixture
    def ok_get(self, mock_api: aioresponses) -> aioresponses:
        mock_api.get(
            url_for("/messages/sendFile"),
            payload={"ok": True, "msgId": "msg-1"},
            repeat=True,
        )
        return mock_api

    async def test_uses_get_with_file_id(
        self, vkteams: VKTeams, ok_get: aioresponses
    ) -> None:
        result = await vkteams.send_file("chat", file_id="file-abc")

        assert request_method(ok_get, SEND_FILE) == "GET"
        assert isinstance(result, MsgResponse)
        assert result.msgId == "msg-1"
        params = single_query(ok_get, SEND_FILE)
        assert params["fileId"] == "file-abc"
        assert params["chatId"] == "chat"

    async def test_optional_params(
        self, vkteams: VKTeams, ok_get: aioresponses
    ) -> None:
        await vkteams.send_file(
            "chat",
            file_id="file-abc",
            caption="Подпись",
            parse_mode="MarkdownV2",
            reply_msg_id=[1, 2],
        )
        params = query_of(ok_get, SEND_FILE)
        assert params["caption"] == ["Подпись"]
        assert params["parseMode"] == ["MarkdownV2"]
        assert params["replyMsgId"] == ["1", "2"]

    async def test_keyboard_and_format_are_json_encoded(
        self, vkteams: VKTeams, ok_get: aioresponses
    ) -> None:
        keyboard = [[{"text": "Кнопка", "url": "https://example.com"}]]
        text_format = {"bold": [{"offset": 0, "length": 4}]}
        await vkteams.send_file(
            "chat",
            file_id="file-abc",
            inline_keyboard_markup=keyboard,
            format=text_format,
        )
        params = single_query(ok_get, SEND_FILE)
        assert json.loads(params["inlineKeyboardMarkup"]) == keyboard
        assert json.loads(params["format"]) == text_format

    async def test_forward_requires_pair(
        self, vkteams: VKTeams, ok_get: aioresponses
    ) -> None:
        await vkteams.send_file("chat", file_id="f", forward_chat_id="other")
        assert "forwardChatId" not in single_query(ok_get, SEND_FILE)

    async def test_forward_pair(self, vkteams: VKTeams, ok_get: aioresponses) -> None:
        await vkteams.send_file(
            "chat", file_id="f", forward_chat_id="other", forward_msg_id=[7]
        )
        params = query_of(ok_get, SEND_FILE)
        assert params["forwardChatId"] == ["other"]
        assert params["forwardMsgId"] == ["7"]

    async def test_timeout_is_30_seconds(
        self, vkteams: VKTeams, ok_get: aioresponses
    ) -> None:
        await vkteams.send_file("chat", file_id="f")
        (request,) = requests_to(ok_get, SEND_FILE)
        assert request.kwargs["timeout"].total == 30

    async def test_failed_response_has_no_msg_id(
        self, vkteams: VKTeams, mock_api: aioresponses
    ) -> None:
        """При ``ok: false`` идентификатора нет, но разбор не падает."""
        mock_api.get(
            url_for("/messages/sendFile"),
            payload={"ok": False, "description": "File not found"},
        )

        result = await vkteams.send_file("chat", file_id="f")

        assert result.ok is False
        assert result.msgId is None
        assert result.description == "File not found"


class TestSendFileUpload:
    """Загрузка нового файла (POST multipart/form-data)."""

    @pytest.fixture
    def ok_post(self, mock_api: aioresponses) -> aioresponses:
        mock_api.post(
            url_for("/messages/sendFile"),
            payload={"ok": True, "msgId": "msg-2", "fileId": "file-new"},
            repeat=True,
        )
        return mock_api

    async def test_uses_post_and_returns_file_id(
        self, vkteams: VKTeams, ok_post: aioresponses
    ) -> None:
        result = await vkteams.send_file(
            "chat", file=b"content", filename="doc.pdf", caption="Документ"
        )

        assert request_method(ok_post, SEND_FILE) == "POST"
        assert isinstance(result, MsgLoadFileResponse)
        assert (result.fileId, result.msgId) == ("file-new", "msg-2")

    async def test_params_move_into_form(
        self, vkteams: VKTeams, ok_post: aioresponses
    ) -> None:
        await vkteams.send_file(
            "chat", file=b"content", filename="doc.pdf", caption="Документ"
        )
        fields = form_fields(ok_post)
        assert fields["chatId"] == "chat"
        assert fields["caption"] == "Документ"
        assert fields["token"] == vkteams.token
        assert fields["file"] == b"content"

    async def test_no_query_params(
        self, vkteams: VKTeams, ok_post: aioresponses
    ) -> None:
        await vkteams.send_file("chat", file=b"content", filename="doc.pdf")
        assert single_query(ok_post, SEND_FILE) == {}

    async def test_list_params_become_json(
        self, vkteams: VKTeams, ok_post: aioresponses
    ) -> None:
        await vkteams.send_file("chat", file=b"c", filename="f", reply_msg_id=[10, 11])
        assert json.loads(form_fields(ok_post)["replyMsgId"]) == [10, 11]

    async def test_keyboard_and_format_are_json_fields(
        self, vkteams: VKTeams, ok_post: aioresponses
    ) -> None:
        keyboard = [[{"text": "Кнопка", "callbackData": "cb"}]]
        await vkteams.send_file(
            "chat",
            file=b"c",
            filename="f",
            inline_keyboard_markup=keyboard,
            format={"bold": [{"offset": 0, "length": 1}]},
        )
        fields = form_fields(ok_post)
        assert json.loads(fields["inlineKeyboardMarkup"]) == keyboard
        assert json.loads(fields["format"])["bold"][0]["length"] == 1

    async def test_filename_defaults_to_file(
        self, vkteams: VKTeams, ok_post: aioresponses
    ) -> None:
        await vkteams.send_file("chat", file=b"c")
        assert form_field_options(ok_post, "file")["filename"] == "file"

    async def test_filename_is_not_quoted(
        self, vkteams: VKTeams, ok_post: aioresponses
    ) -> None:
        """``quote_fields=False``: имя файла уходит как есть."""
        await vkteams.send_file("chat", file=b"c", filename="отчёт за май.pdf")
        assert form_field_options(ok_post, "file")["filename"] == "отчёт за май.pdf"

    async def test_upload_timeout_is_60_seconds(
        self, vkteams: VKTeams, ok_post: aioresponses
    ) -> None:
        await vkteams.send_file("chat", file=b"c", filename="f")
        (request,) = requests_to(ok_post, SEND_FILE)
        assert request.kwargs["timeout"].total == 60

    async def test_file_id_wins_over_file(
        self, vkteams: VKTeams, mock_api: aioresponses
    ) -> None:
        """Если передано и то и другое, используется ветка ``file_id`` (GET)."""
        mock_api.get(
            url_for("/messages/sendFile"), payload={"ok": True, "msgId": "msg-1"}
        )
        result = await vkteams.send_file("chat", file_id="f", file=b"c")
        assert isinstance(result, MsgResponse)
        assert request_method(mock_api, SEND_FILE) == "GET"


class TestSendFileValidation:
    """Проверка аргументов."""

    async def test_without_file_and_file_id_raises(self, vkteams: VKTeams) -> None:
        with pytest.raises(ValueError, match="file_id"):
            await vkteams.send_file("chat")

    async def test_empty_bytes_are_treated_as_missing(self, vkteams: VKTeams) -> None:
        """Пустой файл не проходит проверку ``elif file:``."""
        with pytest.raises(ValueError, match="file_id"):
            await vkteams.send_file("chat", file=b"")


class TestSendFileFromUrl:
    """``send_file_from_url``."""

    @pytest.fixture
    def ok_post(self, mock_api: aioresponses) -> aioresponses:
        mock_api.post(
            url_for("/messages/sendFile"),
            payload={"ok": True, "msgId": "msg-3", "fileId": "file-url"},
            repeat=True,
        )
        return mock_api

    async def test_downloads_and_uploads(
        self, vkteams: VKTeams, ok_post: aioresponses
    ) -> None:
        ok_post.get("https://example.com/doc.pdf", body=b"pdf-bytes")
        result = await vkteams.send_file_from_url("chat", "https://example.com/doc.pdf")

        assert result.fileId == "file-url"
        assert form_fields(ok_post)["file"] == b"pdf-bytes"

    async def test_filename_from_content_disposition(
        self, vkteams: VKTeams, ok_post: aioresponses
    ) -> None:
        ok_post.get(
            "https://example.com/download?id=7",
            body=b"data",
            headers={"Content-Disposition": 'attachment; filename="report.xlsx"'},
        )
        await vkteams.send_file_from_url("chat", "https://example.com/download?id=7")
        assert form_field_options(ok_post, "file")["filename"] == "report.xlsx"

    async def test_filename_from_url_tail(
        self, vkteams: VKTeams, ok_post: aioresponses
    ) -> None:
        ok_post.get("https://example.com/files/doc.pdf?v=2", body=b"data")
        await vkteams.send_file_from_url(
            "chat", "https://example.com/files/doc.pdf?v=2"
        )
        assert form_field_options(ok_post, "file")["filename"] == "doc.pdf"

    async def test_filename_falls_back_to_file(
        self, vkteams: VKTeams, ok_post: aioresponses
    ) -> None:
        ok_post.get("https://example.com/", body=b"data")
        await vkteams.send_file_from_url("chat", "https://example.com/")
        assert form_field_options(ok_post, "file")["filename"] == "file"

    async def test_explicit_filename_wins(
        self, vkteams: VKTeams, ok_post: aioresponses
    ) -> None:
        ok_post.get(
            "https://example.com/doc.pdf",
            body=b"data",
            headers={"Content-Disposition": 'attachment; filename="ignored.pdf"'},
        )
        await vkteams.send_file_from_url(
            "chat", "https://example.com/doc.pdf", filename="my.pdf"
        )
        assert form_field_options(ok_post, "file")["filename"] == "my.pdf"

    async def test_download_error_raises(
        self, vkteams: VKTeams, mock_api: aioresponses
    ) -> None:
        mock_api.get("https://example.com/missing.pdf", status=404, body=b"")
        with pytest.raises(ValueError, match="Не удалось скачать файл"):
            await vkteams.send_file_from_url("chat", "https://example.com/missing.pdf")

    async def test_options_are_forwarded(
        self, vkteams: VKTeams, ok_post: aioresponses
    ) -> None:
        ok_post.get("https://example.com/doc.pdf", body=b"data")
        await vkteams.send_file_from_url(
            "chat",
            "https://example.com/doc.pdf",
            caption="Подпись",
            parse_mode="HTML",
        )
        fields = form_fields(ok_post)
        assert fields["caption"] == "Подпись"
        assert fields["parseMode"] == "HTML"
