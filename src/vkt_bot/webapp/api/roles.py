import math
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from vkt_bot.core.audit import AuditLogger
from vkt_bot.core.models.log_entry import EntityType
from vkt_bot.core.models.role import Role, RoleAssignment
from vkt_bot.core.repositories.role import (
    CreateRoleAssignmentSchema,
    CreateRoleSchema,
    RoleAssignmentRepository,
    RoleRepository,
)
from vkt_bot.core.repositories.user import ChatUserRepository
from vkt_bot.db.exceptions import NotFoundError
from vkt_bot.webapp.dependencies import CurrentAdminUser, CurrentUser, SessionDep
from vkt_bot.webapp.schemas.role import (
    AddRoleMemberRequest,
    PaginatedRolesResponse,
    RoleCreate,
    RoleMemberResponse,
    RoleResponse,
    RoleUpdate,
    RoleWithMembersResponse,
)

router = APIRouter(prefix="/api/roles", tags=["roles"])

#: Число участников роли — скалярный подзапрос, чтобы не тянуть назначения.
MEMBER_COUNT = (
    sa.select(sa.func.count(RoleAssignment.id))
    .where(RoleAssignment.role_id == Role.id)
    .correlate(Role)
    .scalar_subquery()
)


def role_response(role: Role, member_count: int) -> RoleResponse:
    """Ответ по роли с посчитанным составом."""
    return RoleResponse(id=role.id, name=role.name, member_count=member_count)


async def count_members(session: AsyncSession, role_id: UUID) -> int:
    """Сколько участников у роли."""
    return (
        await session.scalar(
            sa.select(sa.func.count(RoleAssignment.id)).where(
                RoleAssignment.role_id == role_id
            )
        )
        or 0
    )


@router.get("", response_model=PaginatedRolesResponse)
async def list_roles(
    session: SessionDep,
    _: CurrentUser,
    page: int = 1,
    size: int = 20,
) -> PaginatedRolesResponse:
    """List all roles with pagination."""
    # Get total count
    count_stmt = sa.select(sa.func.count()).select_from(Role)
    total = await session.scalar(count_stmt) or 0

    # Get paginated roles
    stmt = (
        sa.select(Role, MEMBER_COUNT.label("member_count"))
        .order_by(Role.name)
        .offset((page - 1) * size)
        .limit(size)
    )
    rows = (await session.execute(stmt)).all()

    return PaginatedRolesResponse(
        items=[role_response(role, member_count) for role, member_count in rows],
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if total > 0 else 0,
    )


@router.get("/{role_id}", response_model=RoleWithMembersResponse)
async def get_role(
    role_id: UUID,
    session: SessionDep,
    _: CurrentUser,
) -> RoleWithMembersResponse:
    """Get role by ID with its members."""
    stmt = (
        sa.select(Role)
        .where(Role.id == role_id)
        .options(selectinload(Role.assignments).selectinload(RoleAssignment.user))
    )
    role = await session.scalar(stmt)

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )

    members = [
        RoleMemberResponse(
            user_id=assignment.user.id,
            display_name=assignment.user.display_name,
            is_bot=assignment.user.is_bot,
        )
        for assignment in role.assignments
    ]
    members.sort(key=lambda member: member.display_name.lower())

    return RoleWithMembersResponse(
        id=role.id,
        name=role.name,
        member_count=len(members),
        members=members,
    )


@router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    role_data: RoleCreate,
    session: SessionDep,
    current_admin: CurrentAdminUser,
) -> RoleResponse:
    """Create new role. Admin only."""
    role_repo = RoleRepository(session)
    audit = AuditLogger(session)

    # Check if role with this name already exists
    try:
        existing_role = await role_repo.get_by_name(role_data.name)
        if existing_role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Role with this name already exists",
            )
    except NotFoundError:
        pass

    # Create role
    create_schema = CreateRoleSchema(name=role_data.name)
    role = await role_repo.create(create_schema, commit=False)
    # id проставляется только на flush: без него в аудит уходит "None".
    await session.flush()

    # Audit log
    await audit.log_create(
        entity_type=EntityType.ROLE,
        entity_id=str(role.id),
        user=current_admin,
        description=f"Created role {role.name}",
        details={"name": role.name},
    )

    await session.commit()
    await session.refresh(role)

    return role_response(role, member_count=0)


