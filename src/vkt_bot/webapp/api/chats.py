import math
from typing import Any

import sqlalchemy as sa
from fastapi import APIRouter, HTTPException, status

from vkt_bot.app import bot
from vkt_bot.core.models import Chat, ChatMembership, ChatUser, Webhook
from vkt_bot.core.queries.chat import ChatSearchQuery
from vkt_bot.core.repositories.chat import ChatRepository
from vkt_bot.webapp.dependencies import (
    CurrentAdminUser,
    CurrentUser,
    SessionDep,
    is_admin,
)
from vkt_bot.webapp.schemas.chat import (
    ChatDetailResponse,
    ChatResponse,
    PaginatedChatsResponse,
    SendMessageRequest,
    SendMessageResponse,
)
from vkt_bot.webapp.schemas.webhook import WebhookListResponse, WebhookResponse

router = APIRouter(prefix="/api/chats", tags=["chats"])


def visible_webhooks(chat_id: str, user: ChatUser) -> sa.Select[Any]:
    """Вебхуки чата, доступные пользователю.

    Обычный пользователь видит только свои — так же, как в ``/api/webhooks``.
    """
    stmt = sa.select(Webhook).where(Webhook.chat_id == chat_id)
    if not is_admin(user):
        stmt = stmt.where(Webhook.created_by == user.id)
    return stmt


@router.get("", response_model=PaginatedChatsResponse)
async def list_chats(
    session: SessionDep,
    _: CurrentUser,
    page: int = 1,
    size: int = 20,
    search: str | None = None,
) -> PaginatedChatsResponse:
    """List all chats with pagination. Optional search by title or id."""
    search_query = ChatSearchQuery(search=search)

    # Get total count
    count_stmt = search_query.apply(sa.select(sa.func.count()).select_from(Chat))
    total = await session.scalar(count_stmt) or 0

    # Get paginated chats
    stmt = (
        search_query.apply(sa.select(Chat))
        .order_by(Chat.title, Chat.id)
        .offset((page - 1) * size)
        .limit(size)
    )
    result = await session.scalars(stmt)
    chats = result.all()

    return PaginatedChatsResponse(
        items=[ChatResponse.model_validate(chat) for chat in chats],
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if total > 0 else 0,
    )


@router.get("/{chat_id}", response_model=ChatDetailResponse)
async def get_chat(
    chat_id: str,
    session: SessionDep,
    current_user: CurrentUser,
) -> ChatDetailResponse:
    """Get chat by ID with member and webhook counts."""
    chat_repo = ChatRepository(session)
    chat = await chat_repo.get_or_none(chat_id)

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat not found",
        )

    member_count = await session.scalar(
        sa.select(sa.func.count())
        .select_from(ChatMembership)
        .where(ChatMembership.chat_id == chat_id)
    )
    # Счётчик считает то же, что покажет список: иначе «3» рядом с одной строкой.
    webhook_count = await session.scalar(
        visible_webhooks(chat_id, current_user).with_only_columns(sa.func.count())
    )

    return ChatDetailResponse(
        id=chat.id,
        type=chat.type,
        title=chat.title,
        member_count=member_count or 0,
        webhook_count=webhook_count or 0,
    )


@router.get("/{chat_id}/webhooks", response_model=WebhookListResponse)
async def list_chat_webhooks(
    chat_id: str,
    session: SessionDep,
    current_user: CurrentUser,
) -> WebhookListResponse:
    """Вебхуки, отправляющие в этот чат."""
    chat_repo = ChatRepository(session)
    if not await chat_repo.get_or_none(chat_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat not found",
        )

    stmt = visible_webhooks(chat_id, current_user).order_by(Webhook.created_at.desc())
    webhooks = (await session.scalars(stmt)).all()

    return WebhookListResponse(
        webhooks=[WebhookResponse.model_validate(webhook) for webhook in webhooks],
        total=len(webhooks),
    )


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
