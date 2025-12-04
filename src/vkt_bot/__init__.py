import importlib
from importlib.metadata import version
import importlib.metadata

from fastapi import FastAPI

from vkt_bot.utils.log import init_logging, setup_sentry
from .config import settings


__all__ = ("settings",)

__version__ = version("vkt_bot")


def setup(app: FastAPI) -> None:
    init_logging()
    setup_sentry()
    importlib.import_module("vkt_bot.core.models")
    importlib.import_module("vkt_bot.core.handlers")
    for plugin in importlib.metadata.entry_points(group="vkt_bot.plugins"):
        module = plugin.load()
        module.install(app)
