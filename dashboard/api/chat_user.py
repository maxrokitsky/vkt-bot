from typing import Any

from fastapi import APIRouter, HTTPException

from bot_framework.exceptions import NotFoundError
from core.repositories.user import ChatUserRepository
from dashboard.db import DB
from dashboard.dependencies import CurrentUser
from dashboard.schemas.chat_user import DetailChatUserAPISchema

chat_user_router = APIRouter(prefix='/chat_users', tags=['chat_users'])


@chat_user_router.get('/{username}', response_model=DetailChatUserAPISchema)
async def get_user(session: DB, _user: CurrentUser, username: str) -> Any:
    """Получить пользователя."""
    user_repository = ChatUserRepository(session)
    try:
        return await user_repository.get(username)
    except NotFoundError as err:
        raise HTTPException(status_code=404, detail='Пользователь не найден') from err
