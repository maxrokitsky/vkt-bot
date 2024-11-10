from enum import Enum, StrEnum, unique


@unique
class EventType(StrEnum):
    """Тип события."""

    NEW_MESSAGE = 'newMessage'
    EDITED_MESSAGE = 'editedMessage'
    NEW_CHAT_MEMBERS = 'newChatMembers'

    DELETED_MESSAGE = 'deletedMessage'
    PINNED_MESSAGE = 'pinnedMessage'
    UNPINNED_MESSAGE = 'unpinnedMessage'
    LEFT_CHAT_MEMBERS = 'leftChatMembers'
    CHANGED_CHAT_INFO = 'changedChatInfo'
    CALLBACK_QUERY = 'callbackQuery'


@unique
class ImageType(StrEnum):
    """ImageType."""

    REGULAR = "0"
    SNAP = "1"
    STICKER = "2"
    RESERVED_3 = "3"
    IMAGE_ANIMATED = "4"
    STICKER_ANIMATED = "5"
    RESERVED_6 = "6"
    RESERVED_7 = "7"


@unique
class VideoType(StrEnum):
    """VideoType."""

    REGULAR = "8"
    SNAP = "9"
    PTS = "A"
    PTS_B = "B"
    RESERVED_C = "C"
    STICKER = "D"
    RESERVED_E = "E"
    RESERVED_F = "F"


@unique
class AudioType(StrEnum):
    """AudioType."""

    REGULAR = "G"
    SNAP = "H"
    PTT = "I"
    PTT_J = "J"
    RESERVED_K = "K"
    RESERVED_L = "L"
    RESERVED_M = "M"
    RESERVED_N = "N"


@unique
class Parts(StrEnum):
    """Parts."""

    FILE = "file"
    STICKER = "sticker"
    MENTION = "mention"
    VOICE = "voice"
    FORWARD = "forward"
    REPLY = "reply"


@unique
class PayLoadFileType(StrEnum):
    """PayLoadFileType."""

    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"


@unique
class ChatType(Enum):
    """ChatType."""

    PRIVATE = "private"
    GROUP = "group"
    CHANNEL = "channel"


@unique
class ParseMode(StrEnum):
    """ParseMode."""

    MARKDOWNV2 = "MarkdownV2"
    HTML = "HTML"


@unique
class StyleType(StrEnum):
    """StyleType."""

    BOLD = "bold"
    ITALIC = "italic"
    UNDERLINE = "underline"
    STRIKETHROUGH = "strikethrough"
    LINK = "link"
    MENTION = "mention"
    INLINE_CODE = "inline_code"
    PRE = "pre"
    ORDERED_LIST = "ordered_list"
    UNORDERED_LIST = "unordered_list"
    QUOTE = "quote"
