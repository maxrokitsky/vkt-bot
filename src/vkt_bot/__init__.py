import importlib
from importlib.metadata import version
import importlib.metadata
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI

from vkt_bot.utils.log import init_logging, setup_sentry
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
    init_logging()
    setup_sentry()
    importlib.import_module("vkt_bot.core.models")
    importlib.import_module("vkt_bot.core.handlers")
    for plugin in importlib.metadata.entry_points(group="vkt_bot.plugins"):
        module = plugin.load()
        module.install(app)


if TYPE_CHECKING:
    from .config import VktSettings

    settings: VktSettings
