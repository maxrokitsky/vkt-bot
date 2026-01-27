import base64
import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class WebhookFileSchema(BaseModel):
    """Схема для файла в вебхуке."""

    content: str | None = Field(None, description="Base64 encoded file content")
    data_url: str | None = Field(None, description="Data URL with file content")
    filename: str = Field(..., description="File name")
    caption: str | None = Field(None, max_length=4000, description="Подпись к файлу")

    @model_validator(mode="after")
    def validate_content(self):
        if not self.content and not self.data_url:
            raise ValueError("Either content or data_url must be provided")
        if self.content and self.data_url:
            raise ValueError("Cannot provide both content and data_url")
        return self

    def get_file_content(self) -> bytes:
        """Получить содержимое файла в виде bytes."""
        if self.content:
            try:
                return base64.b64decode(self.content)
            except Exception as e:
                raise ValueError(f"Invalid base64 encoding: {str(e)}")
        elif self.data_url:
            try:
                # Парсим data URL: data:[<mediatype>][;base64],<data>
                if not self.data_url.startswith("data:"):
                    raise ValueError("Invalid data URL format")

                # Разделяем заголовок и данные
                header, data = self.data_url.split(",", 1)
                parts = header.split(";")

                # Проверяем base64 кодирование
                if "base64" not in parts:
                    raise ValueError("Data URL must be base64 encoded")

                return base64.b64decode(data)
            except Exception as e:
                raise ValueError(f"Invalid data URL: {str(e)}")
        else:
            raise ValueError("No file content provided")


class WebhookSendRequest(BaseModel):
    """Схема для отправки сообщения через вебхук."""

    text: str | None = Field(None, max_length=4000, description="Текст сообщения")
    file: WebhookFileSchema | None = Field(None, description="Файл для отправки")
    parse_mode: Literal["MarkdownV2", "HTML"] | None = Field(
        None, description="Режим разметки текста"
    )

    @model_validator(mode="after")
    def validate_content(self):
        has_text = bool(self.text)
        has_file = bool(self.file)

        if not (has_text or has_file):
            raise ValueError("Должен быть указан либо text, либо file")

        # Проверяем, что не указано одновременно несколько источников контента
        content_sources = sum([has_text, has_file])
        if content_sources > 1:
            raise ValueError("Нельзя указывать одновременно text и file")

        return self


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
    msg_id: str | None = Field(None, description="ID отправленного сообщения")
    file_id: str | None = Field(
        None, description="ID загруженного файла (если отправлялся файл)"
    )


class WebhookListResponse(BaseModel):
    """Схема ответа со списком вебхуков."""

    webhooks: list[WebhookResponse]
    total: int = Field(..., description="Общее количество вебхуков")


class WebhookRegenerateResponse(BaseModel):
    """Схема ответа при перегенерации API ключа."""

    webhook: WebhookResponse
    api_key: str = Field(..., description="Новый API ключ для доступа к вебхуку")
    message: str = Field(..., description="Сообщение о результате операции")
