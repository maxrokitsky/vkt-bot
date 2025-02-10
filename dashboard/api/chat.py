from typing import Any

from fastapi import APIRouter, HTTPException

from bot_framework.exceptions import NotFoundError
from core.repositories.chat import ChatRepository
from dashboard.db import DB
from dashboard.dependencies import CurrentUser
from dashboard.schemas.chat import DetailChatAPIModel
from dashboard.schemas.pagination import PaginatedResponse

chat_router = APIRouter(prefix='/chats', tags=['chats'])


@chat_router.get('', response_model=PaginatedResponse[DetailChatAPIModel])
async def list_chats(session: DB, _user: CurrentUser, page: int = 1, page_size: int = 50) -> Any:
    """Возврашает список чатов."""
    query = ChatRepository(session).query()
    return await query.paginate(page=page, size=page_size)


@chat_router.get('/{chat_id}', response_model=DetailChatAPIModel)
async def get_chat(session: DB, _user: CurrentUser, chat_id: str) -> Any:
    """Возвращает чат."""
    repository = ChatRepository(session)
    try:
        return await repository.get(chat_id)
    except NotFoundError as err:
        raise HTTPException(status_code=404, detail='Чат не найден') from err
