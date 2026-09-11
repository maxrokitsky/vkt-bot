"""API агента для панели: сессии и расход токенов.

Доступ устроен как в ленте событий: админ видит всё, обычный участник —
только свои сессии. Вопрос, заданный агенту, говорит о человеке не
меньше, чем ответ, поэтому чужие диалоги не показываются никому.

Отдельная предосторожность — автоконтекст. В первом сообщении диалога
лежит подложенная в промпт переписка чата; наружу она не уходит
(`prompts.strip_context`), иначе панель стала бы вторым способом читать
чужие чаты — в обход проверок инструмента `chat_messages`.
"""

from __future__ import annotations

import datetime
import math
import uuid

import sqlalchemy as sa
from fastapi import APIRouter, HTTPException, Query, status

from vkt_bot.core.models import Chat, ChatUser
from vkt_bot.db.query import Query as DbQuery
from vkt_bot.webapp.dependencies import CurrentUser, SessionDep, is_admin

from .agent import agent_enabled, configured
from .config import get_ai_settings
from .models import AgentMessage, AgentSession, SessionStatus
from .prompts import strip_context
from .queries import (
    FilterByChat,
    FilterByDateRange,
    FilterByStatus,
    FilterByUser,
    OrderByCreated,
)
from .repositories import AgentMessageRepository, AgentSessionRepository
from .schemas import (
    AgentMessageResponse,
    AgentSessionDetailResponse,
    AgentSessionResponse,
    AgentStatusResponse,
    AgentUsageActor,
    AgentUsagePoint,
    AgentUsageResponse,
    AgentUsageTotals,
    PaginatedAgentSessionsResponse,
)
from .session import day_start

router = APIRouter(prefix="/api/ai", tags=["ai"])

#: Сколько строк в топах расхода. Больше — это уже не сводка.
TOP_SIZE = 10

#: Длина превью вопроса в списке.
QUESTION_PREVIEW = 200


@router.get("/status", response_model=AgentStatusResponse)
async def get_status(session: SessionDep, _: CurrentUser) -> AgentStatusResponse:
    """Включён ли агент и с какими лимитами.

    Панель без этого не отличила бы «агента выключили» от «никто ещё не
    спрашивал»: и там, и там пустой список.
    """
    settings = get_ai_settings()
    return AgentStatusResponse(
        configured=configured(),
        enabled=await agent_enabled(session),
        model=settings.model,
        max_steps=settings.max_steps,
        context_messages=settings.context_messages,
        daily_token_budget=settings.daily_token_budget,
        retention_days=settings.retention_days,
    )


async def first_questions(
    session: SessionDep, ids: list[uuid.UUID]
) -> dict[uuid.UUID, str]:
    """Первый вопрос каждой сессии — одним запросом, без N+1.

    Берётся минимальный id сообщения роли ``user``: сообщения в диалоге
    идут по возрастанию, а `created_at` у соседних совпадает.
    """
    if not ids:
        return {}
    firsts = (
        sa.select(sa.func.min(AgentMessage.id))
        .where(AgentMessage.session_id.in_(ids), AgentMessage.role == "user")
        .group_by(AgentMessage.session_id)
    )
    rows = await session.execute(
        sa.select(AgentMessage.session_id, AgentMessage.content).where(
            AgentMessage.id.in_(firsts)
        )
    )
    return {
        session_id: strip_context(content or "")[:QUESTION_PREVIEW]
        for session_id, content in rows.all()
    }


async def names(session: SessionDep, rows: list[AgentSession]) -> tuple[dict, dict]:
    """Имена участников и названия чатов для страницы списка."""
    user_ids = {row.user_id for row in rows}
    chat_ids = {row.chat_id for row in rows}

    users = (
        await session.scalars(sa.select(ChatUser).where(ChatUser.id.in_(user_ids)))
    ).all()
    chats = (await session.scalars(sa.select(Chat).where(Chat.id.in_(chat_ids)))).all()
    return (
        {user.id: user.display_name for user in users},
        {chat.id: chat.title for chat in chats},
    )


