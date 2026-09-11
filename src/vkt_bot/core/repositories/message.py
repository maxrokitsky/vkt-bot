"""Репозиторий истории сообщений."""

from __future__ import annotations

import datetime
from typing import Any

import sqlalchemy as sa
from pydantic import BaseModel

from vkt_bot.core.models.message import Message
from vkt_bot.db.repository import AsyncRepository
from vkt_bot.utils.datetime import to_naive_utc, utcnow


class CreateMessageSchema(BaseModel):
    """CreateMessageSchema."""

    chat_id: str
    msg_id: str
    user_id: str | None = None
    text: str | None = None
    ts: datetime.datetime
    is_outgoing: bool = False


class MessageRepository(AsyncRepository[Message, int, CreateMessageSchema, Any]):
    """Message Repository."""

    async def get_by_msg_id(self, chat_id: str, msg_id: str) -> Message | None:
        """Сообщение по паре чат—идентификатор."""
        return await self.session.scalar(
            sa.select(Message).where(
                Message.chat_id == chat_id, Message.msg_id == msg_id
            )
        )

    async def record(
        self,
        chat_id: str,
        msg_id: str,
        *,
        user_id: str | None = None,
        text: str | None = None,
        ts: datetime.datetime | None = None,
        is_outgoing: bool = False,
    ) -> Message:
        """Записать сообщение; повторный вызов на той же паре обновляет строку.

        Уникальность по ``(chat_id, msg_id)`` держит индекс, но проверка
        идёт запросом: ``ON CONFLICT`` пришлось бы писать по диалектам, а
        события приходят по одному в цикле опроса.
        """
        existing = await self.get_by_msg_id(chat_id, msg_id)
        if existing is not None:
            if text is not None and existing.text != text:
                existing.text = text
                self.session.add(existing)
            return existing
        return await self.create(
            CreateMessageSchema(
                chat_id=chat_id,
                msg_id=msg_id,
                user_id=user_id,
                text=text,
                ts=to_naive_utc(ts) if ts else utcnow(),
                is_outgoing=is_outgoing,
            )
        )

    async def mark_edited(
        self,
        chat_id: str,
        msg_id: str,
        text: str | None,
        edited_at: datetime.datetime | None = None,
    ) -> Message | None:
        """Обновить текст. ``None``, если сообщения в истории нет."""
        message = await self.get_by_msg_id(chat_id, msg_id)
        if message is None:
            return None
        message.text = text
        message.edited_at = to_naive_utc(edited_at) if edited_at else utcnow()
        self.session.add(message)
        return message

    async def mark_deleted(self, chat_id: str, msg_id: str) -> Message | None:
        """Пометить сообщение удалённым."""
        message = await self.get_by_msg_id(chat_id, msg_id)
        if message is None:
            return None
        message.deleted_at = utcnow()
        self.session.add(message)
        return message

    def _visible(self) -> sa.Select[Any]:
        """Базовый запрос: удалённые не отдаются никогда."""
        return sa.select(Message).where(Message.deleted_at.is_(None))

    async def recent(self, chat_id: str, limit: int = 20) -> list[Message]:
        """Последние сообщения чата в хронологическом порядке.

        Выбираются последние по времени, а отдаются от старых к новым —
        именно в таком виде история идёт в промпт и читается человеком.
        """
        stmt = (
            self._visible()
            .where(Message.chat_id == chat_id)
            .order_by(Message.ts.desc(), Message.id.desc())
            .limit(limit)
        )
        rows = list((await self.session.scalars(stmt)).all())
        rows.reverse()
        return rows

    async def search(
        self,
        chat_id: str,
        query: str,
        limit: int = 20,
    ) -> list[Message]:
        """Поиск по тексту.

        ``ilike`` по кириллице корректно работает только на PostgreSQL —
        на SQLite он регистрозависим для не-ASCII.
        """
        stmt = (
            self._visible()
            .where(Message.chat_id == chat_id, Message.text.ilike(f"%{query}%"))
            .order_by(Message.ts.desc(), Message.id.desc())
            .limit(limit)
        )
        rows = list((await self.session.scalars(stmt)).all())
        rows.reverse()
        return rows

    async def in_range(
        self,
        chat_id: str,
        *,
        after: datetime.datetime | None = None,
        before: datetime.datetime | None = None,
        limit: int = 20,
    ) -> list[Message]:
        """Сообщения чата в интервале времени."""
        stmt = self._visible().where(Message.chat_id == chat_id)
        if after is not None:
            stmt = stmt.where(Message.ts >= to_naive_utc(after))
        if before is not None:
            stmt = stmt.where(Message.ts <= to_naive_utc(before))
        stmt = stmt.order_by(Message.ts.desc(), Message.id.desc()).limit(limit)
        rows = list((await self.session.scalars(stmt)).all())
        rows.reverse()
        return rows

    async def purge_older_than(self, days: int) -> int:
        """Удалить сообщения старше ``days``. ``days <= 0`` — не чистить."""
        if days <= 0:
            return 0
        edge = utcnow() - datetime.timedelta(days=days)
        result = await self.session.execute(sa.delete(Message).where(Message.ts < edge))
        return result.rowcount or 0

    async def enforce_chat_limit(self, max_per_chat: int) -> int:
        """Оставить в каждом чате не больше ``max_per_chat`` сообщений.

        Потолок на чат нужен рядом со сроком хранения: один болтливый чат
        успевает набрать миллионы строк раньше, чем истечёт срок.
        """
        if max_per_chat <= 0:
            return 0

        removed = 0
        chat_ids = (
            await self.session.scalars(sa.select(Message.chat_id).distinct())
        ).all()
        for chat_id in chat_ids:
            edge_id = await self.session.scalar(
                sa.select(Message.id)
                .where(Message.chat_id == chat_id)
                .order_by(Message.ts.desc(), Message.id.desc())
                .limit(1)
                .offset(max_per_chat - 1)
            )
            if edge_id is None:
                continue
            edge = await self.session.scalar(
                sa.select(Message.ts).where(Message.id == edge_id)
            )
            result = await self.session.execute(
                sa.delete(Message).where(
                    Message.chat_id == chat_id,
                    sa.or_(
                        Message.ts < edge,
                        sa.and_(Message.ts == edge, Message.id < edge_id),
                    ),
                )
            )
            removed += result.rowcount or 0
        return removed
