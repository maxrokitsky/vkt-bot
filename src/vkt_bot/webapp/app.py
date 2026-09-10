from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from vkt_bot import setup

from .middleware import RequestContextMiddleware
from .api import (
    auth,
    chats,
    roles,
    chat_users,
    bot_settings,
    events,
    overview,
    webhooks,
)

STATIC_DIR = "./static"


def create_app(*args, **kwargs) -> FastAPI:  # noqa: ARG001
    app = FastAPI(title="VKT Bot API", version="1.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Добавляется последним — значит, оказывается снаружи CORS: контекст
    # нужен и для ответов, которые CORS формирует сам.
    app.add_middleware(RequestContextMiddleware)

    app.include_router(auth.router)
    app.include_router(chats.router)
    app.include_router(roles.router)
    app.include_router(chat_users.router)
    app.include_router(bot_settings.router)
    app.include_router(events.router)
    app.include_router(overview.router)
    app.include_router(webhooks.router)
    app.include_router(webhooks.public_router)

    @app.get("/")
    async def root():
        return {"message": "VKT Bot API"}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    setup(app)

    Path(STATIC_DIR).mkdir(parents=True, exist_ok=True)
    app.mount("/", StaticFiles(directory="./static", html=True), name="static")

    return app
