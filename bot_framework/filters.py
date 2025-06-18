from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import TYPE_CHECKING, Self, cast

from bot_framework.bot.types import NewMessageEvent

from .bot.enums import Parts, PayLoadFileType

if TYPE_CHECKING:
    from .bot.types import Event


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


class FileFilter(MessageFilter):
    """FileFilter."""

    def filter(self, event: Event) -> bool:
        return (
            super().filter(event)
            and "parts" in event.data
            and any(p["type"] == Parts.FILE.value for p in event.data["parts"])
        )


class ImageFilter(FileFilter):
    """ImageFilter."""

    def filter(self, event: Event) -> bool:
        return super().filter(event) and any(
            p["payload"]["type"] == PayLoadFileType.IMAGE.value
            for p in event.data["parts"]
            if "type" in p["payload"]
        )


class VideoFilter(FileFilter):
    """VideoFilter."""

    def filter(self, event: Event) -> bool:
        return super().filter(event) and any(
            p["payload"]["type"] == PayLoadFileType.VIDEO.value
            for p in event.data["parts"]
            if "type" in p["payload"]
        )


class AudioFilter(FileFilter):
    """AudioFilter."""

    def filter(self, event: Event) -> bool:
        return super().filter(event) and any(
            p["payload"]["type"] == PayLoadFileType.AUDIO.value
            for p in event.data["parts"]
            if "type" in p["payload"]
        )


class StickerFilter(MessageFilter):
    """StickerFilter."""

    def filter(self, event: Event) -> bool:
        return (
            super().filter(event)
            and "parts" in event.data
            and any(p["type"] == Parts.STICKER.value for p in event.data["parts"])
        )


class MentionFilter(MessageFilter):
    """MentionFilter."""

    user_id: str | None

    def __init__(self, user_id: str | None = None) -> None:
        super().__init__()

        self.user_id = user_id

    def filter(self, event: Event) -> bool:
        return (
            super().filter(event)
            and "parts" in event.data
            and any(
                p["type"] == Parts.MENTION.value
                and (p["payload"]["userId"] == self.user_id if self.user_id else True)
                for p in event.data["parts"]
            )
        )


class ForwardFilter(MessageFilter):
    """ForwardFilter."""

    def filter(self, event: Event) -> bool:
        return "parts" in event.data and any(
            p["type"] == Parts.FORWARD.value for p in event.data["parts"]
        )


class ReplyFilter(MessageFilter):
    """ReplyFilter."""

    def filter(self, event: Event) -> bool:
        return (
            super().filter(event)
            and "parts" in event.data
            and any(p["type"] == Parts.REPLY.value for p in event.data["parts"])
        )


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


class CallbackDataFilter(FilterBase):
    """CallbackDataFilter."""

    def __init__(self, callback_data) -> None:
        super().__init__()

        self.callback_data = callback_data

    def filter(self, event: Event) -> bool:
        return (
            "callbackData" in event.data
            and event.data["callbackData"] == self.callback_data
        )


class CallbackDataRegexpFilter(FilterBase):
    """CallbackDataRegexpFilter."""

    def __init__(self, pattern) -> None:
        super().__init__()

        self.pattern = re.compile(pattern)

    def filter(self, event: Event) -> bool:
        return "callbackData" in event.data and self.pattern.search(
            event.data["callbackData"]
        )


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
    url = URLFilter()
    text = message & ~(command | sticker | file | url)
    regexp = RegexpFilter
    mention = MentionFilter
    forward = ForwardFilter()
    reply = ReplyFilter()
    sender = SenderFilter
    callback_data = CallbackDataFilter
    callback_data_regexp = CallbackDataRegexpFilter
