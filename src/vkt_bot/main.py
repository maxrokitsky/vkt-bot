import asyncio
import logging
import sys
from importlib import import_module

import IPython
import uvicorn

from vkt_bot.bot_framework.db.session import async_session
from vkt_bot.teams_bot.app import dispatcher
from vkt_bot.webapp.app import app as webapp
from vkt_bot.utils.log import init_logging
import_module("vkt_bot.teams_bot.handlers")

logger = logging.getLogger("teams_bot")


async def main() -> None:
    # await broker.connect()
    try:
        await asyncio.gather(
            dispatcher.run(),
            # broker.execute(),
        )
    except asyncio.CancelledError:
        sys.stdout.write("\r")
        # await broker.close()
        logger.info("Shutting down...")


def start_bot() -> None:
    init_logging()
    asyncio.run(main())


def start_server() -> None:
    uvicorn.run(webapp)


def shell() -> None:
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
