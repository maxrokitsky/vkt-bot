from dataclasses import dataclass
import math
from typing import Any, Sequence

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from vkt_bot.bot_framework.db import Statement, Model
from vkt_bot.bot_framework.exceptions import NotFoundError


@dataclass
class Page[T: Model]:
    results: list[T]
    total: int
    page: int


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

    async def paginate(self, page: int, size: int) -> Page[T]:
        statement = self.statement

        page = max(page, 1)
        total = (
            await self.session.scalar(
                sa.select(sa.func.count()).select_from(statement.froms[0])
            )
            or 0
        )
        max_pages = math.ceil(total / size) or 1
        page = min(page, max_pages)

        limit = size
        offset = (page - 1) * size
        results = (
            await self.session.scalars(statement.limit(limit).offset(offset))
        ).all()
        return Page(results=list(results), total=total, page=page)


class Query(BaseModel):
    def apply[T_Statement: sa.Select[Any]](
        self, statement: T_Statement
    ) -> T_Statement: ...
