import asyncio
import logging
import sys
from importlib import import_module

import IPython

from bot_framework.db.session import async_session
from teams_bot.app import broker, dispatcher

import_module('teams_bot.handlers')

logger = logging.getLogger('teams_bot')


async def main() -> None:
    # await broker.connect()
    try:
        await asyncio.gather(
            dispatcher.run(),
            # broker.execute(),
        )
    except asyncio.CancelledError:
        sys.stdout.write('\r')
        # await broker.close()
        logger.info('Shutting down...')


def run_server() -> None:
    asyncio.run(main())


def shell() -> None:
    session = async_session()
    try:
        IPython.start_ipython(
            argv=[],
            user_ns={
                'session': session,
            },
        )
    finally:
        asyncio.run(session.close())


if __name__ == '__main__':
    run_server()
