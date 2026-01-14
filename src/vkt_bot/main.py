import asyncio
import json
import logging
from pathlib import Path
import sys

import IPython
import uvicorn

from vkt_bot.db.session import async_session
from vkt_bot.app import dispatcher
from vkt_bot.webapp.app import create_app
from .loggers import main_logger
from . import setup

logging.getLogger('passlib').setLevel(logging.ERROR)


async def main() -> None:
    try:
        await dispatcher.run()
    except asyncio.CancelledError:
        sys.stdout.write("\r")
        main_logger.info("Завершение работы")


def start_bot() -> None:
    create_app()
    asyncio.run(main())


def start_server() -> None:
    uvicorn.run('vkt_bot.webapp.app:create_app', port=8765, reload=True)

def export_schema() -> None:
    Path('openapi.json').write_text(json.dumps(create_app().openapi()))
    print('openapi.json exported')

def shell() -> None:
    setup()
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
