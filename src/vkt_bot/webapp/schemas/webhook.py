import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class WebhookCreateSchema(BaseModel):
    """Схема для создания вебхука."""

    name: str = Field(..., min_length=1, max_length=100, description="Название вебхука")
    chat_id: str = Field(..., description="ID чата для отправки сообщений")
    webhook_metadata: dict = Field(
        default_factory=dict, description="Дополнительные настройки вебхука"
    )


class WebhookUpdateSchema(BaseModel):
    """Схема для обновления вебхука."""

    name: str | None = Field(
        None, min_length=1, max_length=100, description="Название вебхука"
    )
    is_active: bool | None = Field(None, description="Активен ли вебхук")
    webhook_metadata: dict | None = Field(
        None, description="Дополнительные настройки вебхука"
    )


class WebhookSendRequest(BaseModel):
    """Схема для отправки сообщения через вебхук."""

    text: str = Field(..., min_length=1, max_length=4000, description="Текст сообщения")
    parse_mode: Literal["MarkdownV2", "HTML"] | None = Field(
        None, description="Режим разметки текста"
    )
    inline_keyboard_markup: str | None = Field(
        None, description="JSON-строка с inline клавиатурой"
    )


class WebhookResponse(BaseModel):
    """Схема ответа с информацией о вебхуке."""

    id: str
    name: str
    chat_id: str
    created_by: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    is_active: bool
    webhook_metadata: dict

    model_config = ConfigDict(from_attributes=True)


class WebhookCreateResponse(BaseModel):
    """Схема ответа при создании вебхука."""

    webhook: WebhookResponse
    api_key: str = Field(
        ...,
        description="API ключ для доступа к вебхуку (показывается только один раз!)",
    )
    message: str = Field(..., description="Сообщение о результате операции")


class WebhookSendResponse(BaseModel):
    """Схема ответа при отправке сообщения через вебхук."""

    success: bool = Field(..., description="Успешно ли отправлено сообщение")
    message: str = Field(..., description="Сообщение о результате")
    webhook_id: str = Field(..., description="ID вебхука")
    chat_id: str = Field(..., description="ID чата, в который отправлено сообщение")


class WebhookListResponse(BaseModel):
    """Схема ответа со списком вебхуков."""

    webhooks: list[WebhookResponse]
    total: int = Field(..., description="Общее количество вебхуков")


class WebhookRegenerateResponse(BaseModel):
    """Схема ответа при перегенерации API ключа."""

    webhook: WebhookResponse
    api_key: str = Field(..., description="Новый API ключ для доступа к вебхуку")
    message: str = Field(..., description="Сообщение о результате операции")
