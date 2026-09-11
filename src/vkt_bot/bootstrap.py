"""Сборка приложения без веба.

``setup(app)`` смешивал три несвязанных дела — логирование, регистрацию
моделей и загрузку плагинов — и требовал ``FastAPI`` даже там, где веба
нет. Процессов теперь четыре: бот, веб, воркер и планировщик. Общая часть
у них одна, а роутеры нужны ровно одному.

Отсюда два хука у плагина. ``install()`` зовут все процессы: модели,
хендлеры, типы событий, фоновые задачи. ``install_api(app)`` —
необязательный, только ``include_router``, и зовёт его ``create_app()``.
Вариант ``install(webapp=None)`` был бы хуже: подпись врала бы про
контракт, и каждый плагин обзавёлся бы веткой ``if webapp is not None``.
"""

from __future__ import annotations

import importlib
import importlib.metadata
import sys
from typing import TYPE_CHECKING

from pydantic import ValidationError

from vkt_bot.logging_setup import init_logging, setup_sentry

if TYPE_CHECKING:
    from collections.abc import Callable

    from fastapi import FastAPI

#: Повторный вызов не должен второй раз настраивать логи, Sentry и
#: плагины: ``shell()`` поднимает и приложение, и IPython в одном
#: процессе, а тесты дёргают сборку по многу раз.
_done = False

#: Веб-части плагинов. Заполняются в ``bootstrap()``, разворачиваются в
#: ``install_api()``: роутеры подключает веб-процесс, а не плагин —
#: воркеру ``FastAPI`` взять неоткуда.
_api_installers: list[Callable[[FastAPI], None]] = []


def check_settings() -> None:
    """Проверить настройки и завершить процесс, если они неполные.

    Единственная точка, где невалидная конфигурация приводит к
    ``sys.exit``: импорт модулей приложения сам по себе процесс не роняет.
    """
    from vkt_bot.config import get_settings

    try:
        get_settings()
    except ValidationError as e:
        print(e, file=sys.stderr)  # noqa: T201
        sys.exit(1)


def bootstrap() -> None:
    """Логи, Sentry, модели, хендлеры, плагины. Зовут все процессы."""
    global _done  # noqa: PLW0603
    if _done:
        return

    init_logging()
    setup_sentry()
    importlib.import_module("vkt_bot.core.models")
    importlib.import_module("vkt_bot.core.handlers")

    # Действия бота становятся событиями: клиент сам в базу не ходит.
    from vkt_bot.app import bot
    from vkt_bot.core.bot_events import record_bot_action
    from vkt_bot.core.messages import record_outgoing

    bot.event_sink = record_bot_action
    # Свои сообщения — в историю чата: в поток событий они не приходят.
    bot.message_sink = record_outgoing

    for plugin in importlib.metadata.entry_points(group="vkt_bot.plugins"):
        module = plugin.load()
        module.install()
        if (installer := getattr(module, "install_api", None)) is not None:
            _api_installers.append(installer)

    _done = True


def install_api(app: FastAPI) -> None:
    """Подключить веб-части плагинов. Зовёт только ``create_app()``."""
    bootstrap()
    for installer in _api_installers:
        installer(app)
