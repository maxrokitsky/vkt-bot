from typing import Any

from fastapi import APIRouter, HTTPException

from bot_framework.exceptions import NotFoundError
from core.queries.user import UserByUsernameOrEmail
from core.repositories.user import CreateUserSchema, UpdateUserSchema, UserRepository
from core.security import get_password_hash
from dashboard.db import DB
from dashboard.dependencies import CurrentUser
from dashboard.schemas.pagination import PaginatedResponse
from dashboard.schemas.user import (
    CreateUserAPISchema,
    DetailUserAPISchema,
    PartialUpdateUserAPISchema,
    UpdateUserAPISchema,
)

user_router = APIRouter(
    prefix='/users',
    tags=['users'],
)


@user_router.get('', response_model=PaginatedResponse[DetailUserAPISchema])
async def list_users(session: DB, _user: CurrentUser, page: int = 1, page_size: int = 50) -> Any:
    """Список пользователей."""
    query = UserRepository(session).query()
    return await query.paginate(page=page, size=page_size)


@user_router.get('/{username}', response_model=DetailUserAPISchema)
async def get_user(session: DB, _user: CurrentUser, username: str) -> Any:
    """Получить пользователя."""
    user_repository = UserRepository(session)
    try:
        return await user_repository.get(username)
    except NotFoundError as err:
        raise HTTPException(status_code=404, detail='Пользователь не найден') from err


@user_router.post('', response_model=DetailUserAPISchema)
async def create_user(session: DB, _user: CurrentUser, user_data: CreateUserAPISchema) -> Any:
    """Создать пользователя."""
    user_repository = UserRepository(session)
    if await user_repository.query(UserByUsernameOrEmail(username=user_data.username, email=user_data.email)).exists():
        raise HTTPException(status_code=400, detail='Пользователь уже существует')
    return await user_repository.create(
        CreateUserSchema(
            username=user_data.username,
            hashed_password=get_password_hash(user_data.password),
            email=user_data.email,
            is_active=user_data.is_active,
            is_superuser=user_data.is_superuser,
        ),
        commit=True,
    )


@user_router.put('/{username}', response_model=DetailUserAPISchema)
async def update_user(session: DB, _user: CurrentUser, username: str, user_data: UpdateUserAPISchema) -> Any:
    """Редактировать пользователя."""
    user_repository = UserRepository(session)
    if not await user_repository.query(UserByUsernameOrEmail(username=username)).exists():
        raise HTTPException(status_code=404, detail='Пользователь не найден')
    return await user_repository.update(
        pk=username,
        data=UpdateUserSchema(
            hashed_password=get_password_hash(user_data.password),
            email=user_data.email,
            is_active=user_data.is_active,
            is_superuser=user_data.is_superuser,
        ),
        commit=True,
    )


@user_router.patch('/{username}', response_model=DetailUserAPISchema)
async def partial_update_user(
    session: DB, _user: CurrentUser, username: str, user_data: PartialUpdateUserAPISchema
) -> Any:
    """Редактировать пользователя (partial)."""
    user_repository = UserRepository(session)
    if not await user_repository.query(UserByUsernameOrEmail(username=username)).exists():
        raise HTTPException(status_code=404, detail='Пользователь не найден')
    data = user_data.model_dump(exclude_unset=True)
    if password := data.get('password'):
        data['hashed_password'] = password
    return await user_repository.update(
        pk=username,
        data=data,
        commit=True,
    )
