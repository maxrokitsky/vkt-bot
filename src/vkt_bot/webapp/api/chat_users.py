import math
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import selectinload

from vkt_bot.core.events import Actor, EventType, emit
from vkt_bot.core.models import ChatMembership, ChatUser, RoleAssignment
from vkt_bot.core.models.event import EntityType
from vkt_bot.core.queries.user import ChatUserInChatQuery, ChatUserSearchQuery
from vkt_bot.core.repositories.role import (
    CreateRoleAssignmentSchema,
    RoleAssignmentRepository,
    RoleRepository,
)
from vkt_bot.core.repositories.user import ChatUserRepository
from vkt_bot.config import settings
from vkt_bot.webapp.dependencies import (
    CurrentAdminUser,
    CurrentOwnerUser,
    CurrentUser,
    SessionDep,
)
from vkt_bot.webapp.schemas.chat_user import (
    ChatUserDetailResponse,
    ChatUserResponse,
    PaginatedChatUsersResponse,
    UpdateChatUserRequest,
)

router = APIRouter(prefix="/api/chat-users", tags=["chat-users"])

#: Роли участника нужны почти в каждом ответе — грузим их одним запросом.
WITH_ROLES = selectinload(ChatUser.role_assignments).selectinload(RoleAssignment.role)


@router.get("", response_model=PaginatedChatUsersResponse)
async def list_chat_users(
    session: SessionDep,
    _: CurrentUser,
    page: int = 1,
    size: int = 20,
    search: str | None = None,
    chat_id: str | None = None,
) -> PaginatedChatUsersResponse:
    """List all chat users with pagination.

    Optional search by name or id and filter by chat membership.
    """
    count_stmt = sa.select(sa.func.count()).select_from(ChatUser)
    users_stmt = sa.select(ChatUser)
    for query in (
        ChatUserSearchQuery(search=search),
        ChatUserInChatQuery(chat_id=chat_id),
    ):
        count_stmt = query.apply(count_stmt)
        users_stmt = query.apply(users_stmt)

    # Get total count
    total = await session.scalar(count_stmt) or 0

    # Get paginated users
    stmt = (
        users_stmt.options(WITH_ROLES)
        .order_by(ChatUser.created_at.desc(), ChatUser.id)
        .offset((page - 1) * size)
        .limit(size)
    )
    result = await session.scalars(stmt)
    users = result.all()

    return PaginatedChatUsersResponse(
        items=[ChatUserResponse.model_validate(user) for user in users],
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if total > 0 else 0,
    )


@router.get("/{user_id}", response_model=ChatUserDetailResponse)
async def get_chat_user(
    user_id: str,
    session: SessionDep,
    _: CurrentUser,
) -> ChatUserDetailResponse:
    """Get chat user by ID with roles and chats."""
    stmt = (
        sa.select(ChatUser)
        .where(ChatUser.id == user_id)
        .options(
            WITH_ROLES,
            selectinload(ChatUser.chat_memberships).selectinload(ChatMembership.chat),
        )
    )
    user = await session.scalar(stmt)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat user not found",
        )

    return ChatUserDetailResponse.model_validate(user)


@router.patch("/{user_id}", response_model=ChatUserResponse)
async def update_chat_user(
    user_id: str,
    data: UpdateChatUserRequest,
    session: SessionDep,
    current_owner: CurrentOwnerUser,
) -> ChatUserResponse:
    """Update chat user. Owner only."""
    # Prevent modifying owner's admin status
    if settings.owner_id and user_id == settings.owner_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify owner's admin status. Owner is always admin.",
        )

    # Check if user exists
    user = await session.scalar(
        sa.select(ChatUser).where(ChatUser.id == user_id).options(WITH_ROLES)
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat user not found",
        )

    # Track the change for audit
    old_status = user.is_superuser
    new_status = data.is_superuser

    if old_status != new_status:
        # Update user
        user.is_superuser = new_status
        session.add(user)

        granted = "выдал" if new_status else "снял"
        await emit(
            session,
            EventType.CHAT_USER_UPDATED,
            actor=Actor.from_user(current_owner),
            entity=(EntityType.CHAT_USER, user_id),
            payload={
                "target": user.display_name,
                "target_id": user_id,
                "field": "is_superuser",
                "old_value": old_status,
                "new_value": new_status,
            },
            summary=(
                f"{current_owner.display_name} {granted} права администратора "
                f"участнику {user.display_name}"
            ),
        )

        # Без refresh: ``expire_on_commit=False``, а refresh сбросил бы
        # загруженные роли и увёл их в ленивую загрузку внутри корутины.
        await session.commit()

    return ChatUserResponse.model_validate(user)


@router.post(
    "/{user_id}/roles/{role_id}",
    status_code=status.HTTP_201_CREATED,
)
async def assign_role_to_user(
    user_id: str,
    role_id: UUID,
    session: SessionDep,
    current_admin: CurrentAdminUser,
) -> dict[str, str]:
    """Assign role to chat user. Admin only."""
    user_repo = ChatUserRepository(session)
    role_repo = RoleRepository(session)
    assignment_repo = RoleAssignmentRepository(session)

    # Check if user exists
    user = await user_repo.get_or_none(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat user not found",
        )

    # Check if role exists
    role = await role_repo.get_or_none(role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )

    # Check if assignment already exists
    stmt = sa.select(RoleAssignment).where(
        RoleAssignment.role_id == role_id,
        RoleAssignment.user_id == user_id,
    )
    existing = await session.scalar(stmt)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has this role",
        )

    # Create assignment
    create_schema = CreateRoleAssignmentSchema(
        role_id=role_id,
        user_id=user_id,
    )
    assignment = await assignment_repo.create(create_schema, commit=False)
    # id проставляется только на flush: без него в аудит уходит "None".
    await session.flush()

    await emit(
        session,
        EventType.ROLE_ASSIGNED,
        actor=Actor.from_user(current_admin),
        entity=(EntityType.ROLE_ASSIGNMENT, str(assignment.id)),
        payload={
            "role": role.name,
            "role_id": str(role_id),
            "target": user.display_name,
            "target_id": user_id,
        },
    )

    await session.commit()

    return {"message": "Role assigned successfully"}


@router.delete("/{user_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_role_from_user(
    user_id: str,
    role_id: UUID,
    session: SessionDep,
    current_admin: CurrentAdminUser,
) -> None:
    """Remove role from chat user. Admin only."""
    # Find assignment with role eagerly loaded
    stmt = (
        sa.select(RoleAssignment)
        .where(
            RoleAssignment.role_id == role_id,
            RoleAssignment.user_id == user_id,
        )
        .options(selectinload(RoleAssignment.role))
    )
    assignment = await session.scalar(stmt)

    if not assignment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User does not have this role",
        )

    role_name = assignment.role.name
    assignment_id = assignment.id

    # Delete assignment
    await session.delete(assignment)

    await emit(
        session,
        EventType.ROLE_UNASSIGNED,
        actor=Actor.from_user(current_admin),
        entity=(EntityType.ROLE_ASSIGNMENT, str(assignment_id)),
        payload={"role": role_name, "role_id": str(role_id), "target_id": user_id},
    )

    await session.commit()
