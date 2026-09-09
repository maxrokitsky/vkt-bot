"""Парсинг ответа ``/events/get``."""

from __future__ import annotations

import datetime
import json
from typing import TYPE_CHECKING

import pytest
from vkteams_client.enums import ChatType, EventType
from vkteams_client.types import (
    Bot,
    CallbackQueryEvent,
    ChangedChatInfoEvent,
    DeletedMessageEvent,
    EditedMessageEvent,
    EventsResponse,
    LeftChatMembersEvent,
    NewChatMembersEvent,
    NewMessageEvent,
    PinnedMessageEvent,
    UnpinnedMessageEvent,
    User,
)

from tests.client.conftest import query_of, url_for
from tests.factories import ALL_EVENT_FIXTURES, events_response, make_event, raw_event

if TYPE_CHECKING:
    from aioresponses import aioresponses
    from vkteams_client import VKTeams

EVENT_CLASSES = {
    "new_message": NewMessageEvent,
    "edited_message": EditedMessageEvent,
    "deleted_message": DeletedMessageEvent,
    "pinned_message": PinnedMessageEvent,
    "unpinned_message": UnpinnedMessageEvent,
    "new_chat_members": NewChatMembersEvent,
    "left_chat_members": LeftChatMembersEvent,
    "changed_chat_info": ChangedChatInfoEvent,
    "callback_query": CallbackQueryEvent,
}


class TestDiscriminator:
    """Дискриминатор ``type`` выбирает правильный класс события."""

    @pytest.mark.parametrize(("fixture", "expected"), EVENT_CLASSES.items())
    def test_type_resolves_to_class(self, fixture: str, expected: type) -> None:
        event = make_event(fixture)
        assert isinstance(event, expected)

    @pytest.mark.parametrize("fixture", ALL_EVENT_FIXTURES)
    def test_every_fixture_parses(self, fixture: str) -> None:
        event = make_event(fixture)
        assert event.eventId == raw_event(fixture)["eventId"]

    def test_all_nine_event_types_covered(self) -> None:
        assert set(EVENT_CLASSES) == {
            name for name in EVENT_CLASSES if name in ALL_EVENT_FIXTURES
        }
        assert len(EVENT_CLASSES) == len(EventType)

    def test_unknown_type_is_rejected(self) -> None:
        from pydantic import ValidationError

        data = raw_event("new_message")
        data["type"] = "somethingNew"
        with pytest.raises(ValidationError):
            EventsResponse.model_validate({"ok": True, "events": [data]})


class TestNewMessagePayload:
    """Полезная нагрузка ``newMessage``."""

    def test_sender_is_read_from_alias_from(self) -> None:
        event = make_event("new_message")
        assert isinstance(event.payload.sender, User)
        assert event.payload.sender.userId == "1234567890"
        assert event.payload.sender.firstName == "Иван"

    def test_bot_sender_parses_as_bot(self) -> None:
        event = make_event("new_message_from_bot")
        assert isinstance(event.payload.sender, Bot)
        assert event.payload.sender.nick == "test_bot"

    def test_sender_field_name_is_not_accepted(self) -> None:
        """Модель принимает только ``from``: ``sender`` не альтернативное имя."""
        from pydantic import ValidationError

        data = raw_event("new_message")
        data["payload"]["sender"] = data["payload"].pop("from")
        with pytest.raises(ValidationError):
            NewMessageEvent.model_validate(data)

    def test_timestamp_becomes_datetime(self) -> None:
        event = make_event("new_message")
        assert isinstance(event.payload.timestamp, datetime.datetime)
        assert event.payload.timestamp == datetime.datetime.fromtimestamp(
            raw_event("new_message")["payload"]["timestamp"], tz=datetime.UTC
        )

    def test_chat_type_becomes_enum(self) -> None:
        assert make_event("new_message").payload.chat.type is ChatType.GROUP
        assert make_event("new_message_private").payload.chat.type is ChatType.PRIVATE

    def test_text_is_optional(self) -> None:
        data = raw_event("new_message")
        del data["payload"]["text"]
        assert NewMessageEvent.model_validate(data).payload.text is None

    def test_format_defaults_to_empty_dict(self) -> None:
        assert make_event("new_message").payload.format == {}

    def test_format_parts_are_parsed(self) -> None:
        payload = make_event("new_message_with_format").payload
        assert set(payload.format) == {"bold", "italic"}
        bold = payload.format["bold"][0]
        assert (bold.offset, bold.length) == (0, 6)

    def test_parts_are_dropped(self) -> None:
        """Известный дефект: вложения и упоминания теряются при парсинге.

        ``NewMessagePayload`` не описывает поле ``parts`` — см. ROADMAP 3.1.
        Тест фиксирует текущее поведение, чтобы падение было замечено, когда
        поле появится.
        """
        payload = make_event("new_message_with_parts").payload
        assert not hasattr(payload, "parts")
        assert payload.model_extra in (None, {})


