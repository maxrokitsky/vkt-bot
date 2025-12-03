from vkt_bot.webapp.app import app as webapp


def install() -> None:
    from . import models  # noqa: F401
    from . import handlers  # noqa: F401
    from . import api

    webapp.include_router(api.gl_router)
    print("gl is installed")
