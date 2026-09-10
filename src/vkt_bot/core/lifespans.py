"""Фоновые задачи на время работы бота.

Ядру не полагается знать про плагины, но плагину нужно место, где его
фоновая работа начнётся и, главное, аккуратно закончится. Поэтому
``install()`` регистрирует здесь контекстный менеджер, а ``main.main``
входит во все зарегистрированные разом.

Это только про бота: ``uv run server`` фоновых задач не поднимает — там
нет опроса событий, и агенту с чисткой журнала браться неоткуда.
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator, Callable
from typing import Any

import structlog

logger = structlog.get_logger("vkt_bot.lifespans")

#: Фабрики контекстных менеджеров: ``install()`` кладёт сюда свою.
_lifespans: list[Callable[[], Any]] = []


def register(factory: Callable[[], Any]) -> None:
    """Зарегистрировать фоновую работу на время жизни бота."""
    if factory not in _lifespans:
        _lifespans.append(factory)


def registered() -> list[Callable[[], Any]]:
    """Всё, что зарегистрировано."""
    return list(_lifespans)


@contextlib.asynccontextmanager
async def background_tasks() -> AsyncIterator[None]:
    """Войти во все зарегистрированные менеджеры.

    Сбой одного не должен мешать остальным и уж точно не должен мешать
    боту запуститься: фоновая работа — не то, ради чего он существует.
    """
    async with contextlib.AsyncExitStack() as stack:
        for factory in _lifespans:
            try:
                await stack.enter_async_context(factory())
            except Exception:
                logger.exception(
                    "lifespan.failed", factory=getattr(factory, "__qualname__", factory)
                )
        yield
