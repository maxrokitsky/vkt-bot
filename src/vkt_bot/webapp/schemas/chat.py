from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatResponse(BaseModel):
    id: str
    title: str | None = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedChatsResponse(BaseModel):
    items: list[ChatResponse]
    total: int
    page: int
    size: int
    pages: int


class SendMessageRequest(BaseModel):
    text: str = Field(
        ..., min_length=1, max_length=4096, description="Message text to send"
    )
    parse_mode: Literal["MarkdownV2", "HTML"] | None = Field(
        None, description="Parse mode for message formatting"
    )


class SendMessageResponse(BaseModel):
    success: bool
    message: str
