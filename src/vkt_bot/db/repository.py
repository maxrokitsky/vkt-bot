from collections.abc import Sequence
from typing import Any, get_args, get_origin

import sqlalchemy as sa
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from vkt_bot.db.base import Model
from vkt_bot.db.exceptions import NotFoundError
from vkt_bot.db.query import Query, QueryResult


class AsyncRepository[
    T_Model: Model,
    T_PK: Any,
    T_CreateSchema: BaseModel,
    T_UpdateSchema: BaseModel,
]:
    """Repository."""

    session: AsyncSession
    model: type[T_Model]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def __init_subclass__(cls) -> None:
        """__init_subclass__."""
        if not hasattr(cls, "model"):
            for orig_cls in cls.__orig_bases__:
                if issubclass(get_origin(orig_cls), AsyncRepository):  # type: ignore [reportUnknownArgumentType]
                    args = get_args(orig_cls)
                    if args:
                        cls.model = args[0]
                    break

        super().__init_subclass__()

    async def get_or_none(self, pk: T_PK) -> T_Model | None:
        """Get or none."""
        try:
            return await self.get(pk=pk)
        except NotFoundError:
            return None

    async def list(self) -> Sequence[T_Model]:
        return (await self.session.scalars(sa.select(self.model))).all()

    async def get(self, pk: T_PK) -> T_Model:
        """Get."""
        pk_column = sa.inspect(self.model).primary_key[0]
        if result := await self.session.scalar(
            sa.select(self.model).where(pk_column == pk)
        ):
            return result
        raise NotFoundError

    def query(self, *queries: Query) -> QueryResult[T_Model]:
        stmt = sa.select(self.model)
        for query in queries:
            stmt = query.apply(stmt)
        return QueryResult(self.session, stmt)

    async def exists(self, pk: T_PK) -> bool:
        """Get."""
        return bool(await self.get_or_none(pk))

    async def create(self, schema: T_CreateSchema, *, commit: bool = False) -> T_Model:
        """Save."""
        obj = self.model()
        for k, v in schema.model_dump().items():
            setattr(obj, k, v)
        self.session.add(obj)
        if commit:
            await self.session.commit()
            await self.session.refresh(obj)
        return obj

    async def update(
        self, pk: T_PK, data: T_UpdateSchema | dict[str, Any], *, commit: bool = False
    ) -> T_Model:
        """Update."""
        if isinstance(data, BaseModel):
            data = data.model_dump()
        obj = await self.get(pk)
        for k, v in data.items():
            setattr(obj, k, v)
        self.session.add(obj)
        if commit:
            await self.session.commit()
            await self.session.refresh(obj)
        return obj

    async def delete(self, pk: T_PK, *, commit: bool = False) -> None:
        """Save."""
        stmt = sa.delete(self.model).where(self.model.id == pk)
        res = await self.session.execute(stmt)
        if not res.rowcount:
            raise NotFoundError
        if commit:
            await self.session.commit()
