from typing import Any, Sequence

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from bot_framework.db import Statement, Model
from bot_framework.exceptions import NotFoundError


class QueryResult[T: Model]:
    statement: Statement
    session: AsyncSession

    def __init__(self, session: AsyncSession, statement: Statement) -> None:
        self.session = session
        self.statement = statement

    async def one(self):
        if result := await self.one_or_none():
            return result
        raise NotFoundError

    async def one_or_none(self) -> T | None:
        return await self.session.scalar(self.statement)

    async def exists(self) -> bool:
        return bool(await self.session.scalar(self.statement))

    async def list(self) -> Sequence[T]:
        return (await self.session.scalars(self.statement)).all()


class Query(BaseModel):
    def apply[T_Statement: sa.Select[Any]](self, statement: T_Statement) -> T_Statement: ...
