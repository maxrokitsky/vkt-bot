import structlog
from fastapi import FastAPI

logger = structlog.get_logger("vkt_gitlab")


def install() -> None:
    """Подключить плагин. Зовут все процессы: бот, веб, воркер."""
    from . import models  # noqa: F401
    from . import handlers  # noqa: F401
    from .events import install_events

    install_events()
    logger.info("plugin.installed", plugin="gitlab")


def install_api(webapp: FastAPI) -> None:
    """Отдать свои роутеры. Зовёт только веб-процесс."""
    from . import api

    webapp.include_router(api.gl_router)
