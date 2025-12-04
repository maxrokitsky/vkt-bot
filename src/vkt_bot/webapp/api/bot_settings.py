from fastapi import APIRouter, HTTPException, status

from vkt_bot.core.repositories.bot_settings import BotSettingsRepository
from vkt_bot.core.constants import DEFAULT_START_MESSAGE
from vkt_bot.webapp.dependencies import CurrentAdminUser, SessionDep
from vkt_bot.webapp.schemas.bot_settings import (
    BotSettingsResponse,
    UpdateBotSettingsRequest,
)

router = APIRouter(prefix="/api/bot-settings", tags=["bot-settings"])


@router.get("/{key}", response_model=BotSettingsResponse)
async def get_bot_setting(
    key: str,
    session: SessionDep,
    _: CurrentAdminUser,
) -> BotSettingsResponse:
    """Get bot setting by key. Admin only."""
    repo = BotSettingsRepository(session)
    setting = await repo.get_by_key(key)

    if not setting:
        # Если настройка не найдена и это start_message, возвращаем значение по умолчанию
        if key == "start_message":
            from datetime import datetime, timezone
            return BotSettingsResponse(
                key=key,
                value=DEFAULT_START_MESSAGE,
                description="Приветственное сообщение бота",
                updated_at=datetime.now(timezone.utc),
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Setting with key '{key}' not found",
        )

    return BotSettingsResponse.model_validate(setting)


@router.put("/{key}", response_model=BotSettingsResponse)
async def update_bot_setting(
    key: str,
    request: UpdateBotSettingsRequest,
    session: SessionDep,
    _: CurrentAdminUser,
) -> BotSettingsResponse:
    """Update or create bot setting. Admin only."""
    repo = BotSettingsRepository(session)

    # Если значение пустое и это start_message, восстанавливаем значение по умолчанию
    value = request.value
    if not value.strip() and key == "start_message":
        value = DEFAULT_START_MESSAGE

    setting = await repo.set_value(
        key=key,
        value=value,
        description=request.description,
    )
    await session.commit()
    await session.refresh(setting)

    return BotSettingsResponse.model_validate(setting)


@router.get("", response_model=list[BotSettingsResponse])
async def list_bot_settings(
    session: SessionDep,
    _: CurrentAdminUser,
) -> list[BotSettingsResponse]:
    """List all bot settings. Admin only."""
    repo = BotSettingsRepository(session)
    settings = await repo.list()

    return [BotSettingsResponse.model_validate(setting) for setting in settings]
