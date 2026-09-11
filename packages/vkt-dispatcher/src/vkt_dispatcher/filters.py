from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, ClassVar, Self, cast

from vkteams_client.types import CallbackQueryEvent, NewMessageEvent

from vkteams_client.enums import Parts, PayLoadFileType

if TYPE_CHECKING:
    from vkteams_client.types import Event, NewMessagePayload


class FilterBase(ABC):
    """FilterBase."""

    def __init__(self) -> None:
        super().__init__()

    def __call__(self, event: Event) -> bool:
        return self.filter(event)

    def __and__[T_RightFilter: FilterBase](
        self, other: T_RightFilter
    ) -> AndFilter[Self, T_RightFilter]:
        return AndFilter(self, other)

    def __or__[T_RightFilter: FilterBase](
        self, other: T_RightFilter
    ) -> OrFilter[Self, T_RightFilter]:
        return OrFilter(self, other)

    def __invert__(self) -> InvertFilter[Self]:
        return InvertFilter(self)

    @abstractmethod
    def filter(self, event: Event) -> bool:
        pass


class CompositeFilter[T_LeftFilter: FilterBase, T_RightFilter: FilterBase](FilterBase):
    """CompositeFilter."""

    filter_1: T_LeftFilter
    filter_2: T_RightFilter

    def __init__(self, filter_1: T_LeftFilter, filter_2: T_RightFilter) -> None:
        super().__init__()

        self.filter_1 = filter_1
        self.filter_2 = filter_2


class AndFilter[T_LeftFilter: FilterBase, T_RightFilter: FilterBase](
    CompositeFilter[T_LeftFilter, T_RightFilter]
):
    """AndFilter."""

    def filter(self, event: Event) -> bool:
        return self.filter_1(event) and self.filter_2(event)


class OrFilter[T_LeftFilter: FilterBase, T_RightFilter: FilterBase](
    CompositeFilter[T_LeftFilter, T_RightFilter]
):
    """OrFilter."""

    def filter(self, event: Event) -> bool:
        return self.filter_1(event) or self.filter_2(event)


class IterableFilter[T_FilterBase: FilterBase](FilterBase):
    """IterableFilter."""

    iterable: Iterable[T_FilterBase]

    def __init__(self, iterable: Iterable[T_FilterBase]) -> None:
        super().__init__()

        self.iterable = iterable


class AllFilter[T_FilterBase: FilterBase](IterableFilter[T_FilterBase]):
    """AllFilter."""

    def filter(self, event: Event) -> bool:
        return all(f(event) for f in self.iterable)


class AnyFilter[T_FilterBase: FilterBase](IterableFilter[T_FilterBase]):
    """AnyFilter."""

    def filter(self, event: Event) -> bool:
        return any(f(event) for f in self.iterable)


class InvertFilter[T_FilterBase: FilterBase](FilterBase):
    """InvertFilter."""

    filter_: T_FilterBase

    def __init__(self, filter_: T_FilterBase) -> None:
        super().__init__()

        self.filter_ = filter_

    def filter(self, event: Event) -> bool:
        return not self.filter_(event)


class MessageFilter(FilterBase):
    """MessageFilter."""

    def filter(self, event: Event) -> bool:
        return NewMessageEvent.isinstance(event)


class CommandFilter(MessageFilter):
    """CommandFilter."""

    COMMAND_PREFIXES = ("/", ".", "!")

    def filter(self, event: Event) -> bool:
        if not super().filter(event):
            return False

        event = cast(NewMessageEvent, event)
        return super().filter(event) and any(
            event.payload.text and event.payload.text.strip().startswith(p)
            for p in self.COMMAND_PREFIXES
        )


class SenderFilter(MessageFilter):
    """SenderFilter."""

    user_id: str

    def __init__(self, user_id: str) -> None:
        super().__init__()

        self.user_id = user_id

    def filter(self, event: Event) -> bool:
        """Filter."""
        return super().filter(event) and event.payload.chat.chatId == self.user_id


class RegexpFilter(MessageFilter):
    """RegexpFilter."""

    pattern: re.Pattern[str]

    def __init__(self, pattern: str | re.Pattern[str]) -> None:
        super().__init__()

        self.pattern = re.compile(pattern) if isinstance(pattern, str) else pattern

    def filter(self, event: Event) -> bool:
        if not isinstance(event, NewMessageEvent):
            return False
        return super().filter(event) and bool(
            self.pattern.search(event.payload.text or "")
        )


def message_payload(event: Event) -> NewMessagePayload | None:
    """Payload сообщения или ``None``, если событие другого типа.

    Фильтры по вложениям спрашивают ``parts``, а они есть только у
    сообщения. Раньше здесь читалось ``event.data`` — словарь, которого у
    pydantic-модели нет и никогда не было (ROADMAP 3.1).
    """
    if isinstance(event, NewMessageEvent):
        return event.payload
    return None