def public_session(
    row: AgentSession,
    *,
    user_names: dict[str, str],
    chat_titles: dict[str, str | None],
    question: str | None,
) -> AgentSessionResponse:
    """Сессия для выдачи наружу."""
    return AgentSessionResponse(
        id=row.id,
        chat_id=row.chat_id,
        chat_title=chat_titles.get(row.chat_id),
        user_id=row.user_id,
        user_name=user_names.get(row.user_id, row.user_id),
        thread_id=row.thread_id,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
        tokens_in=row.tokens_in,
        tokens_out=row.tokens_out,
        question=question,
    )


@router.get("/sessions", response_model=PaginatedAgentSessionsResponse)
async def list_sessions(
    session: SessionDep,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    # Без потолка один запрос с ``size=100000`` выгружает все диалоги
    # разом — и базе, и памяти это заметно.
    size: int = Query(20, ge=1, le=100),
    user_id: str | None = None,
    chat_id: str | None = None,
    session_status: SessionStatus | None = None,
    start_date: datetime.datetime | None = None,
    end_date: datetime.datetime | None = None,
) -> PaginatedAgentSessionsResponse:
    """Диалоги с агентом.

    Админ видит все, остальные — только свои: фильтр по участнику для них
    не расширяет выдачу, а сужает её внутри собственных сессий.
    """
    queries: list[DbQuery] = [OrderByCreated(descending=True)]
    if chat_id:
        queries.append(FilterByChat(chat_id=chat_id))
    if session_status:
        queries.append(FilterByStatus(status=session_status))
    if start_date or end_date:
        queries.append(FilterByDateRange(start_date=start_date, end_date=end_date))

    if is_admin(current_user):
        if user_id:
            queries.append(FilterByUser(user_id=user_id))
    else:
        queries.append(FilterByUser(user_id=current_user.id))

    result = (
        await AgentSessionRepository(session)
        .query(*queries)
        .paginate(page=page, size=size)
    )
    user_names, chat_titles = await names(session, result.results)
    questions = await first_questions(session, [row.id for row in result.results])

    return PaginatedAgentSessionsResponse(
        items=[
            public_session(
                row,
                user_names=user_names,
                chat_titles=chat_titles,
                question=questions.get(row.id),
            )
            for row in result.results
        ],
        total=result.total,
        page=result.page,
        size=size,
        pages=math.ceil(result.total / size) if result.total > 0 else 0,
    )


