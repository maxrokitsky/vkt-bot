"""Фильтры ``vkt_dispatcher.filters``."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from vkt_dispatcher.filters import (
    AllFilter,
    AndFilter,
    AnyFilter,
    AudioFilter,
    CallbackDataFilter,
    CallbackDataRegexpFilter,
    CommandFilter,
    FileFilter,
    Filter,
    FilterBase,
    ForwardFilter,
    ImageFilter,
    InvertFilter,
    MentionFilter,
    MessageFilter,
    OrFilter,
    RegexpFilter,
    ReplyFilter,
    SenderFilter,
    StickerFilter,
    URLFilter,
    VideoFilter,
)

from tests.factories import make_event

if TYPE_CHECKING:
    from vkteams_client.types import Event

# ROADMAP 3.1: фильтры обращаются к отсутствующему `event.data`.
BROKEN_BY_MISSING_PARTS = pytest.mark.xfail(
    raises=AttributeError,
    strict=True,
    reason="ROADMAP 3.1: фильтры читают event.data, которого у pydantic-модели нет",
)


class Const(FilterBase):
    """Фильтр-заглушка с фиксированным результатом."""

    def __init__(self, value: bool) -> None:
        super().__init__()
        self.value = value
        self.calls = 0

    def filter(self, event: Event) -> bool:  # noqa: ARG002
        self.calls += 1
        return self.value


TRUE = Const(True)
FALSE = Const(False)


@pytest.fixture
def message() -> Event:
    """Сообщение в групповом чате."""
    return make_event("new_message")


@pytest.fixture
def command() -> Event:
    """Сообщение-команда."""
    return make_event("new_message", text="/help")


@pytest.fixture
def callback() -> Event:
    """Событие callbackQuery."""
    return make_event("callback_query")


class TestComposition:
    """Композиция фильтров операторами."""

    def test_and_operator_builds_and_filter(self, message: Event) -> None:
        composed = Const(True) & Const(True)
        assert isinstance(composed, AndFilter)
        assert composed(message) is True

    @pytest.mark.parametrize(
        ("left", "right", "expected"),
        [
            (True, True, True),
            (True, False, False),
            (False, True, False),
            (False, False, False),
        ],
    )
    def test_and_truth_table(
        self, message: Event, left: bool, right: bool, expected: bool
    ) -> None:
        assert (Const(left) & Const(right))(message) is expected

    @pytest.mark.parametrize(
        ("left", "right", "expected"),
        [
            (True, True, True),
            (True, False, True),
            (False, True, True),
            (False, False, False),
        ],
    )
    def test_or_truth_table(
        self, message: Event, left: bool, right: bool, expected: bool
    ) -> None:
        composed = Const(left) | Const(right)
        assert isinstance(composed, OrFilter)
        assert composed(message) is expected

    def test_invert(self, message: Event) -> None:
        composed = ~Const(True)
        assert isinstance(composed, InvertFilter)
        assert composed(message) is False
        assert (~Const(False))(message) is True

    def test_and_short_circuits(self, message: Event) -> None:
        right = Const(True)
        (Const(False) & right)(message)
        assert right.calls == 0

    def test_or_short_circuits(self, message: Event) -> None:
        right = Const(False)
        (Const(True) & Const(True) | right)(message)
        assert right.calls == 0

    def test_nested_composition(self, message: Event) -> None:
        assert ((Const(True) & Const(False)) | ~Const(False))(message) is True

    def test_call_delegates_to_filter(self, message: Event) -> None:
        const = Const(True)
        assert const(message) == const.filter(message)


class TestIterableFilters:
    """``AllFilter`` и ``AnyFilter``."""

    def test_all_true(self, message: Event) -> None:
        assert AllFilter([Const(True), Const(True)])(message) is True

    def test_all_with_one_false(self, message: Event) -> None:
        assert AllFilter([Const(True), Const(False)])(message) is False

    def test_all_on_empty_is_true(self, message: Event) -> None:
        assert AllFilter([])(message) is True

    def test_any_true(self, message: Event) -> None:
        assert AnyFilter([Const(False), Const(True)])(message) is True

    def test_any_all_false(self, message: Event) -> None:
        assert AnyFilter([Const(False), Const(False)])(message) is False

    def test_any_on_empty_is_false(self, message: Event) -> None:
        assert AnyFilter([])(message) is False


class TestMessageFilter:
    """``Filter.message``."""

    def test_matches_new_message(self, message: Event) -> None:
        assert MessageFilter()(message) is True

    @pytest.mark.parametrize(
        "fixture",
        [
            "edited_message",
            "deleted_message",
            "callback_query",
            "new_chat_members",
            "changed_chat_info",
        ],
    )
    def test_rejects_other_events(self, fixture: str) -> None:
        assert MessageFilter()(make_event(fixture)) is False


class TestCommandFilter:
    """``Filter.command``."""

    @pytest.mark.parametrize("prefix", ["/", ".", "!"])
    def test_accepts_all_prefixes(self, prefix: str) -> None:
        event = make_event("new_message", text=f"{prefix}help")
        assert CommandFilter()(event) is True

    def test_leading_whitespace_is_stripped(self) -> None:
        assert CommandFilter()(make_event("new_message", text="   /help")) is True

    def test_rejects_plain_text(self, message: Event) -> None:
        assert CommandFilter()(message) is False

    def test_rejects_prefix_in_the_middle(self) -> None:
        event = make_event("new_message", text="см. /help")
        assert CommandFilter()(event) is False

    def test_empty_text(self) -> None:
        assert CommandFilter()(make_event("new_message", text="")) is False

    def test_missing_text(self) -> None:
        from tests.factories import raw_event
        from vkteams_client.types import NewMessageEvent

        data = raw_event("new_message")
        del data["payload"]["text"]
        event = NewMessageEvent.model_validate(data)
        assert CommandFilter()(event) is False

    def test_rejects_non_message_events(self, callback: Event) -> None:
        assert CommandFilter()(callback) is False


class TestSenderFilter:
    """``Filter.sender``.

    Фильтр сравнивает ``chatId``, а не ``userId`` отправителя, — в личке это
    одно и то же, в группе нет. Тесты фиксируют текущее поведение.
    """

    def test_matches_private_chat_id(self) -> None:
        event = make_event("new_message_private")
        assert SenderFilter("1234567890")(event) is True

    def test_group_chat_matches_chat_id_not_user_id(self, message: Event) -> None:
        assert SenderFilter("681869378@chat.agent")(message) is True
        assert SenderFilter("1234567890")(message) is False

    def test_rejects_non_message_events(self, callback: Event) -> None:
        assert SenderFilter("1234567890")(callback) is False


class TestRegexpFilter:
    """``Filter.regexp``."""

    def test_matches_string_pattern(self, message: Event) -> None:
        assert RegexpFilter(r"Прив")(message) is True

    def test_accepts_compiled_pattern(self, message: Event) -> None:
        assert RegexpFilter(re.compile(r"Прив"))(message) is True

    def test_searches_anywhere(self) -> None:
        event = make_event("new_message", text="в конце hashtag #dev")
        assert RegexpFilter(r"#(\w+)")(event) is True

    def test_no_match(self, message: Event) -> None:
        assert RegexpFilter(r"^\d+$")(message) is False

    def test_missing_text_is_empty_string(self) -> None:
        from tests.factories import raw_event
        from vkteams_client.types import NewMessageEvent

        data = raw_event("new_message")
        del data["payload"]["text"]
        event = NewMessageEvent.model_validate(data)
        assert RegexpFilter(r".+")(event) is False

    def test_rejects_non_message_events(self, callback: Event) -> None:
        assert RegexpFilter(r".*")(callback) is False


class TestUrlFilter:
    """``Filter.url``."""

    @pytest.mark.parametrize("text", ["не ссылка", "текст https://example.com текст"])
    def test_rejects_without_raising(self, text: str) -> None:
        """Регексп не совпал — до сломанного ``FileFilter`` дело не доходит."""
        assert URLFilter()(make_event("new_message", text=text)) is False

    @BROKEN_BY_MISSING_PARTS
    @pytest.mark.parametrize(
        "text", ["https://example.com", "  http://example.com/a?b=1  "]
    )
    def test_matches_bare_url(self, text: str) -> None:
        assert URLFilter()(make_event("new_message", text=text)) is True


class TestBrokenPartFilters:
    """Фильтры по ``parts``: сейчас падают с ``AttributeError`` (ROADMAP 3.1)."""

    @BROKEN_BY_MISSING_PARTS
    def test_file_filter_matches_file_part(self) -> None:
        assert FileFilter()(make_event("new_message_with_parts")) is True

    @BROKEN_BY_MISSING_PARTS
    def test_file_filter_rejects_plain_message(self, message: Event) -> None:
        assert FileFilter()(message) is False

    @BROKEN_BY_MISSING_PARTS
    def test_image_filter(self) -> None:
        assert ImageFilter()(make_event("new_message_with_parts")) is True

    @BROKEN_BY_MISSING_PARTS
    def test_video_filter(self) -> None:
        assert VideoFilter()(make_event("new_message_with_parts")) is False

    @BROKEN_BY_MISSING_PARTS
    def test_audio_filter(self) -> None:
        assert AudioFilter()(make_event("new_message_with_parts")) is False

    @BROKEN_BY_MISSING_PARTS
    def test_sticker_filter(self, message: Event) -> None:
        assert StickerFilter()(message) is False

    @BROKEN_BY_MISSING_PARTS
    def test_mention_filter_without_user(self) -> None:
        assert MentionFilter()(make_event("new_message_with_parts")) is True

    @BROKEN_BY_MISSING_PARTS
    def test_mention_filter_with_user(self) -> None:
        event = make_event("new_message_with_parts")
        assert MentionFilter("9876543210")(event) is True
        assert MentionFilter("0000000000")(event) is False

    @BROKEN_BY_MISSING_PARTS
    def test_forward_filter(self, message: Event) -> None:
        assert ForwardFilter()(message) is False

    @BROKEN_BY_MISSING_PARTS
    def test_reply_filter(self, message: Event) -> None:
        assert ReplyFilter()(message) is False

    @BROKEN_BY_MISSING_PARTS
    def test_media_shortcut(self) -> None:
        assert Filter.media(make_event("new_message_with_parts")) is True

    @BROKEN_BY_MISSING_PARTS
    def test_data_shortcut(self) -> None:
        assert Filter.data(make_event("new_message_with_parts")) is False

    @BROKEN_BY_MISSING_PARTS
    def test_text_shortcut(self, message: Event) -> None:
        assert Filter.text(message) is True

    @BROKEN_BY_MISSING_PARTS
    def test_callback_data_filter(self, callback: Event) -> None:
        expected = callback.payload.callbackData
        assert CallbackDataFilter(expected)(callback) is True

    @BROKEN_BY_MISSING_PARTS
    def test_callback_data_regexp_filter(self, callback: Event) -> None:
        assert bool(CallbackDataRegexpFilter(r"showcommands")(callback)) is True


class TestFilterShortcuts:
    """Ярлыки в классе ``Filter``."""

    def test_message_and_command_are_instances(self) -> None:
        assert isinstance(Filter.message, MessageFilter)
        assert isinstance(Filter.command, CommandFilter)

    def test_parametrised_shortcuts_are_classes(self) -> None:
        assert Filter.regexp is RegexpFilter
        assert Filter.sender is SenderFilter
        assert Filter.mention is MentionFilter
        assert Filter.callback_data is CallbackDataFilter
        assert Filter.callback_data_regexp is CallbackDataRegexpFilter

    def test_command_and_private_composition(self) -> None:
        composed = Filter.command & Filter.sender("1234567890")
        assert composed(make_event("new_message_private", text="/help")) is True
        assert composed(make_event("new_message", text="/help")) is False
