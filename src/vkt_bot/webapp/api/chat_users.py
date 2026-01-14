import math
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import selectinload

from vkt_bot.core.audit import AuditLogger
from vkt_bot.core.models import ChatMembership, ChatUser, RoleAssignment
from vkt_bot.core.models.log_entry import EntityType
from vkt_bot.core.repositories.role import (
    CreateRoleAssignmentSchema,
    RoleAssignmentRepository,
    RoleRepository,
)
from vkt_bot.core.repositories.user import ChatUserRepository
from vkt_bot.webapp.dependencies import CurrentAdminUser, CurrentUser, SessionDep
from vkt_bot.webapp.schemas.chat_user import (
    ChatUserChatResponse,
    ChatUserDetailResponse,
    ChatUserResponse,
    ChatUserRoleResponse,
    PaginatedChatUsersResponse,
)

router = APIRouter(prefix="/api/chat-users", tags=["chat-users"])


@router.get("", response_model=PaginatedChatUsersResponse)
async def list_chat_users(
    session: SessionDep,
    _: CurrentUser,
    page: int = 1,
    size: int = 20,
) -> PaginatedChatUsersResponse:
    """List all chat users with pagination."""
    # Get total count
    count_stmt = sa.select(sa.func.count()).select_from(ChatUser)
    total = await session.scalar(count_stmt) or 0

    # Get paginated users
    stmt = sa.select(ChatUser).offset((page - 1) * size).limit(size)
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
    # Load user with relationships
    stmt = (
        sa.select(ChatUser)
        .where(ChatUser.id == user_id)
        .options(
            selectinload(ChatUser.role_assignments).selectinload(RoleAssignment.role),
            selectinload(ChatUser.chat_memberships).selectinload(ChatMembership.chat),
        )
    )
    result = await session.scalar(stmt)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat user not found",
        )

    # Extract roles
    roles = [
        ChatUserRoleResponse(id=str(assignment.role.id), name=assignment.role.name)
        for assignment in result.role_assignments
    ]

    # Extract chats
    chats = [
        ChatUserChatResponse(id=membership.chat.id, type=membership.chat.type.value)
        for membership in result.chat_memberships
    ]

    return ChatUserDetailResponse(
        id=result.id,
        roles=roles,
        chats=chats,
    )


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
    audit = AuditLogger(session)

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

    # Audit log
    await audit.log_assign(
        entity_type=EntityType.ROLE_ASSIGNMENT,
        entity_id=str(assignment.id),
        user=current_admin,
        description=f"Assigned role {role.name} to user {user_id}",
        details={"role_id": str(role_id), "role_name": role.name, "user_id": user_id},
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
    audit = AuditLogger(session)

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

    # Audit log
    await audit.log_unassign(
        entity_type=EntityType.ROLE_ASSIGNMENT,
        entity_id=str(assignment_id),
        user=current_admin,
        description=f"Removed role {role_name} from user {user_id}",
        details={"role_id": str(role_id), "role_name": role_name, "user_id": user_id},
    )

    await session.commit()