class PartsFilter(MessageFilter):
    """Основа фильтров по частям сообщения."""

    def parts(self, event: Event) -> list[Any]:
        payload = message_payload(event)
        return payload.parts if payload else []

    def has(self, event: Event, kind: Parts) -> bool:
        """Есть ли в сообщении часть такого типа."""
        return any(part.type == kind for part in self.parts(event))


class FileFilter(PartsFilter):
    """FileFilter."""

    def filter(self, event: Event) -> bool:
        return super().filter(event) and self.has(event, Parts.FILE)


class MediaFilter(FileFilter):
    """Файл конкретного вида: картинка, видео или аудио.

    ``type`` у части есть только у медиа — у обычного документа его нет.
    """

    media_type: ClassVar[PayLoadFileType]

    def filter(self, event: Event) -> bool:
        payload = message_payload(event)
        if not super().filter(event) or payload is None:
            return False
        return any(file.type is self.media_type for file in payload.files)


class ImageFilter(MediaFilter):
    """ImageFilter."""

    media_type: ClassVar[PayLoadFileType] = PayLoadFileType.IMAGE


class VideoFilter(MediaFilter):
    """VideoFilter."""

    media_type: ClassVar[PayLoadFileType] = PayLoadFileType.VIDEO


class AudioFilter(MediaFilter):
    """AudioFilter."""

    media_type: ClassVar[PayLoadFileType] = PayLoadFileType.AUDIO


class StickerFilter(PartsFilter):
    """StickerFilter."""

    def filter(self, event: Event) -> bool:
        return super().filter(event) and self.has(event, Parts.STICKER)


class VoiceFilter(PartsFilter):
    """VoiceFilter."""

    def filter(self, event: Event) -> bool:
        return super().filter(event) and self.has(event, Parts.VOICE)


class MentionFilter(PartsFilter):
    """Упоминание участника.

    Без ``user_id`` — любое упоминание, с ним — упоминание конкретного
    человека. ``userId`` есть только здесь: разметка ``format.mention``
    несёт лишь смещение и длину.
    """

    user_id: str | None

    def __init__(self, user_id: str | None = None) -> None:
        super().__init__()

        self.user_id = user_id

    def filter(self, event: Event) -> bool:
        payload = message_payload(event)
        if not super().filter(event) or payload is None:
            return False
        if self.user_id is None:
            return bool(payload.mentions)
        return any(mention.userId == self.user_id for mention in payload.mentions)


class ForwardFilter(PartsFilter):
    """ForwardFilter."""

    def filter(self, event: Event) -> bool:
        return super().filter(event) and self.has(event, Parts.FORWARD)


class ReplyFilter(PartsFilter):
    """ReplyFilter."""

    def filter(self, event: Event) -> bool:
        return super().filter(event) and self.has(event, Parts.REPLY)


class URLFilter(RegexpFilter):
    """URLFilter."""

    REGEXP = re.compile(r"^\s*https?://\S+\s*$", re.IGNORECASE)

    __FILTER = InvertFilter(
        FileFilter()
    )  # Files are also URLs, but we need to skip it.

    def __init__(self) -> None:
        super().__init__(self.REGEXP)

    def filter(self, event: Event) -> bool:
        return super().filter(event) and self.__FILTER(event)


def callback_data(event: Event) -> str | None:
    """Данные нажатой кнопки или ``None``, если событие другое."""
    if isinstance(event, CallbackQueryEvent):
        return event.payload.callbackData
    return None


class CallbackDataFilter(FilterBase):
    """CallbackDataFilter."""

    def __init__(self, callback_data: str) -> None:
        super().__init__()

        self.callback_data = callback_data

    def filter(self, event: Event) -> bool:
        return callback_data(event) == self.callback_data


class CallbackDataRegexpFilter(FilterBase):
    """CallbackDataRegexpFilter."""

    def __init__(self, pattern: str | re.Pattern[str]) -> None:
        super().__init__()

        self.pattern = re.compile(pattern) if isinstance(pattern, str) else pattern

    def filter(self, event: Event) -> bool:
        data = callback_data(event)
        # Именно bool: фильтр обязан возвращать булево, а ``search``
        # отдаёт объект совпадения.
        return bool(data and self.pattern.search(data))


class Filter:
    """Filter."""

    message = MessageFilter()
    command = CommandFilter()
    file = FileFilter()
    image = ImageFilter()
    video = VideoFilter()
    audio = AudioFilter()
    media = image | video | audio
    data = file & ~media
    sticker = StickerFilter()
    voice = VoiceFilter()
    url = URLFilter()
    text = message & ~(command | sticker | file | url)
    regexp = RegexpFilter
    mention = MentionFilter
    forward = ForwardFilter()
    reply = ReplyFilter()
    sender = SenderFilter
    callback_data = CallbackDataFilter
    callback_data_regexp = CallbackDataRegexpFilter
