# ruff: noqa: N815
import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal, Union
from typing_extensions import TypeIs

from pydantic import BaseModel, Field

from .enums import ChatType, EventType, Parts, PayLoadFileType


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

    def __str__(self) -> str:
        return f"{self.eventId} (type: {self.type})"

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


class MentionPayload(BaseModel):
    """Кого упомянули."""

    userId: str
    firstName: str | None = None
    lastName: str | None = None


class FilePayload(BaseModel):
    """Вложенный файл.

    ``type`` есть только у медиа: у обычного документа его нет.
    """

    fileId: str
    type: PayLoadFileType | None = None
    caption: str | None = None
    format: dict[str, list[FormatPart]] = {}


class FileIdPayload(BaseModel):
    """Стикер или голосовое: кроме идентификатора файла, ничего."""

    fileId: str


class QuotedMessage(BaseModel):
    """Сообщение, которое переслали или на которое ответили."""

    sender: User | Bot | None = Field(alias="from", default=None)
    msgId: str | None = None
    text: str | None = None
    timestamp: datetime.datetime | None = None
    format: dict[str, list[FormatPart]] = {}


class QuotedPayload(BaseModel):
    """Обёртка вокруг процитированного сообщения."""

    message: QuotedMessage


class StickerPart(BaseModel):
    """Стикер."""

    type: Literal[Parts.STICKER]
    payload: FileIdPayload


class VoicePart(BaseModel):
    """Голосовое сообщение."""

    type: Literal[Parts.VOICE]
    payload: FileIdPayload


class FilePart(BaseModel):
    """Файл: документ, картинка, видео или аудио."""

    type: Literal[Parts.FILE]
    payload: FilePayload


class MentionPart(BaseModel):
    """Упоминание участника."""

    type: Literal[Parts.MENTION]
    payload: MentionPayload


class ForwardPart(BaseModel):
    """Пересланное сообщение."""

    type: Literal[Parts.FORWARD]
    payload: QuotedPayload


class ReplyPart(BaseModel):
    """Ответ на сообщение."""

    type: Literal[Parts.REPLY]
    payload: QuotedPayload


class UnknownPart(BaseModel):
    """Часть неизвестного типа.

    Нужна как запасной вариант: новый тип части не должен ронять разбор
    всего события. Без неё один незнакомый элемент делал бы сообщение
    нечитаемым целиком — и бот молчал бы, вместо того чтобы ответить на
    остальное.
    """

    type: str
    payload: dict[str, Any] = Field(default_factory=dict)


#: Известные части. Дискриминатор по ``type`` — разбор идёт сразу в нужную
#: модель, без перебора.
type KnownPart = Annotated[
    Union[  # noqa: UP007
        StickerPart,
        VoicePart,
        FilePart,
        MentionPart,
        ForwardPart,
        ReplyPart,
    ],
    Field(discriminator="type"),
]

type MessagePart = KnownPart | UnknownPart


class NewMessagePayload(BaseModel):
    """NewMessagePayload."""

    chat: Chat
    sender: User | Bot = Field(alias="from")
    msgId: str
    text: str | None = None
    timestamp: datetime.datetime
    format: dict[str, list[FormatPart]] = {}
    #: Вложения, упоминания, пересылки и ответы. В ``text`` их нет:
    #: вложение приходит отдельной частью, а упоминание — и частью, и
    #: разметкой ``format`` одновременно.
    parts: list[MessagePart] = Field(default_factory=list)

    def parts_of[T](self, kind: Parts, model: type[T]) -> list[T]:
        """Части одного типа.

        ``model`` нужен не для проверки, а для типизации: у каждого типа
        своя модель payload, и без него вызывающий получал бы объединение.
        """
        return [
            part.payload  # type: ignore[misc]
            for part in self.parts
            if part.type == kind and isinstance(part.payload, model)
        ]

    @property
    def mentions(self) -> list[MentionPayload]:
        """Кого упомянули в сообщении.

        Единственный источник, где у упоминания есть ``userId``: разметка
        ``format.mention`` несёт только смещение и длину.
        """
        return self.parts_of(Parts.MENTION, MentionPayload)

    @property
    def files(self) -> list[FilePayload]:
        """Вложенные файлы."""
        return self.parts_of(Parts.FILE, FilePayload)


class EditedMessagePayload(NewMessagePayload):
    """EditedMessagePayload."""

    editedTimestamp: datetime.datetime


class NewChatMembersPayload(BaseModel):
    """NewChatMembersPayload."""

    addedBy: User | None = None
    chat: Chat
    newMembers: list[User | Bot] = Field(default_factory=list)


class LeftChatMembersPayload(BaseModel):
    """LeftChatMembersPayload."""

    removedBy: User | None = None
    chat: Chat
    leftMembers: list[User | Bot] = Field(default_factory=list)


class ChangedChatInfoPayload(BaseModel):
    """ChangedChatInfoPayload.

    Событие ``changedChatInfo`` в официальной документации отсутствует,
    поля восстановлены по реальным ответам API — поэтому все, кроме
    ``chat``, необязательные.
    """

    chat: Chat
    title: str | None = None


class NewMessageEvent(BaseEvent[NewMessagePayload]):
    """Новое сообщение."""

    type: Literal[EventType.NEW_MESSAGE]

    def __str__(self) -> str:
        # msgId нужен, чтобы по логу можно было разобрать проблему с
        # конкретным сообщением: пересылку, правку, удаление.
        return (
            f"{self.eventId} (type: {self.type}, "
            f"chatId: {self.payload.chat.chatId}, msgId: {self.payload.msgId})"
        )


class EditedMessageEvent(BaseEvent[EditedMessagePayload]):
    """Сообщение был изменено."""

    type: Literal[EventType.EDITED_MESSAGE]


class DeletedMessagePayload(BaseModel):
    """DeletedMessagePayload.

    Отправителя в событии нет: удалить сообщение может и не автор.
    """

    chat: Chat
    msgId: str
    timestamp: datetime.datetime


class DeletedMessageEvent(BaseEvent[DeletedMessagePayload]):
    """Сообщение удалено."""

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


class LeftChatMembersEvent(BaseEvent[LeftChatMembersPayload]):
    """Участники покинули чат."""

    type: Literal[EventType.LEFT_CHAT_MEMBERS]


class ChangedChatInfoEvent(BaseEvent[ChangedChatInfoPayload]):
    """Информация о чате изменилась."""

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
    #: Причина отказа: приходит вместе с ``ok: false``.
    description: str | None = None


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


class MsgResponse(Response):
    """Ответ метода с msgId.

    При ``ok: false`` идентификатора в ответе нет.
    """

    msgId: str | None = None


class MsgLoadFileResponse(Response):
    """Ответ метода /messages/sendFile (POST)."""

    fileId: str
    msgId: str


class ThreadAddResponse(Response):
    """Ответ метода /threads/add.

    При ``ok: false`` идентификатора в ответе нет.
    """

    threadId: str | None = None


class UserState(BaseModel):
    """Активность подписчика обсуждения."""

    lastseen: int | None = None


class Subscriber(BaseModel):
    """Подписчик обсуждения."""

    sn: str
    userState: UserState | None = None


class ThreadSubscribersResponse(Response):
    """Ответ метода /threads/subscribers/get."""

    subscribers: list[Subscriber] = Field(default_factory=list)
    cursor: str | None = None