@router.get("/sessions/{session_id}", response_model=AgentSessionDetailResponse)
async def get_session(
    session_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> AgentSessionDetailResponse:
    """Ход одного диалога."""
    row = await AgentSessionRepository(session).get_or_none(session_id)
    if row is None or not (is_admin(current_user) or row.user_id == current_user.id):
        # Чужая сессия отвечает так же, как несуществующая: иначе по кодам
        # ответа перебирается чужая активность.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    user_names, chat_titles = await names(session, [row])
    messages = await AgentMessageRepository(session).history(session_id)

    return AgentSessionDetailResponse(
        session=public_session(
            row,
            user_names=user_names,
            chat_titles=chat_titles,
            question=(
                strip_context(messages[0].content or "")[:QUESTION_PREVIEW]
                if messages
                else None
            ),
        ),
        messages=[
            AgentMessageResponse(
                id=message.id,
                role=message.role,
                content=strip_context(message.content) if message.content else None,
                tool_name=message.tool_name,
                created_at=message.created_at,
            )
            for message in messages
        ],
    )


def as_date(value: object) -> datetime.date:
    """Привести ``date(timestamp)`` к дате: PostgreSQL отдаёт ``date``,
    SQLite — строку. То же приведение, что в сводке панели."""
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    return datetime.date.fromisoformat(str(value))


@router.get("/usage", response_model=AgentUsageResponse)
async def get_usage(
    session: SessionDep,
    current_user: CurrentUser,
    days: int = Query(14, ge=1, le=90),
) -> AgentUsageResponse:
    """Расход токенов за период.

    Админ видит всех, обычный участник — только себя. Топы у него пустые
    не потому, что данных нет, а потому что чужой расход — это чужая
    активность.
    """
    admin = is_admin(current_user)
    first_day = datetime.date.today() - datetime.timedelta(days=days - 1)
    since = datetime.datetime.combine(first_day, datetime.time.min)

    scope = [AgentSession.created_at >= since]
    if not admin:
        scope.append(AgentSession.user_id == current_user.id)

    tokens = AgentSession.tokens_in + AgentSession.tokens_out

    totals_row = (
        await session.execute(
            sa.select(
                sa.func.count(AgentSession.id),
                sa.func.coalesce(sa.func.sum(AgentSession.tokens_in), 0),
                sa.func.coalesce(sa.func.sum(AgentSession.tokens_out), 0),
                sa.func.count(sa.distinct(AgentSession.user_id)),
            ).where(*scope)
        )
    ).one()
    failed = await session.scalar(
        sa.select(sa.func.count()).where(
            *scope, AgentSession.status == SessionStatus.FAILED
        )
    )

    day = sa.func.date(AgentSession.created_at)
    per_day = (
        await session.execute(
            sa.select(day, sa.func.count(), sa.func.coalesce(sa.func.sum(tokens), 0))
            .where(*scope)
            .group_by(day)
        )
    ).all()
    counted = {as_date(row[0]): (row[1], row[2]) for row in per_day}

    return AgentUsageResponse(
        days=days,
        totals=AgentUsageTotals(
            sessions=totals_row[0],
            tokens_in=int(totals_row[1]),
            tokens_out=int(totals_row[2]),
            users=totals_row[3],
            failed=failed or 0,
        ),
        by_day=[
            AgentUsagePoint(
                date=first_day + datetime.timedelta(days=offset),
                sessions=counted.get(
                    first_day + datetime.timedelta(days=offset), (0, 0)
                )[0],
                tokens=int(
                    counted.get(first_day + datetime.timedelta(days=offset), (0, 0))[1]
                ),
            )
            for offset in range(days)
        ],
        top_users=await top_actors(session, scope, by_user=True) if admin else [],
        top_chats=await top_actors(session, scope, by_user=False),
        daily_token_budget=get_ai_settings().daily_token_budget,
        spent_today=await AgentSessionRepository(session).tokens_since(
            current_user.id, day_start()
        ),
    )


async def top_actors(
    session: SessionDep, scope: list, *, by_user: bool
) -> list[AgentUsageActor]:
    """Кто (или какой чат) израсходовал больше всех."""
    key = AgentSession.user_id if by_user else AgentSession.chat_id
    tokens = AgentSession.tokens_in + AgentSession.tokens_out

    rows = (
        await session.execute(
            sa.select(key, sa.func.count(), sa.func.coalesce(sa.func.sum(tokens), 0))
            .where(*scope)
            .group_by(key)
            .order_by(sa.func.coalesce(sa.func.sum(tokens), 0).desc())
            .limit(TOP_SIZE)
        )
    ).all()
    if not rows:
        return []

    ids = [row[0] for row in rows]
    if by_user:
        found = (
            await session.scalars(sa.select(ChatUser).where(ChatUser.id.in_(ids)))
        ).all()
        titles = {user.id: user.display_name for user in found}
    else:
        found = (await session.scalars(sa.select(Chat).where(Chat.id.in_(ids)))).all()
        # У обсуждения своего чата в таблице нет, а название треда пустое —
        # показываем идентификатор, иначе строка выглядит безымянной.
        titles = {chat.id: chat.title or chat.id for chat in found}

    return [
        AgentUsageActor(
            id=row[0],
            name=titles.get(row[0], row[0]),
            sessions=row[1],
            tokens=int(row[2]),
        )
        for row in rows
    ]
