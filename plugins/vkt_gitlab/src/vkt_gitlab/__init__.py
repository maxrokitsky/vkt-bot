from fastapi import FastAPI


def install(webapp: FastAPI) -> None:
    from . import models  # noqa: F401
    from . import handlers  # noqa: F401
    from . import api

    webapp.include_router(api.gl_router)
    print("gl is installed")
