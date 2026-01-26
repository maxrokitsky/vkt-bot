import logging
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status

from vkt_bot.app import bot
from vkt_bot.core.repositories.webhook import WebhookRepository
from vkt_bot.webapp.dependencies import SessionDep
from vkt_bot.webapp.schemas.webhook import WebhookSendRequest, WebhookSendResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["public-webhooks"])


@router.post("/{webhook_id}", response_model=WebhookSendResponse)
async def handle_public_webhook(
    webhook_id: str,
    request: WebhookSendRequest,
    session: SessionDep,
    authorization: Annotated[str | None, Header()] = None,
) -> WebhookSendResponse:
    """Универсальный обработчик для публичных вебхуков (для интеграции с n8n)."""
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
            "Public webhook message sent: webhook_id=%s, chat_id=%s, text_length=%d",
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
            "Failed to send public webhook message: webhook_id=%s, chat_id=%s, error=%s",
            webhook.id,
            webhook.chat_id,
            str(e),
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send message: {str(e)}",
        )
