"""Методы обсуждений (тредов)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.client.conftest import query_of, request_method, single_query, url_for

if TYPE_CHECKING:
    from aioresponses import aioresponses
    from vkteams_client import VKTeams

THREADS_ADD = "/bot/v1/threads/add"
AUTOSUBSCRIBE = "/bot/v1/threads/autosubscribe"
SUBSCRIBERS_GET = "/bot/v1/threads/subscribers/get"

THREAD_ID = "2601@chat.agent"
CHAT_ID = "681869378@chat.agent"


class TestThreadsAdd:
    """``threads_add``."""

    @pytest.fixture
    def ok_add(self, mock_api: aioresponses) -> aioresponses:
        mock_api.get(
            url_for("/threads/add"),
            payload={"ok": True, "threadId": THREAD_ID},
            repeat=True,
        )
        return mock_api

    async def test_params(self, vkteams: VKTeams, ok_add: aioresponses) -> None:
        await vkteams.threads_add(chat_id=CHAT_ID, msg_id="6752739791872001111")

        assert single_query(ok_add, THREADS_ADD) == {
            "token": vkteams.token,
            "chatId": CHAT_ID,
            "msgId": "6752739791872001111",
        }

    async def test_uses_get(self, vkteams: VKTeams, ok_add: aioresponses) -> None:
        await vkteams.threads_add(chat_id=CHAT_ID, msg_id="1")
        assert request_method(ok_add, THREADS_ADD) == "GET"

    async def test_returns_thread_id(
        self,
        vkteams: VKTeams,
        ok_add: aioresponses,  # noqa: ARG002
    ) -> None:
        result = await vkteams.threads_add(chat_id=CHAT_ID, msg_id="1")

        assert result.ok is True
        assert result.threadId == THREAD_ID


class TestThreadsAutosubscribe:
    """``threads_autosubscribe``."""

    @pytest.fixture
    def ok_autosubscribe(self, mock_api: aioresponses) -> aioresponses:
        mock_api.get(
            url_for("/threads/autosubscribe"), payload={"ok": True}, repeat=True
        )
        return mock_api

    async def test_enable_with_existing(
        self, vkteams: VKTeams, ok_autosubscribe: aioresponses
    ) -> None:
        await vkteams.threads_autosubscribe(
            chat_id=CHAT_ID, enable=True, with_existing=True
        )

        assert single_query(ok_autosubscribe, AUTOSUBSCRIBE) == {
            "token": vkteams.token,
            "chatId": CHAT_ID,
            "enable": "true",
            "withExisting": "true",
        }

    async def test_booleans_are_lowercase_strings(
        self, vkteams: VKTeams, ok_autosubscribe: aioresponses
    ) -> None:
        """``aiohttp`` не умеет сериализовать ``bool`` в query."""
        await vkteams.threads_autosubscribe(
            chat_id=CHAT_ID, enable=False, with_existing=False
        )

        params = single_query(ok_autosubscribe, AUTOSUBSCRIBE)
        assert params["enable"] == "false"
        assert params["withExisting"] == "false"

    async def test_with_existing_is_optional(
        self, vkteams: VKTeams, ok_autosubscribe: aioresponses
    ) -> None:
        await vkteams.threads_autosubscribe(chat_id=CHAT_ID, enable=True)

        assert "withExisting" not in single_query(ok_autosubscribe, AUTOSUBSCRIBE)

    async def test_returns_ok(
        self,
        vkteams: VKTeams,
        ok_autosubscribe: aioresponses,  # noqa: ARG002
    ) -> None:
        result = await vkteams.threads_autosubscribe(chat_id=CHAT_ID, enable=True)
        assert result.ok is True

    async def test_refusal_is_returned_not_raised(
        self, vkteams: VKTeams, mock_api: aioresponses
    ) -> None:
        mock_api.get(url_for("/threads/autosubscribe"), payload={"ok": False})

        result = await vkteams.threads_autosubscribe(chat_id=CHAT_ID, enable=True)

        assert result.ok is False


class TestThreadSubscribers:
    """``threads_subscribers_get`` и ``iter_thread_subscribers``."""

    async def test_params(self, vkteams: VKTeams, mock_api: aioresponses) -> None:
        mock_api.get(
            url_for("/threads/subscribers/get"),
            payload={"ok": True, "subscribers": []},
        )

        await vkteams.threads_subscribers_get(
            thread_id=THREAD_ID, page_size=10, cursor="c1"
        )

        assert single_query(mock_api, SUBSCRIBERS_GET) == {
            "token": vkteams.token,
            "threadId": THREAD_ID,
            "pageSize": "10",
            "cursor": "c1",
        }

    async def test_optional_params_are_omitted(
        self, vkteams: VKTeams, mock_api: aioresponses
    ) -> None:
        mock_api.get(
            url_for("/threads/subscribers/get"),
            payload={"ok": True, "subscribers": []},
        )

        await vkteams.threads_subscribers_get(thread_id=THREAD_ID)

        params = single_query(mock_api, SUBSCRIBERS_GET)
        assert set(params) == {"token", "threadId"}

    async def test_parses_subscribers(
        self, vkteams: VKTeams, mock_api: aioresponses
    ) -> None:
        mock_api.get(
            url_for("/threads/subscribers/get"),
            payload={
                "ok": True,
                "cursor": "next",
                "subscribers": [
                    {"sn": "user@example.com", "userState": {"lastseen": 1752920423}},
                    {"sn": "other@example.com"},
                ],
            },
        )

        result = await vkteams.threads_subscribers_get(thread_id=THREAD_ID)

        assert result.cursor == "next"
        assert [s.sn for s in result.subscribers] == [
            "user@example.com",
            "other@example.com",
        ]
        assert result.subscribers[0].userState is not None
        assert result.subscribers[0].userState.lastseen == 1752920423
        assert result.subscribers[1].userState is None

    async def test_iterator_follows_cursor(
        self, vkteams: VKTeams, mock_api: aioresponses
    ) -> None:
        mock_api.get(
            url_for("/threads/subscribers/get"),
            payload={"ok": True, "cursor": "page2", "subscribers": [{"sn": "a"}]},
        )
        mock_api.get(
            url_for("/threads/subscribers/get"),
            payload={"ok": True, "subscribers": [{"sn": "b"}]},
        )

        subscribers = [s async for s in vkteams.iter_thread_subscribers(THREAD_ID)]

        assert [s.sn for s in subscribers] == ["a", "b"]
        assert query_of(mock_api, SUBSCRIBERS_GET, 1)["cursor"] == ["page2"]

    async def test_iterator_stops_on_empty_page(
        self, vkteams: VKTeams, mock_api: aioresponses
    ) -> None:
        """Курсор без подписчиков не должен крутить запросы вечно."""
        mock_api.get(
            url_for("/threads/subscribers/get"),
            payload={"ok": True, "cursor": "page2", "subscribers": []},
        )

        subscribers = [s async for s in vkteams.iter_thread_subscribers(THREAD_ID)]

        assert subscribers == []

    async def test_iterator_passes_page_size(
        self, vkteams: VKTeams, mock_api: aioresponses
    ) -> None:
        mock_api.get(
            url_for("/threads/subscribers/get"),
            payload={"ok": True, "subscribers": [{"sn": "a"}]},
        )

        [s async for s in vkteams.iter_thread_subscribers(THREAD_ID, page_size=50)]

        assert single_query(mock_api, SUBSCRIBERS_GET)["pageSize"] == "50"