class TestOtherPayloads:
    """Остальные события."""

    def test_edited_message_has_edited_timestamp(self) -> None:
        payload = make_event("edited_message").payload
        assert payload.editedTimestamp > payload.timestamp

    def test_new_chat_members(self) -> None:
        payload = make_event("new_chat_members").payload
        assert [m.userId for m in payload.newMembers] == ["9876543210"]
        assert payload.addedBy is not None
        assert payload.addedBy.userId == "1234567890"

    def test_new_chat_members_added_by_is_optional(self) -> None:
        data = raw_event("new_chat_members")
        del data["payload"]["addedBy"]
        assert NewChatMembersEvent.model_validate(data).payload.addedBy is None

    def test_callback_query(self) -> None:
        payload = make_event("callback_query").payload
        assert payload.queryId == "SVR:123456"
        assert payload.sender.userId == "1234567890"
        assert payload.message.chat.chatId == "681869378@chat.agent"
        assert json.loads(payload.callbackData)["command"] == "start__showcommands"

    @pytest.mark.parametrize(
        "fixture",
        [
            "deleted_message",
            "pinned_message",
            "unpinned_message",
            "left_chat_members",
            "changed_chat_info",
        ],
    )
    def test_untyped_payloads_stay_dicts(self, fixture: str) -> None:
        """У четырёх событий ``payload: Any`` — см. ROADMAP 3.5."""
        event = make_event(fixture)
        assert isinstance(event.payload, dict)
        assert event.payload == raw_event(fixture)["payload"]


class TestEventStr:
    """``__str__`` события."""

    def test_new_message_str_includes_chat(self) -> None:
        event = make_event("new_message")
        assert str(event) == "1 (type: newMessage, chatId: 681869378@chat.agent)"

    def test_base_event_str(self) -> None:
        event = make_event("deleted_message")
        assert str(event) == "7 (type: deletedMessage)"


class TestIsinstance:
    """Хелпер ``BaseEvent.isinstance``."""

    def test_true_for_own_class(self) -> None:
        assert NewMessageEvent.isinstance(make_event("new_message"))

    def test_false_for_other_class(self) -> None:
        assert not NewMessageEvent.isinstance(make_event("callback_query"))


class TestGetEvents:
    """HTTP-слой ``get_events``."""

    async def test_request_params(
        self, vkteams: VKTeams, mock_api: aioresponses
    ) -> None:
        mock_api.get(url_for("/events/get"), payload={"ok": True, "events": []})
        await vkteams.get_events(last_event_id=42, poll_time=20)

        params = query_of(mock_api, "/bot/v1/events/get")
        assert params["token"] == [vkteams.token]
        assert params["lastEventId"] == ["42"]
        assert params["pollTime"] == ["20"]

    async def test_parses_all_events(
        self, vkteams: VKTeams, mock_api: aioresponses
    ) -> None:
        mock_api.get(
            url_for("/events/get"),
            payload=events_response(*ALL_EVENT_FIXTURES),
        )
        response = await vkteams.get_events(last_event_id=0, poll_time=1)

        assert response.ok
        assert len(response.events) == len(ALL_EVENT_FIXTURES)

    async def test_empty_events(self, vkteams: VKTeams, mock_api: aioresponses) -> None:
        mock_api.get(url_for("/events/get"), payload={"ok": True, "events": []})
        response = await vkteams.get_events(last_event_id=0, poll_time=1)
        assert response.events == []

    async def test_invalid_json_raises(
        self, vkteams: VKTeams, mock_api: aioresponses
    ) -> None:
        from pydantic import ValidationError

        mock_api.get(url_for("/events/get"), body="not a json")
        with pytest.raises(ValidationError):
            await vkteams.get_events(last_event_id=0, poll_time=1)

    async def test_missing_events_key_raises(
        self, vkteams: VKTeams, mock_api: aioresponses
    ) -> None:
        from pydantic import ValidationError

        mock_api.get(url_for("/events/get"), payload={"ok": False})
        with pytest.raises(ValidationError):
            await vkteams.get_events(last_event_id=0, poll_time=1)

    async def test_http_error_body_is_still_parsed(
        self, vkteams: VKTeams, mock_api: aioresponses
    ) -> None:
        """Клиент не смотрит на статус: решает валидность тела."""
        mock_api.get(
            url_for("/events/get"), status=500, payload={"ok": False, "events": []}
        )
        response = await vkteams.get_events(last_event_id=0, poll_time=1)
        assert response.ok is False

    async def test_events_are_logged(
        self,
        vkteams: VKTeams,
        mock_api: aioresponses,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mock_api.get(url_for("/events/get"), payload=events_response("new_message"))
        with caplog.at_level("INFO", logger="vkteams_client.events"):
            await vkteams.get_events(last_event_id=0, poll_time=1)
        assert any("newMessage" in record.getMessage() for record in caplog.records)
