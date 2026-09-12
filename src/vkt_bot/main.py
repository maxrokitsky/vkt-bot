import asyncio
import json
from pathlib import Path
import sys

import IPython
import uvicorn

from vkt_bot.bootstrap import bootstrap, check_settings
from vkt_bot.core.lifespans import background_tasks
from vkt_bot.db.session import async_session
from vkt_bot.app import dispatcher
from vkt_bot.webapp.app import create_app
from vkt_bot.worker import broker_client, local_retention
from .loggers import main_logger

__all__ = (
    "check_settings",
    "export_schema",
    "main",
    "shell",
    "start_bot",
    "start_server",
)


async def main() -> None:
    try:
        # Брокер снаружи: он нужен хендлерам всё время их работы и
        # закрывается последним. Явно, а не через ``lifespans.register``:
        # тот намеренно глотает сбой любой фабрики, а молча подняться без
        # очереди — значит отвечать «не смог» на каждый вопрос агенту.
        async with broker_client(), local_retention(), background_tasks():
            await dispatcher.run()
    except asyncio.CancelledError:
        sys.stdout.write("\r")
        # Только лог: писать в базу на отмене корутины — ловить
        # оборванное соединение в момент, когда цикл уже гасится.
        main_logger.info("bot.stopped")


def start_bot() -> None:
    check_settings()
    create_app()
    asyncio.run(main())


def start_server() -> None:
    check_settings()
    uvicorn.run(
        "vkt_bot.webapp.app:create_app",
        host="0.0.0.0",
        port=8765,
        reload=True,
        # Свою строку про запрос пишет RequestContextMiddleware — с
        # request_id и в общем формате.
        access_log=False,
    )


def export_schema() -> None:
    check_settings()
    Path("openapi.json").write_text(json.dumps(create_app().openapi()))
    print("openapi.json exported")


def shell() -> None:
    check_settings()
    # Веб в IPython не нужен, а логи, модели и плагины — нужны.
    bootstrap()
    session = async_session()
    try:
        IPython.start_ipython(
            argv=[],
            user_ns={
                "session": session,
            },
        )
    finally:
        asyncio.run(session.close())


if __name__ == "__main__":
    start_bot()
