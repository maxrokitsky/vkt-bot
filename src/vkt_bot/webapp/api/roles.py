import math
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, HTTPException, status

from vkt_bot.core.models.role import Role
from vkt_bot.core.repositories.role import (
    CreateRoleSchema,
    RoleRepository,
)
from vkt_bot.db.exceptions import NotFoundError
from vkt_bot.webapp.dependencies import CurrentAdminUser, SessionDep
from vkt_bot.webapp.schemas.role import (
    PaginatedRolesResponse,
    RoleCreate,
    RoleResponse,
    RoleUpdate,
)

router = APIRouter(prefix="/api/roles", tags=["roles"])


@router.get("", response_model=PaginatedRolesResponse)
async def list_roles(
    session: SessionDep,
    _: CurrentAdminUser,
    page: int = 1,
    size: int = 20,
) -> PaginatedRolesResponse:
    """List all roles with pagination. Admin only."""
    # Get total count
    count_stmt = sa.select(sa.func.count()).select_from(Role)
    total = await session.scalar(count_stmt) or 0

    # Get paginated roles
    stmt = sa.select(Role).offset((page - 1) * size).limit(size)
    result = await session.scalars(stmt)
    roles = result.all()

    return PaginatedRolesResponse(
        items=[RoleResponse.model_validate(role) for role in roles],
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if total > 0 else 0,
    )


@router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    role_data: RoleCreate,
    session: SessionDep,
    _: CurrentAdminUser,
) -> RoleResponse:
    """Create new role. Admin only."""
    role_repo = RoleRepository(session)

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
    role = await role_repo.create(create_schema, commit=True)

    return RoleResponse.model_validate(role)


@router.patch("/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: UUID,
    role_data: RoleUpdate,
    session: SessionDep,
    _: CurrentAdminUser,
) -> RoleResponse:
    """Update role. Admin only."""
    role_repo = RoleRepository(session)

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

        role.name = role_data.name
        session.add(role)
        await session.commit()
        await session.refresh(role)

    return RoleResponse.model_validate(role)


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: UUID,
    session: SessionDep,
    _: CurrentAdminUser,
) -> None:
    """Delete role. Admin only."""
    role_repo = RoleRepository(session)

    # Check if role exists
    role = await role_repo.get_or_none(role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )

    await role_repo.delete(role_id, commit=True)
