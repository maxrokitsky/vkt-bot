import structlog
from fastapi import FastAPI

logger = structlog.get_logger("vkt_gitlab")


def install(webapp: FastAPI) -> None:
    from . import models  # noqa: F401
    from . import handlers  # noqa: F401
    from . import api
    from .events import install_events

    install_events()
    webapp.include_router(api.gl_router)
    logger.info("plugin.installed", plugin="gitlab")
