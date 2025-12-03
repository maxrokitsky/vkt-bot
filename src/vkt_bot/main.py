import asyncio
import logging
import sys

import IPython
import uvicorn

from vkt_bot.db.session import async_session
from vkt_bot.app import dispatcher
from vkt_bot.webapp.app import app as webapp
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
    setup()
    asyncio.run(main())


def start_server() -> None:
    setup()
    uvicorn.run('vkt_bot.webapp.app:app', reload=True)


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
