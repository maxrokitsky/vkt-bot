"""Лента событий.

Заменила `/api/logs`: у события теперь есть тип, источник, значимость и
чат, а не пара «действие + сущность».
"""

import math

from fastapi import APIRouter, Depends, HTTPException, status
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from vkt_bot.core.events.registry import all_specs
from vkt_bot.core.models.chat import ChatMembership
from vkt_bot.core.models.event import EventRecord
from vkt_bot.core.models.user import ChatUser
from vkt_bot.core.queries.event import (
    FilterByActorId,
    FilterByChatId,
    FilterByDateRange,
    FilterByEntity,
    FilterBySeverity,
    FilterBySource,
    FilterByType,
    FilterByTypes,
    OrderByTs,
    SearchBySummary,
    VisibleToUser,
)
from vkt_bot.core.repositories.event import EventRepository
from vkt_bot.db.query import Query
from vkt_bot.webapp.dependencies import CurrentUser, SessionDep, is_admin
from vkt_bot.webapp.schemas.event import (
    EventFilters,
    EventResponse,
    EventTypeResponse,
    PaginatedEventsResponse,
)

router = APIRouter(prefix="/api/events", tags=["events"])

#: Поля ``payload``, в которых лежит переписка. Обычному участнику лента
#: показывается без них: он видит, что произошло, но не что было
#: написано.
TEXT_FIELDS = frozenset(
    {"text", "text_preview", "message", "body", "caption", "summary_text"}
)


def public_event(event: EventRecord, *, with_texts: bool) -> EventResponse:
    """Событие для выдачи наружу, при необходимости без текстов."""
    response = EventResponse.model_validate(event)
    if not with_texts and response.payload:
        response.payload = {
            key: value
            for key, value in response.payload.items()
            if key not in TEXT_FIELDS
        }
    return response


def build_queries(filters: EventFilters) -> list[Query]:
    """Собрать фильтры ленты."""
    queries: list[Query] = [OrderByTs(descending=True)]

    if filters.type:
        queries.append(FilterByType(type=filters.type))
    if filters.source:
        queries.append(FilterBySource(source=filters.source))
    if filters.severity:
        queries.append(FilterBySeverity(severity=filters.severity))
    if filters.actor_id:
        queries.append(FilterByActorId(actor_id=filters.actor_id))
    if filters.chat_id:
        queries.append(FilterByChatId(chat_id=filters.chat_id))
    if filters.entity_type or filters.entity_id:
        queries.append(
            FilterByEntity(entity_type=filters.entity_type, entity_id=filters.entity_id)
        )
    if filters.start_date or filters.end_date:
        queries.append(
            FilterByDateRange(start_date=filters.start_date, end_date=filters.end_date)
        )
    if filters.search_query:
        queries.append(SearchBySummary(search_query=filters.search_query))

    return queries


@router.get("/types", response_model=list[EventTypeResponse])
async def list_event_types(_: CurrentUser) -> list[EventTypeResponse]:
    """Реестр типов событий.

    Панель строит по нему подписи и список фильтров — иначе словарь
    названий пришлось бы держать во фронтенде и синхронизировать руками,
    а типы плагинов туда не попали бы вовсе.
    """
    return [
        EventTypeResponse(
            type=spec.type,
            title=spec.title,
            source=spec.source,
            severity=spec.severity,
            persist=spec.persist,
            chat_scoped=spec.chat_scoped,
        )
        for spec in all_specs()
    ]


@router.get("", response_model=PaginatedEventsResponse)
async def list_events(
    session: SessionDep,
    current_user: CurrentUser,
    page: int = 1,
    size: int = 20,
    filters: EventFilters = Depends(),
) -> PaginatedEventsResponse:
    """Лента событий.

    Админ видит всё. Обычный участник — события чатов, в которых
    состоит, и без текстов сообщений.
    """
    admin = is_admin(current_user)
    queries = build_queries(filters)
    if not admin:
        queries.append(VisibleToUser(user_id=current_user.id))

    result = (
        await EventRepository(session).query(*queries).paginate(page=page, size=size)
    )

    return PaginatedEventsResponse(
        items=[public_event(event, with_texts=admin) for event in result.results],
        total=result.total,
        page=result.page,
        size=size,
        pages=math.ceil(result.total / size) if result.total > 0 else 0,
    )


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> EventResponse:
    """Одно событие."""
    admin = is_admin(current_user)
    event = await EventRepository(session).get_or_none(event_id)

    if event is None or not (
        admin or await in_users_chat(session, event, current_user)
    ):
        # Скрытое событие отвечает так же, как несуществующее: иначе по
        # кодам ответа можно перебирать чужую активность.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Event not found"
        )
    return public_event(event, with_texts=admin)


async def in_users_chat(
    session: AsyncSession, event: EventRecord, user: ChatUser
) -> bool:
    """Состоит ли пользователь в чате события."""
    if event.chat_id is None:
        return False
    found = await session.scalar(
        sa.select(ChatMembership.id).where(
            ChatMembership.chat_id == event.chat_id,
            ChatMembership.user_id == user.id,
        )
    )
    return found is not None


def chat_scoped_types() -> list[str]:
    """Типы, которым место в ленте чата."""
    return [spec.type for spec in all_specs() if spec.chat_scoped]


async def chat_events(
    session: SessionDep,
    chat_id: str,
    *,
    with_texts: bool,
    page: int,
    size: int,
) -> PaginatedEventsResponse:
    """Лента одного чата — используется роутером чатов."""
    result = (
        await EventRepository(session)
        .query(
            FilterByChatId(chat_id=chat_id),
            FilterByTypes(types=chat_scoped_types()),
            OrderByTs(descending=True),
        )
        .paginate(page=page, size=size)
    )
    return PaginatedEventsResponse(
        items=[public_event(event, with_texts=with_texts) for event in result.results],
        total=result.total,
        page=result.page,
        size=size,
        pages=math.ceil(result.total / size) if result.total > 0 else 0,
    )
