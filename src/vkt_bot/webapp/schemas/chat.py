from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from vkteams_client.enums import ChatType


class ChatResponse(BaseModel):
    id: str
    type: ChatType
    title: str | None = None
    about: str | None
    rules: str | None
    #: ``None`` — про чат ещё не спрашивали ``chats/getInfo``; «закрытый»
    #: и «неизвестно» на экране выглядят по-разному.
    public: bool | None
    join_moderation: bool | None

    model_config = ConfigDict(from_attributes=True)


class ChatDetailResponse(ChatResponse):
    """Чат на своей странице — со счётчиками для подписей разделов."""

    member_count: int
    webhook_count: int
    #: Ссылка-приглашение: по ней заходят в чат без спроса, поэтому её
    #: видят только те, кто в чате уже состоит, и администраторы. В
    #: списке чатов её нет вовсе: он отдаёт все чаты бота подряд,
    #: включая те, где спрашивающего нет.
    invite_link: str | None


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
