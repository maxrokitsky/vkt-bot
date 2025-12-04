import math

from fastapi import APIRouter, Depends

from vkt_bot.core.models.log_entry import LogEntry
from vkt_bot.core.queries.log_entry import (
    FilterByActionType,
    FilterByActorId,
    FilterByActorType,
    FilterByDateRange,
    FilterByEntityId,
    FilterByEntityType,
    OrderByTimestamp,
    SearchByDescription,
)
from vkt_bot.core.repositories.log_entry import LogEntryRepository
from vkt_bot.webapp.dependencies import CurrentAdminUser, SessionDep
from vkt_bot.webapp.schemas.log_entry import (
    LogEntryFilters,
    LogEntryResponse,
    PaginatedLogEntriesResponse,
)

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("", response_model=PaginatedLogEntriesResponse)
async def list_logs(
    session: SessionDep,
    _: CurrentAdminUser,
    page: int = 1,
    size: int = 20,
    filters: LogEntryFilters = Depends(),
) -> PaginatedLogEntriesResponse:
    """
    List audit logs with pagination and filtering. Admin only.

    Query parameters support all LogEntryFilters fields:
    - actor_type: Filter by actor type (web_user, bot_user, system)
    - actor_id: Filter by actor ID
    - action_type: Filter by action (create, update, delete, assign, unassign)
    - entity_type: Filter by entity type (user, chat_user, role, etc.)
    - entity_id: Filter by entity ID
    - start_date: Filter by date range start (ISO format)
    - end_date: Filter by date range end (ISO format)
    - search_query: Search in description (case-insensitive)
    """
    log_repo = LogEntryRepository(session)

    # Build queries based on filters
    queries = [OrderByTimestamp(descending=True)]

    if filters.actor_type:
        queries.append(FilterByActorType(actor_type=filters.actor_type))

    if filters.actor_id:
        queries.append(FilterByActorId(actor_id=filters.actor_id))

    if filters.action_type:
        queries.append(FilterByActionType(action_type=filters.action_type))

    if filters.entity_type:
        queries.append(FilterByEntityType(entity_type=filters.entity_type))

    if filters.entity_id:
        queries.append(FilterByEntityId(entity_id=filters.entity_id))

    if filters.start_date or filters.end_date:
        queries.append(
            FilterByDateRange(start_date=filters.start_date, end_date=filters.end_date)
        )

    if filters.search_query:
        queries.append(SearchByDescription(search_query=filters.search_query))

    # Execute query with pagination
    result = await log_repo.query(*queries).paginate(page=page, size=size)

    return PaginatedLogEntriesResponse(
        items=[LogEntryResponse.model_validate(log) for log in result.results],
        total=result.total,
        page=result.page,
        size=size,
        pages=math.ceil(result.total / size) if result.total > 0 else 0,
    )


@router.get("/{log_id}", response_model=LogEntryResponse)
async def get_log(
    log_id: int,
    session: SessionDep,
    _: CurrentAdminUser,
) -> LogEntryResponse:
    """Get specific log entry by ID. Admin only."""
    log_repo = LogEntryRepository(session)
    log = await log_repo.get(log_id)
    return LogEntryResponse.model_validate(log)
