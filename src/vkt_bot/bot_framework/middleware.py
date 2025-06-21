from __future__ import annotations

from collections.abc import AsyncGenerator, Coroutine, Generator
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vkt_bot.bot_framework.bot.types import Event


class Middleware:
    def on_event(
        self,
        event: Event,  # noqa: ARG002
    ) -> (
        AsyncGenerator[None, Any]
        | Generator[None, Any, None]
        | Coroutine[Any, Any, Any]
        | None
    ):
        return None

    def on_callback(
        self,
        event: Event,  # noqa: ARG002
    ) -> (
        AsyncGenerator[None, Any]
        | Generator[None, Any, None]
        | Coroutine[Any, Any, Any]
        | None
    ):
        return None
