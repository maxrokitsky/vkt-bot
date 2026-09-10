import asyncio
import json
from pathlib import Path
import sys

import IPython
from pydantic import ValidationError
import uvicorn

from vkt_bot.config import get_settings
from vkt_bot.db.session import async_session
from vkt_bot.app import dispatcher
from vkt_bot.webapp.app import create_app
from .loggers import main_logger


def check_settings() -> None:
    """Проверить настройки и завершить процесс, если они неполные.

    Единственная точка, где невалидная конфигурация приводит к ``sys.exit``:
    импорт модулей приложения сам по себе процесс не роняет.
    """
    try:
        get_settings()
    except ValidationError as e:
        print(e, file=sys.stderr)  # noqa: T201
        sys.exit(1)


async def main() -> None:
    try:
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
    # create_app() сам вызывает setup(): логирование, модели, плагины.
    create_app()
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
