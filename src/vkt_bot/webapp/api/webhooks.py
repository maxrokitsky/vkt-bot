import logging
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status

from vkt_bot.app import bot
from vkt_bot.core.repositories.chat import ChatRepository
from vkt_bot.core.repositories.webhook import WebhookRepository
from vkt_bot.webapp.dependencies import CurrentUser, SessionDep
from vkt_bot.webapp.schemas.webhook import (
    WebhookCreateResponse,
    WebhookCreateSchema,
    WebhookListResponse,
    WebhookRegenerateResponse,
    WebhookResponse,
    WebhookSendRequest,
    WebhookSendResponse,
    WebhookUpdateSchema,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.get("", response_model=WebhookListResponse)
async def list_webhooks(
    session: SessionDep,
    current_user: CurrentUser,
) -> WebhookListResponse:
    """Получить список вебхуков пользователя."""
    webhook_repo = WebhookRepository(session)
    webhooks = await webhook_repo.list_by_creator(current_user.id)

    return WebhookListResponse(
        webhooks=[WebhookResponse.model_validate(webhook) for webhook in webhooks],
        total=len(webhooks),
    )


@router.post("", response_model=WebhookCreateResponse)
async def create_webhook(
    data: WebhookCreateSchema,
    session: SessionDep,
    current_user: CurrentUser,
) -> WebhookCreateResponse:
    """Создать новый вебхук."""
    # Проверка, что пользователь имеет доступ к чату
    chat_repo = ChatRepository(session)
    chat = await chat_repo.get_or_none(data.chat_id)
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat not found",
        )

    # Создание вебхука
    webhook_repo = WebhookRepository(session)
    webhook, api_key = await webhook_repo.create_with_api_key(data, current_user.id)

    logger.info(
        "Webhook created: id=%s, name=%s, chat_id=%s, created_by=%s",
        webhook.id,
        webhook.name,
        webhook.chat_id,
        webhook.created_by,
    )

    return WebhookCreateResponse(
        webhook=WebhookResponse.model_validate(webhook),
        api_key=api_key,
        message="Webhook created successfully. Save this API key - it won't be shown again.",
    )


@router.get("/{webhook_id}", response_model=WebhookResponse)
async def get_webhook(
    webhook_id: str,
    session: SessionDep,
    current_user: CurrentUser,
) -> WebhookResponse:
    """Получить информацию о вебхуке."""
    webhook_repo = WebhookRepository(session)
    webhook = await webhook_repo.get_or_none(webhook_id)

    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found",
        )

    # Проверка, что пользователь является создателем вебхука
    if webhook.created_by != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to access this webhook",
        )

    return WebhookResponse.model_validate(webhook)


@router.put("/{webhook_id}", response_model=WebhookResponse)
async def update_webhook(
    webhook_id: str,
    data: WebhookUpdateSchema,
    session: SessionDep,
    current_user: CurrentUser,
) -> WebhookResponse:
    """Обновить вебхук."""
    webhook_repo = WebhookRepository(session)
    webhook = await webhook_repo.get_or_none(webhook_id)

    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found",
        )

    # Проверка, что пользователь является создателем вебхука
    if webhook.created_by != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to update this webhook",
        )

    # Обновление вебхука
    updated_webhook = await webhook_repo.update(webhook_id, data)

    logger.info(
        "Webhook updated: id=%s, name=%s, is_active=%s",
        updated_webhook.id,
        updated_webhook.name,
        updated_webhook.is_active,
    )

    return WebhookResponse.model_validate(updated_webhook)


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    webhook_id: str,
    session: SessionDep,
    current_user: CurrentUser,
) -> None:
    """Удалить вебхук."""
    webhook_repo = WebhookRepository(session)
    webhook = await webhook_repo.get_or_none(webhook_id)

    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found",
        )

    # Проверка, что пользователь является создателем вебхука
    if webhook.created_by != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to delete this webhook",
        )

    # Удаление вебхука
    await webhook_repo.delete(webhook_id)

    logger.info("Webhook deleted: id=%s, name=%s", webhook.id, webhook.name)


@router.post("/{webhook_id}/regenerate", response_model=WebhookRegenerateResponse)
async def regenerate_webhook_api_key(
    webhook_id: str,
    session: SessionDep,
    current_user: CurrentUser,
) -> WebhookRegenerateResponse:
    """Перегенерировать API ключ для вебхука."""
    webhook_repo = WebhookRepository(session)
    webhook = await webhook_repo.get_or_none(webhook_id)

    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found",
        )

    # Проверка, что пользователь является создателем вебхука
    if webhook.created_by != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to regenerate API key for this webhook",
        )

    # Перегенерация API ключа
    updated_webhook, new_api_key = await webhook_repo.regenerate_api_key(webhook_id)

    logger.info(
        "Webhook API key regenerated: id=%s, name=%s",
        updated_webhook.id,
        updated_webhook.name,
    )

    return WebhookRegenerateResponse(
        webhook=WebhookResponse.model_validate(updated_webhook),
        api_key=new_api_key,
        message="API key regenerated successfully. Save this new API key - it won't be shown again.",
    )


@router.post("/{webhook_id}/send", response_model=WebhookSendResponse)
async def handle_webhook(
    webhook_id: str,
    request: WebhookSendRequest,
    session: SessionDep,
    authorization: Annotated[str | None, Header()] = None,
) -> WebhookSendResponse:
    """Универсальный обработчик для всех вебхуков."""
    # 1. Проверка API ключа
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header. Use 'Bearer <api_key>' format.",
        )

    api_key = authorization[7:]  # Remove "Bearer " prefix

    # 2. Поиск вебхука в БД
    webhook_repo = WebhookRepository(session)
    webhook = await webhook_repo.get_by_id_and_api_key(webhook_id, api_key)

    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found or invalid API key",
        )

    if not webhook.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Webhook is inactive",
        )

    # 3. Проверка rate limiting
    if not await webhook_repo.check_rate_limit(webhook.id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
        )

    # 4. Отправка сообщения
    try:
        parse_mode = request.parse_mode or webhook.webhook_metadata.get(
            "default_parse_mode"
        )

        await bot.send_text(
            chat_id=webhook.chat_id,
            text=request.text,
            parse_mode=parse_mode,
            inline_keyboard_markup=request.inline_keyboard_markup,
        )

        # 5. Логирование успешной отправки
        await webhook_repo.log_webhook_call(
            webhook_id=webhook.id,
            success=True,
            request_data=request.model_dump(),
            response_data={"status": "sent"},
        )

        logger.info(
            "Webhook message sent: webhook_id=%s, chat_id=%s, text_length=%d",
            webhook.id,
            webhook.chat_id,
            len(request.text),
        )

        return WebhookSendResponse(
            success=True,
            message="Message sent successfully",
            webhook_id=webhook.id,
            chat_id=webhook.chat_id,
        )

    except Exception as e:
        # Логирование ошибки
        await webhook_repo.log_webhook_call(
            webhook_id=webhook.id,
            success=False,
            request_data=request.model_dump(),
            response_data={"error": str(e)},
        )

        logger.error(
            "Failed to send webhook message: webhook_id=%s, chat_id=%s, error=%s",
            webhook.id,
            webhook.chat_id,
            str(e),
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send message: {str(e)}",
        )
