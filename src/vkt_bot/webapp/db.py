from collections.abc import AsyncGenerator
from typing import Annotated, Any

from fastapi import Depends
from sqlalchemy.ext.asyncio.session import AsyncSession

from vkt_bot.bot_framework.db.session import async_session


async def _get_db() -> AsyncGenerator[AsyncSession, Any]:
    async with async_session() as session:
        yield session


DB = Annotated[AsyncSession, Depends(_get_db)]
