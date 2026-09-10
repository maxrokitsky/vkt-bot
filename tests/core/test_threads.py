"""Хелперы обсуждений (``vkt_bot.core.threads``)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

from vkteams_client.types import ThreadAddResponse

from vkt_bot.core.threads import get_or_create_thread

if TYPE_CHECKING:
    from tests.conftest import FakeBot

CHAT_ID = "694348323@chat.agent"
MSG_ID = "7683820226256830640"
THREAD_ID = "693938330@chat.agent"


class TestGetOrCreateThread:
    """``get_or_create_thread``."""

    async def test_returns_thread_id(self, fake_bot: FakeBot) -> None:
        fake_bot.results["threads_add"] = ThreadAddResponse(ok=True, threadId=THREAD_ID)

        thread_id = await get_or_create_thread(fake_bot, CHAT_ID, MSG_ID)  # type: ignore[arg-type]

        assert thread_id == THREAD_ID
        (call,) = fake_bot.calls_of("threads_add")
        assert call.kwargs == {"chat_id": CHAT_ID, "msg_id": MSG_ID}

    async def test_repeated_call_gives_the_same_thread(self, fake_bot: FakeBot) -> None:
        """``threads/add`` — get-or-create, дублей на одно сообщение нет."""
        fake_bot.results["threads_add"] = ThreadAddResponse(ok=True, threadId=THREAD_ID)

        first = await get_or_create_thread(fake_bot, CHAT_ID, MSG_ID)  # type: ignore[arg-type]
        second = await get_or_create_thread(fake_bot, CHAT_ID, MSG_ID)  # type: ignore[arg-type]

        assert first == second == THREAD_ID
        assert len(fake_bot.calls_of("threads_add")) == 2

    async def test_refusal_returns_none(
        self, fake_bot: FakeBot, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Вложенных обсуждений нет: в треде API отвечает отказом."""
        fake_bot.results["threads_add"] = ThreadAddResponse(
            ok=False, description="Bad request"
        )

        with caplog.at_level(logging.WARNING, logger="vkt_bot"):
            assert await get_or_create_thread(fake_bot, THREAD_ID, MSG_ID) is None  # type: ignore[arg-type]

        assert "Bad request" in caplog.text

    async def test_ok_without_thread_id_returns_none(self, fake_bot: FakeBot) -> None:
        fake_bot.results["threads_add"] = ThreadAddResponse(ok=True)

        assert await get_or_create_thread(fake_bot, CHAT_ID, MSG_ID) is None  # type: ignore[arg-type]

    async def test_network_error_does_not_propagate(self, fake_bot: FakeBot) -> None:
        """Сбой не должен ронять обработчик, который просил тред."""
        fake_bot.errors["threads_add"] = TimeoutError("нет связи")

        assert await get_or_create_thread(fake_bot, CHAT_ID, MSG_ID) is None  # type: ignore[arg-type]
