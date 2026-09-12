from importlib.metadata import version
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI

from .config import get_settings


__all__ = ("get_settings", "settings", "setup")

__version__ = version("vkt_bot")


def __getattr__(name: str) -> Any:  # noqa: ANN401
    """Ленивый доступ к ``vkt_bot.settings``.

    Импорт пакета не должен требовать полного окружения — настройки
    читаются только при первом обращении.
    """
    if name == "settings":
        return get_settings()
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


def setup(app: FastAPI) -> None:
    """Собрать приложение вместе с веб-частью.

    Тонкая обёртка: общая сборка живёт в ``vkt_bot.bootstrap`` — её же
    зовут воркер и планировщик, которым ``FastAPI`` взять неоткуда.
    """
    from vkt_bot.bootstrap import bootstrap, install_api

    bootstrap()
    install_api(app)


if TYPE_CHECKING:
    from .config import VktSettings

    settings: VktSettings
