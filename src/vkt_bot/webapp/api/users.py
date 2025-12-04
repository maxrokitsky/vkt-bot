import math

import sqlalchemy as sa
from fastapi import APIRouter, HTTPException, status

from vkt_bot.core.audit import AuditLogger
from vkt_bot.core.models.log_entry import EntityType
from vkt_bot.core.models.user import User
from vkt_bot.core.repositories.user import CreateUserSchema, UserRepository
from vkt_bot.core.security import get_password_hash
from vkt_bot.webapp.dependencies import CurrentAdminUser, SessionDep
from vkt_bot.webapp.schemas.user import (
    PaginatedUsersResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=PaginatedUsersResponse)
async def list_users(
    session: SessionDep,
    _: CurrentAdminUser,
    page: int = 1,
    size: int = 20,
) -> PaginatedUsersResponse:
    """List all users with pagination. Admin only."""
    user_repo = UserRepository(session)

    # Get total count
    count_stmt = sa.select(sa.func.count()).select_from(User)
    total = await session.scalar(count_stmt) or 0

    # Get paginated users
    stmt = sa.select(User).offset((page - 1) * size).limit(size)
    result = await session.scalars(stmt)
    users = result.all()

    return PaginatedUsersResponse(
        items=[UserResponse.model_validate(user) for user in users],
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if total > 0 else 0,
    )


@router.get("/{username}", response_model=UserResponse)
async def get_user(
    username: str,
    session: SessionDep,
    _: CurrentAdminUser,
) -> UserResponse:
    """Get user by username. Admin only."""
    user_repo = UserRepository(session)
    user = await user_repo.get_by_username(username)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserResponse.model_validate(user)


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    session: SessionDep,
    current_admin: CurrentAdminUser,
) -> UserResponse:
    """Create new user. Admin only."""
    user_repo = UserRepository(session)
    audit = AuditLogger(session)

    # Check if user already exists
    existing_user = await user_repo.get_by_username(user_data.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this username already exists",
        )

    # Create user with hashed password
    create_schema = CreateUserSchema(
        username=user_data.username,
        hashed_password=get_password_hash(user_data.password),
        email=f"{user_data.username}@example.com",  # Default email
        is_active=user_data.is_active,
        is_superuser=user_data.is_superuser,
    )

    user = await user_repo.create(create_schema, commit=False)

    # Audit log
    await audit.log_create(
        entity_type=EntityType.USER,
        entity_id=user.username,
        web_user=current_admin,
        description=f"Created user {user.username}",
        details={
            "is_active": user.is_active,
            "is_superuser": user.is_superuser,
        },
    )

    await session.commit()
    await session.refresh(user)
    return UserResponse.model_validate(user)


@router.patch("/{username}", response_model=UserResponse)
async def update_user(
    username: str,
    user_data: UserUpdate,
    session: SessionDep,
    current_admin: CurrentAdminUser,
) -> UserResponse:
    """Update user. Admin only."""
    user_repo = UserRepository(session)
    audit = AuditLogger(session)

    # Check if user exists
    user = await user_repo.get_by_username(username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Prepare update data
    update_data = {}
    if user_data.username is not None:
        # Check if new username is already taken
        if user_data.username != username:
            existing = await user_repo.get_by_username(user_data.username)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already taken",
                )
        update_data["username"] = user_data.username

    if user_data.password is not None:
        update_data["hashed_password"] = get_password_hash(user_data.password)

    if user_data.is_superuser is not None:
        update_data["is_superuser"] = user_data.is_superuser

    if user_data.is_active is not None:
        update_data["is_active"] = user_data.is_active

    # Update user
    if update_data:
        for key, value in update_data.items():
            setattr(user, key, value)
        session.add(user)

        # Audit log (log changed fields)
        changed_fields = {k: v for k, v in update_data.items() if k != "hashed_password"}
        if "hashed_password" in update_data:
            changed_fields["password"] = "***"

        await audit.log_update(
            entity_type=EntityType.USER,
            entity_id=username,
            web_user=current_admin,
            description=f"Updated user {username}",
            details={"changed_fields": changed_fields},
        )

        await session.commit()
        await session.refresh(user)

    return UserResponse.model_validate(user)


@router.delete("/{username}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    username: str,
    session: SessionDep,
    current_admin: CurrentAdminUser,
) -> None:
    """Delete user. Admin only."""
    user_repo = UserRepository(session)
    audit = AuditLogger(session)

    # Check if user exists
    user = await user_repo.get_by_username(username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    await user_repo.delete(username, commit=False)

    # Audit log
    await audit.log_delete(
        entity_type=EntityType.USER,
        entity_id=username,
        web_user=current_admin,
        description=f"Deleted user {username}",
    )

    await session.commit()
