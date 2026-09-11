"""Метод ``chats/getInfo``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vkteams_client.enums import ChatType
from vkteams_client.types import (
    ChannelChatInfo,
    GroupChatInfo,
    PrivateChatInfo,
    UnknownChatInfo,
)

from tests.client.conftest import (
    request_method,
    requests_to,
    single_query,
    url_for,
)

if TYPE_CHECKING:
    from aioresponses import aioresponses
    from vkteams_client import VKTeams

GET_INFO = "/bot/v1/chats/getInfo"

USER_ID = "1234567890"
CHAT_ID = "681869378@chat.agent"
AVATAR = "https://rapi.icq.net/avatar/get?targetSn=1234567890&size=1024"


class TestGetChatInfo:
    """``get_chat_info``."""

    async def test_parses_private(
        self, vkteams: VKTeams, mock_api: aioresponses
    ) -> None:
        """Личный чат: имя, ник, описание и аватар."""
        mock_api.get(
            url_for("/chats/getInfo"),
            payload={
                "type": "private",
                "firstName": "Иван",
                "lastName": "Иванов",
                "nick": "ivan",
                "about": "Архитектор",
                "language": "ru",
                "photo": [{"url": AVATAR}],
                "ok": True,
            },
        )

        result = await vkteams.get_chat_info(chat_id=USER_ID)

        # Проверяем именно класс: при поломке дискриминатора разбор молча
        # уходит в ``UnknownChatInfo``, и ``ok`` при этом остаётся True.
        assert isinstance(result, PrivateChatInfo)
        assert result.type is ChatType.PRIVATE
        assert result.firstName == "Иван"
        assert result.lastName == "Иванов"
        assert result.nick == "ivan"
        assert result.about == "Архитектор"
        assert result.language == "ru"
        assert result.photo_url == AVATAR
        # У человека поля нет вовсе — «не бот» и «не знаем» это разное.
        assert result.isBot is None

    async def test_parses_bot(self, vkteams: VKTeams, mock_api: aioresponses) -> None:
        """У бота в том же ответе стоит ``isBot``."""
        mock_api.get(
            url_for("/chats/getInfo"),
            payload={
                "type": "private",
                "firstName": "max_test_bot",
                "nick": "max_test_bot",
                "isBot": True,
                "ok": True,
            },
        )

        result = await vkteams.get_chat_info(chat_id="1011835311")

        assert isinstance(result, PrivateChatInfo)
        assert result.isBot is True

    async def test_parses_group(self, vkteams: VKTeams, mock_api: aioresponses) -> None:
        """Группа: название, правила, ссылка-приглашение и флаги."""
        mock_api.get(
            url_for("/chats/getInfo"),
            payload={
                "type": "group",
                "title": "Тест группа",
                "about": "Описание",
                "rules": "Правила",
                "inviteLink": "https://icq.com/chat/AoLLi9QjQqY9G2FMXzA",
                "public": False,
                "joinModeration": False,
                "ok": True,
            },
        )

        result = await vkteams.get_chat_info(chat_id=CHAT_ID)

        assert isinstance(result, GroupChatInfo)
        assert result.title == "Тест группа"
        assert result.rules == "Правила"
        assert result.inviteLink == "https://icq.com/chat/AoLLi9QjQqY9G2FMXzA"
        # Именно ``is False``: на ``or``-логике ложь неотличима от «не знаем».
        assert result.public is False
        assert result.joinModeration is False

    async def test_group_without_photo(
        self, vkteams: VKTeams, mock_api: aioresponses
    ) -> None:
        """У группы без аватара поля ``photo`` нет вовсе."""
        mock_api.get(
            url_for("/chats/getInfo"),
            payload={"type": "group", "title": "Тест группа", "ok": True},
        )

        result = await vkteams.get_chat_info(chat_id=CHAT_ID)

        assert result.photo == []
        assert result.photo_url is None

    async def test_parses_channel(
        self, vkteams: VKTeams, mock_api: aioresponses
    ) -> None:
        """Канал: тот же набор полей, что у группы."""
        mock_api.get(
            url_for("/chats/getInfo"),
            payload={"type": "channel", "title": "Канал", "public": True, "ok": True},
        )

        result = await vkteams.get_chat_info(chat_id=CHAT_ID)

        assert isinstance(result, ChannelChatInfo)
        assert result.public is True

    async def test_refusal_is_not_an_exception(
        self, vkteams: VKTeams, mock_api: aioresponses
    ) -> None:
        """Так метод отвечает в обсуждении: полей нет, включая ``type``."""
        mock_api.get(
            url_for("/chats/getInfo"),
            payload={"ok": False, "description": "Bad request"},
        )

        result = await vkteams.get_chat_info(chat_id="693938330@chat.agent")

        assert isinstance(result, UnknownChatInfo)
        assert result.ok is False
        assert result.type is None
        assert result.description == "Bad request"

    async def test_invalid_chat_id(
        self, vkteams: VKTeams, mock_api: aioresponses
    ) -> None:
        """Неизвестный или пустой ``chatId``."""
        mock_api.get(
            url_for("/chats/getInfo"),
            payload={"ok": False, "description": "Invalid chatId"},
        )

        result = await vkteams.get_chat_info(chat_id="no.such.user@example.com")

        assert result.ok is False
        assert result.description == "Invalid chatId"

    async def test_unknown_type_does_not_break(
        self, vkteams: VKTeams, mock_api: aioresponses
    ) -> None:
        """Новый вид чата не должен ронять разбор."""
        mock_api.get(
            url_for("/chats/getInfo"),
            payload={"ok": True, "type": "supergroup", "title": "x"},
        )

        result = await vkteams.get_chat_info(chat_id=CHAT_ID)

        assert isinstance(result, UnknownChatInfo)
        assert result.type == "supergroup"

    async def test_broken_field_falls_back(
        self, vkteams: VKTeams, mock_api: aioresponses
    ) -> None:
        """Неожидаемый тип у знакомого поля — тоже не исключение."""
        mock_api.get(
            url_for("/chats/getInfo"),
            payload={"ok": True, "type": "group", "public": {"nested": 1}},
        )

        result = await vkteams.get_chat_info(chat_id=CHAT_ID)

        assert isinstance(result, UnknownChatInfo)
        assert result.type == "group"

    async def test_params(self, vkteams: VKTeams, mock_api: aioresponses) -> None:
        """Параметры запроса."""
        mock_api.get(url_for("/chats/getInfo"), payload={"ok": True, "type": "group"})

        await vkteams.get_chat_info(chat_id=CHAT_ID)

        assert single_query(mock_api, GET_INFO) == {
            "token": vkteams.token,
            "chatId": CHAT_ID,
        }

    async def test_uses_get(self, vkteams: VKTeams, mock_api: aioresponses) -> None:
        """Метод читающий — запрос идёт GET."""
        mock_api.get(url_for("/chats/getInfo"), payload={"ok": True, "type": "group"})

        await vkteams.get_chat_info(chat_id=CHAT_ID)

        assert request_method(mock_api, GET_INFO) == "GET"

    async def test_timeout(self, vkteams: VKTeams, mock_api: aioresponses) -> None:
        """Запрос идёт с таймаутом, как остальные новые методы."""
        mock_api.get(url_for("/chats/getInfo"), payload={"ok": True, "type": "group"})

        await vkteams.get_chat_info(chat_id=CHAT_ID)

        (request,) = requests_to(mock_api, GET_INFO)
        assert request.kwargs["timeout"].total == 30
