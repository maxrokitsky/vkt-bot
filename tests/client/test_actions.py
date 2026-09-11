"""``chats/sendActions`` — индикатор «печатает…» в чате."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from vkteams_client.enums import ChatAction

from tests.client.conftest import query_of, request_method, requests_to, url_for

if TYPE_CHECKING:
    from aioresponses import aioresponses
    from vkteams_client import VKTeams

SEND_ACTIONS = "/bot/v1/chats/sendActions"
CHAT = "681869378@chat.agent"


@pytest.fixture
def ok_actions(mock_api: aioresponses) -> aioresponses:
    """Успешный ответ ``sendActions``."""
    mock_api.get(url_for("/chats/sendActions"), payload={"ok": True}, repeat=True)
    return mock_api


class TestSendActions:
    """``send_actions``."""

    async def test_is_a_get(self, vkteams: VKTeams, ok_actions: aioresponses) -> None:
        await vkteams.send_actions(CHAT, ChatAction.TYPING)

        assert request_method(ok_actions, SEND_ACTIONS) == "GET"

    async def test_single_action(
        self, vkteams: VKTeams, ok_actions: aioresponses
    ) -> None:
        await vkteams.send_actions(CHAT, ChatAction.TYPING)

        query = query_of(ok_actions, SEND_ACTIONS)
        assert query["chatId"] == [CHAT]
        assert query["actions"] == ["typing"]

    async def test_several_actions_repeat_the_parameter(
        self, vkteams: VKTeams, ok_actions: aioresponses
    ) -> None:
        """Массив в query у OpenAPI 3 по умолчанию повторяется по значению.

        Проверено на живом API: `actions=looking&actions=typing` принимается.
        """
        await vkteams.send_actions(CHAT, ChatAction.LOOKING, ChatAction.TYPING)

        assert query_of(ok_actions, SEND_ACTIONS)["actions"] == ["looking", "typing"]

    async def test_empty_means_finished(
        self, vkteams: VKTeams, ok_actions: aioresponses
    ) -> None:
        """Пустое значение — «все действия завершены», так просит спека."""
        await vkteams.send_actions(CHAT)

        assert query_of(ok_actions, SEND_ACTIONS)["actions"] == [""]

    async def test_token_is_sent(
        self, vkteams: VKTeams, ok_actions: aioresponses
    ) -> None:
        assert (await vkteams.send_actions(CHAT)).ok is True
        assert "token" in query_of(ok_actions, SEND_ACTIONS)

    async def test_refusal_is_returned_not_raised(
        self, vkteams: VKTeams, mock_api: aioresponses, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Индикатор — украшение: отказ не должен ломать отправку ответа."""
        mock_api.get(
            url_for("/chats/sendActions"),
            payload={"ok": False, "description": "Bad request"},
        )

        with caplog.at_level("WARNING", logger="vkteams_client"):
            result = await vkteams.send_actions(CHAT, "bogus")

        assert result.ok is False
        assert result.description == "Bad request"
        assert "chat.actions_refused" in caplog.text

    async def test_one_request_per_call(
        self, vkteams: VKTeams, ok_actions: aioresponses
    ) -> None:
        await vkteams.send_actions(CHAT, ChatAction.TYPING)
        await vkteams.send_actions(CHAT)

        assert len(requests_to(ok_actions, SEND_ACTIONS)) == 2