@router.patch("/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: UUID,
    role_data: RoleUpdate,
    session: SessionDep,
    current_admin: CurrentAdminUser,
) -> RoleResponse:
    """Update role. Admin only."""
    role_repo = RoleRepository(session)
    audit = AuditLogger(session)

    # Check if role exists
    role = await role_repo.get_or_none(role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )

    # Update name if provided
    if role_data.name is not None:
        # Check if new name is already taken
        try:
            existing = await role_repo.get_by_name(role_data.name)
            if existing and existing.id != role_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Role with this name already exists",
                )
        except NotFoundError:
            pass

        old_name = role.name
        role.name = role_data.name
        session.add(role)

        # Audit log
        await audit.log_update(
            entity_type=EntityType.ROLE,
            entity_id=str(role_id),
            user=current_admin,
            description=f"Updated role {old_name} to {role.name}",
            details={"old_name": old_name, "new_name": role.name},
        )

        await session.commit()
        await session.refresh(role)

    return role_response(role, await count_members(session, role_id))


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: UUID,
    session: SessionDep,
    current_admin: CurrentAdminUser,
) -> None:
    """Delete role. Admin only."""
    role_repo = RoleRepository(session)
    audit = AuditLogger(session)

    # Check if role exists
    role = await role_repo.get_or_none(role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )

    role_name = role.name
    await role_repo.delete(role_id, commit=False)

    # Audit log
    await audit.log_delete(
        entity_type=EntityType.ROLE,
        entity_id=str(role_id),
        user=current_admin,
        description=f"Deleted role {role_name}",
        details={"name": role_name},
    )

    await session.commit()


@router.post("/{role_id}/members", status_code=status.HTTP_201_CREATED)
async def add_role_member(
    role_id: UUID,
    data: AddRoleMemberRequest,
    session: SessionDep,
    current_admin: CurrentAdminUser,
) -> RoleMemberResponse:
    """Add member to role. Admin only."""
    role_repo = RoleRepository(session)
    user_repo = ChatUserRepository(session)
    assignment_repo = RoleAssignmentRepository(session)
    audit = AuditLogger(session)

    role = await role_repo.get_or_none(role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )

    user = await user_repo.get_or_none(data.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat user not found",
        )

    existing = await session.scalar(
        sa.select(RoleAssignment).where(
            RoleAssignment.role_id == role_id,
            RoleAssignment.user_id == user.id,
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has this role",
        )

    assignment = await assignment_repo.create(
        CreateRoleAssignmentSchema(role_id=role_id, user_id=user.id), commit=False
    )
    await session.flush()

    await audit.log_assign(
        entity_type=EntityType.ROLE_ASSIGNMENT,
        entity_id=str(assignment.id),
        user=current_admin,
        description=f"Assigned role {role.name} to user {user.id}",
        details={"role_id": str(role_id), "role_name": role.name, "user_id": user.id},
    )

    await session.commit()

    return RoleMemberResponse(
        user_id=user.id,
        display_name=user.display_name,
        is_bot=user.is_bot,
    )


@router.delete("/{role_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_role_member(
    role_id: UUID,
    user_id: str,
    session: SessionDep,
    current_admin: CurrentAdminUser,
) -> None:
    """Remove member from role. Admin only."""
    audit = AuditLogger(session)

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

    await session.delete(assignment)

    await audit.log_unassign(
        entity_type=EntityType.ROLE_ASSIGNMENT,
        entity_id=str(assignment_id),
        user=current_admin,
        description=f"Removed role {role_name} from user {user_id}",
        details={"role_id": str(role_id), "role_name": role_name, "user_id": user_id},
    )

    await session.commit()
