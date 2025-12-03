import math

import sqlalchemy as sa
from fastapi import APIRouter, HTTPException, status

from vkt_bot.app import bot
from vkt_bot.core.models.chat import Chat
from vkt_bot.core.repositories.chat import ChatRepository
from vkt_bot.webapp.dependencies import CurrentAdminUser, SessionDep
from vkt_bot.webapp.schemas.chat import (
    ChatResponse,
    PaginatedChatsResponse,
    SendMessageRequest,
    SendMessageResponse,
)

router = APIRouter(prefix="/api/chats", tags=["chats"])


@router.get("", response_model=PaginatedChatsResponse)
async def list_chats(
    session: SessionDep,
    _: CurrentAdminUser,
    page: int = 1,
    size: int = 20,
) -> PaginatedChatsResponse:
    """List all chats with pagination. Admin only."""
    # Get total count
    count_stmt = sa.select(sa.func.count()).select_from(Chat)
    total = await session.scalar(count_stmt) or 0

    # Get paginated chats
    stmt = sa.select(Chat).offset((page - 1) * size).limit(size)
    result = await session.scalars(stmt)
    chats = result.all()

    return PaginatedChatsResponse(
        items=[ChatResponse.model_validate(chat) for chat in chats],
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if total > 0 else 0,
    )


@router.get("/{chat_id}", response_model=ChatResponse)
async def get_chat(
    chat_id: str,
    session: SessionDep,
    _: CurrentAdminUser,
) -> ChatResponse:
    """Get chat by ID. Admin only."""
    chat_repo = ChatRepository(session)
    chat = await chat_repo.get_or_none(chat_id)

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat not found",
        )

    return ChatResponse.model_validate(chat)


@router.post("/{chat_id}/send-message", response_model=SendMessageResponse)
async def send_message(
    chat_id: str,
    request: SendMessageRequest,
    session: SessionDep,
    _: CurrentAdminUser,
) -> SendMessageResponse:
    """Send a message to a chat. Admin only."""
    chat_repo = ChatRepository(session)
    chat = await chat_repo.get_or_none(chat_id)

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat not found",
        )

    try:
        await bot.send_text(
            chat_id=chat_id,
            text=request.text,
            parse_mode=request.parse_mode,
        )
        return SendMessageResponse(
            success=True,
            message="Message sent successfully",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send message: {str(e)}",
        ) from e
