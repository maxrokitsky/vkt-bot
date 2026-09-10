"""Сводка для главной страницы панели."""

import datetime

import sqlalchemy as sa
from fastapi import APIRouter, Query
from sqlalchemy.ext.asyncio import AsyncSession

from vkt_bot.core.models import Chat, ChatUser, LogEntry, Role, Webhook
from vkt_bot.webapp.dependencies import CurrentUser, SessionDep, is_admin
from vkt_bot.webapp.schemas.overview import (
    ActivityPoint,
    OverviewCounts,
    OverviewResponse,
)

router = APIRouter(prefix="/api/overview", tags=["overview"])


async def count_rows(
    session: AsyncSession, model: type, *where: sa.ColumnElement
) -> int:
    """Количество строк модели с необязательным условием."""
    stmt = sa.select(sa.func.count()).select_from(model)
    if where:
        stmt = stmt.where(*where)
    return await session.scalar(stmt) or 0


def as_date(value: object) -> datetime.date:
    """Привести значение ``date(timestamp)`` к дате.

    PostgreSQL отдаёт ``date``, SQLite — строку ``YYYY-MM-DD``.
    """
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    return datetime.date.fromisoformat(str(value))


async def activity_by_day(session: AsyncSession, days: int) -> list[ActivityPoint]:
    """Число записей аудита по дням, включая дни без действий."""
    today = datetime.date.today()
    first_day = today - datetime.timedelta(days=days - 1)

    day = sa.func.date(LogEntry.timestamp)
    stmt = (
        sa.select(day, sa.func.count())
        .where(
            LogEntry.timestamp
            >= datetime.datetime.combine(first_day, datetime.time.min)
        )
        .group_by(day)
    )
    counts = {as_date(row[0]): row[1] for row in (await session.execute(stmt)).all()}

    return [
        ActivityPoint(
            date=first_day + datetime.timedelta(days=offset),
            count=counts.get(first_day + datetime.timedelta(days=offset), 0),
        )
        for offset in range(days)
    ]


@router.get("", response_model=OverviewResponse)
async def get_overview(
    session: SessionDep,
    current_user: CurrentUser,
    days: int = Query(14, ge=1, le=90),
) -> OverviewResponse:
    """Счётчики и активность для главной страницы."""
    counts = OverviewCounts(
        chats=await count_rows(session, Chat),
        chat_users=await count_rows(session, ChatUser),
        roles=await count_rows(session, Role),
        webhooks=await count_rows(
            session, Webhook, Webhook.created_by == current_user.id
        ),
        webhooks_active=await count_rows(
            session, Webhook, Webhook.created_by == current_user.id, Webhook.is_active
        ),
    )

    activity = await activity_by_day(session, days) if is_admin(current_user) else []

    return OverviewResponse(counts=counts, activity=activity, activity_days=days)
