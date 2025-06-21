# ruff: noqa: N815
import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal, Union
from typing_extensions import TypeIs

from pydantic import BaseModel, Field

from vkt_bot.bot_framework.bot.enums import ChatType, EventType


class Chat(BaseModel):
    """Chat."""

    chatId: str
    type: ChatType
    title: str | None = None


class User(BaseModel):
    """User."""

    firstName: str
    lastName: str
    userId: str


class Bot(BaseModel):
    """Bot."""

    firstName: str
    userId: str
    nick: str


class BaseEvent[T](BaseModel):
    """Событие."""

    eventId: int
    payload: T

    @classmethod
    def isinstance[T_Event](cls: type[T_Event], obj: Any) -> TypeIs[T_Event]:  # noqa: ANN401
        """Isinstance."""
        return isinstance(obj, cls)


class FormatPart(BaseModel):
    """FormatPart."""

    length: int
    offset: int


class FormatType(StrEnum):
    """FormatType."""

    MENTION = "mention"
    FORWARD = "forward"


class NewMessagePayload(BaseModel):
    """NewMessagePayload."""

    chat: Chat
    sender: User | Bot = Field(alias="from")
    msgId: str
    text: str | None = None
    timestamp: datetime.datetime
    format: dict[str, list[FormatPart]] = {}


class EditedMessagePayload(NewMessagePayload):
    """EditedMessagePayload."""

    editedTimestamp: datetime.datetime


class NewChatMembersPayload(BaseModel):
    """NewChatMembersPayload."""

    addedBy: User | None = None
    chat: Chat
    newMembers: list[User | Bot]


class NewMessageEvent(BaseEvent[NewMessagePayload]):
    """Новое сообщение."""

    type: Literal[EventType.NEW_MESSAGE]


class EditedMessageEvent(BaseEvent[EditedMessagePayload]):
    """Сообщение был изменено."""

    type: Literal[EventType.EDITED_MESSAGE]


class DeletedMessageEvent(BaseEvent[Any]):
    """Сообщение был изменено."""

    type: Literal[EventType.DELETED_MESSAGE]


class PinnedMessageEvent(BaseEvent[Any]):
    """Сообщение был изменено."""

    type: Literal[EventType.PINNED_MESSAGE]


class UnpinnedMessageEvent(BaseEvent[Any]):
    """Сообщение был изменено."""

    type: Literal[EventType.UNPINNED_MESSAGE]


class NewChatMembersEvent(BaseEvent[NewChatMembersPayload]):
    """Сообщение был изменено."""

    type: Literal[EventType.NEW_CHAT_MEMBERS]


class LeftChatMembersEvent(BaseEvent[Any]):
    """Сообщение был изменено."""

    type: Literal[EventType.LEFT_CHAT_MEMBERS]


class ChangedChatInfoEvent(BaseEvent[Any]):
    """Сообщение был изменено."""

    type: Literal[EventType.CHANGED_CHAT_INFO]


class CallbackQueryEventPayload(BaseModel):
    callbackData: str
    queryId: str
    sender: User = Field(alias="from")
    message: NewMessagePayload


class CallbackQueryEvent(BaseEvent[CallbackQueryEventPayload]):
    """Сообщение был изменено."""

    type: Literal[EventType.CALLBACK_QUERY]


type Event = Annotated[
    Union[  # noqa: UP007
        NewMessageEvent,
        EditedMessageEvent,
        DeletedMessageEvent,
        PinnedMessageEvent,
        UnpinnedMessageEvent,
        NewChatMembersEvent,
        LeftChatMembersEvent,
        ChangedChatInfoEvent,
        CallbackQueryEvent,
    ],
    Field(discriminator="type"),
]


class Response(BaseModel):
    """Ответ."""

    ok: bool


class EventsResponse(Response):
    """Ответ метода /events/get."""

    events: list[Event]


class GetSelfResponse(Response):
    """Ответ метода /self/get."""

    firstName: str
    nick: str
    userId: str


class ChatMember(BaseModel):
    """ChatMember."""

    userId: str
    creator: bool = False
    admin: bool = False


class GetMembersResponse(Response):
    """Ответ метода /chats/members."""

    members: list[ChatMember]
