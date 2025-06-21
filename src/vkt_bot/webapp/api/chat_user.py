from typing import Any

from fastapi import APIRouter, HTTPException

from vkt_bot.bot_framework.exceptions import NotFoundError
from vkt_bot.core.repositories.user import ChatUserRepository
from vkt_bot.webapp.db import DB
from vkt_bot.webapp.dependencies import CurrentUser
from vkt_bot.webapp.schemas.chat_user import DetailChatUserAPISchema

chat_user_router = APIRouter(prefix="/chat_users", tags=["chat_users"])


@chat_user_router.get("/{username}", response_model=DetailChatUserAPISchema)
async def get_user(session: DB, _user: CurrentUser, username: str) -> Any:
    """Получить пользователя."""
    user_repository = ChatUserRepository(session)
    try:
        return await user_repository.get(username)
    except NotFoundError as err:
        raise HTTPException(status_code=404, detail="Пользователь не найден") from err
